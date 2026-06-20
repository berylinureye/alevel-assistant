"""
多Agent并行数学解题系统 — Agent 调用逻辑

使用 aiohttp 实现真正的并行 HTTP 请求。
包含：三个解题 Agent、仲裁 Agent、全超时回退。
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

import aiohttp

from math_solver.config import (
    ARBITRATOR,
    MAX_RETRIES,
    ModelConfig,
    SOLVER_AGENTS,
)
from math_solver.prompts import (
    ARBITRATOR_SYSTEM,
    ARBITRATOR_USER_TEMPLATE,
    FALLBACK_SYSTEM,
    FALLBACK_USER_TEMPLATE,
    SOLVER_SYSTEM_PROMPTS,
    SOLVER_USER_TEMPLATE,
)
from math_solver.utils import AgentResult, log
from math_solver.voting import extract_answer, normalize_answer


# ---------------------------------------------------------------------------
# 底层 API 调用
# ---------------------------------------------------------------------------

async def _call_chat_api(
    session: aiohttp.ClientSession,
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    调用 OpenAI 兼容的 chat/completions API。
    返回 assistant 的文本内容。
    失败时 raise。
    """
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model": config.model_id,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    timeout = aiohttp.ClientTimeout(total=config.timeout)

    for attempt in range(1 + MAX_RETRIES):
        try:
            async with session.post(
                config.base_url,
                json=payload,
                headers=headers,
                timeout=timeout,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"HTTP {resp.status}: {body[:300]}")
                data = await resp.json()

                # 提取文本 — 兼容各家 API 的细微差异
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError(f"Empty choices: {data}")

                message = choices[0].get("message", {})
                content = message.get("content", "")

                # DeepSeek R1 thinking mode：reasoning_content 在 message 中
                if not content and "reasoning_content" in message:
                    content = message["reasoning_content"]

                return content

        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as e:
            if attempt < MAX_RETRIES:
                log.warning(f"  {config.name} 重试 ({attempt+1}/{MAX_RETRIES}): {e}")
                await asyncio.sleep(0.5)
            else:
                raise


# ---------------------------------------------------------------------------
# 单个解题 Agent
# ---------------------------------------------------------------------------

async def run_solver_agent(
    session: aiohttp.ClientSession,
    config: ModelConfig,
    question: str,
) -> AgentResult:
    """运行单个解题 Agent，返回 AgentResult。不抛异常。"""
    result = AgentResult(agent_name=config.name)
    t0 = time.perf_counter()

    system_prompt = SOLVER_SYSTEM_PROMPTS.get(config.name, SOLVER_SYSTEM_PROMPTS["DeepSeek-V3.2"])
    user_prompt = SOLVER_USER_TEMPLATE.format(question=question)

    try:
        output = await _call_chat_api(session, config, system_prompt, user_prompt)
        result.raw_output = output
        result.success = True

        raw_ans = extract_answer(output)
        result.raw_answer = raw_ans or ""
        result.normalized_answer = normalize_answer(raw_ans) if raw_ans else ""

    except asyncio.TimeoutError:
        result.error = "timeout"
        log.warning(f"  ⏰ {config.name} 超时 (>{config.timeout}s)")
    except Exception as e:
        result.error = str(e)
        log.warning(f"  ❌ {config.name} 错误: {e}")
    finally:
        result.elapsed = time.perf_counter() - t0

    return result


# ---------------------------------------------------------------------------
# 并行解题（第一层）
# ---------------------------------------------------------------------------

async def run_all_solvers(
    question: str,
    timeout: float = 15.0,
) -> list[AgentResult]:
    """并行运行三个解题 Agent，统一超时控制。"""
    async with aiohttp.ClientSession() as session:
        tasks = [
            asyncio.create_task(
                run_solver_agent(session, config, question),
                name=config.name,
            )
            for config in SOLVER_AGENTS
        ]

        # 给全局 wait 比各 agent 自身的 aiohttp timeout 多 2 秒缓冲
        # 这样 agent 可以自行超时并返回错误结果，而不是被 cancel 丢掉
        done, pending = await asyncio.wait(tasks, timeout=timeout + 2.0)

        # 取消仍在 pending 的任务（极端情况）
        for task in pending:
            task.cancel()
            log.warning(f"  ⏰ {task.get_name()} 被全局超时取消")

        # 等待 cancel 完成
        if pending:
            await asyncio.wait(pending, timeout=1.0)

        results: list[AgentResult] = []
        for task in tasks:
            if task.done() and not task.cancelled():
                results.append(task.result())
            else:
                results.append(AgentResult(
                    agent_name=task.get_name(),
                    error="global_timeout",
                ))

    return results


# ---------------------------------------------------------------------------
# 仲裁 Agent（第三层）
# ---------------------------------------------------------------------------

async def run_arbitrator(
    question: str,
    agent_results: list[AgentResult],
    timeout: float = 13.0,
) -> tuple[str, str, Optional[float]]:
    """
    运行仲裁 Agent，判断哪个答案正确。

    返回:
        (normalized_answer, raw_output, elapsed)
    """
    # 构造仲裁 prompt
    # 确保有三个 agent 的结果（可能有的失败了）
    def _get(idx: int) -> tuple[str, str, str]:
        if idx < len(agent_results) and agent_results[idx].success:
            r = agent_results[idx]
            return r.agent_name, r.raw_answer or "(未提取到答案)", r.raw_output
        return f"Agent-{idx}", "(未返回)", "(请求失败)"

    name_a, answer_a, solution_a = _get(0)
    name_b, answer_b, solution_b = _get(1)
    name_c, answer_c, solution_c = _get(2)

    user_prompt = ARBITRATOR_USER_TEMPLATE.format(
        question=question,
        name_a=name_a, answer_a=answer_a, solution_a=solution_a,
        name_b=name_b, answer_b=answer_b, solution_b=solution_b,
        name_c=name_c, answer_c=answer_c, solution_c=solution_c,
    )

    t0 = time.perf_counter()
    try:
        async with aiohttp.ClientSession() as session:
            arb_config = ModelConfig(
                name=ARBITRATOR.name,
                base_url=ARBITRATOR.base_url,
                model_id=ARBITRATOR.model_id,
                api_key_env=ARBITRATOR.api_key_env,
                timeout=timeout,
                max_tokens=ARBITRATOR.max_tokens,
                temperature=ARBITRATOR.temperature,
            )
            output = await _call_chat_api(
                session, arb_config, ARBITRATOR_SYSTEM, user_prompt,
            )
            elapsed = time.perf_counter() - t0
            raw_ans = extract_answer(output)
            norm = normalize_answer(raw_ans) if raw_ans else ""
            return norm, output, elapsed

    except Exception as e:
        elapsed = time.perf_counter() - t0
        log.warning(f"  ❌ 仲裁 Agent 失败: {e}")
        return "", str(e), elapsed


# ---------------------------------------------------------------------------
# 全超时回退：DeepSeek R1 单独解题
# ---------------------------------------------------------------------------

async def run_fallback(
    question: str,
    timeout: float = 28.0,
) -> AgentResult:
    """所有 Agent 全超时时的回退方案：DeepSeek R1 单独解题。"""
    result = AgentResult(agent_name="DeepSeek-R1-Fallback")
    t0 = time.perf_counter()

    user_prompt = FALLBACK_USER_TEMPLATE.format(question=question)

    try:
        async with aiohttp.ClientSession() as session:
            fallback_config = ModelConfig(
                name="DeepSeek-R1-Fallback",
                base_url=ARBITRATOR.base_url,
                model_id=ARBITRATOR.model_id,
                api_key_env=ARBITRATOR.api_key_env,
                timeout=timeout,
                max_tokens=ARBITRATOR.max_tokens,
                temperature=0.0,
            )
            output = await _call_chat_api(
                session, fallback_config,
                FALLBACK_SYSTEM, user_prompt,
            )
            result.raw_output = output
            result.success = True
            raw_ans = extract_answer(output)
            result.raw_answer = raw_ans or ""
            result.normalized_answer = normalize_answer(raw_ans) if raw_ans else ""

    except Exception as e:
        result.error = str(e)
        log.error(f"  ❌ 回退 Agent 也失败: {e}")
    finally:
        result.elapsed = time.perf_counter() - t0

    return result
