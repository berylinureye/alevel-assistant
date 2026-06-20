"""
多Agent并行数学解题系统 — 流式解题入口

Phase 1: 三个模型并行 streaming 调用，边接收 token 边扫描 ANSWER:
         一旦收集到 ≥2 个答案（或超时），立即投票并输出答案行。
Phase 2: 等剩余模型跑完，然后流式生成解题报告（model / local 两种模式）。

不修改现有 agents.py / voting.py，仅复用其中的数据结构和投票函数。

用法:
    python -m math_solver.stream_solver --question "求 1+2+...+100 的值"
    python -m math_solver.stream_solver  # 交互模式
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import AsyncIterator, Optional

import aiohttp

from math_solver.config import (
    AGENT_A,
    MAX_RETRIES,
    ModelConfig,
    REPORT_MODE,
    REPORT_MODEL,
    SOLVER_AGENTS,
    STREAM_ANSWER_TIMEOUT,
    STREAM_MIN_ANSWERS,
)
from math_solver.prompts import (
    REPORT_SYSTEM,
    REPORT_USER_TEMPLATE,
    SOLVER_SYSTEM_PROMPTS,
    SOLVER_USER_TEMPLATE,
)
from math_solver.utils import AgentResult, SolveResult, log
from math_solver.voting import (
    answers_equivalent,
    extract_answer,
    normalize_answer,
    vote,
)


# ═══════════════════════════════════════════════════════════════════════════
# 终端输出辅助
# ═══════════════════════════════════════════════════════════════════════════

def _write(text: str) -> None:
    """写到 stdout 并立即 flush"""
    sys.stdout.write(text)
    sys.stdout.flush()


def _write_line(text: str) -> None:
    _write(text + "\n")


# ═══════════════════════════════════════════════════════════════════════════
# SSE / Streaming 底层
# ═══════════════════════════════════════════════════════════════════════════

async def _stream_chat_api(
    session: aiohttp.ClientSession,
    config: ModelConfig,
    system_prompt: str,
    user_prompt: str,
) -> AsyncIterator[str]:
    """
    调用 OpenAI 兼容的 chat/completions streaming API。
    逐 token yield 文本 delta。
    """
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model_id,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    timeout = aiohttp.ClientTimeout(total=config.timeout)

    async with session.post(
        config.base_url, json=payload, headers=headers, timeout=timeout,
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            raise RuntimeError(f"HTTP {resp.status}: {body[:300]}")

        async for raw_line in resp.content:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if data_str == "[DONE]":
                return

            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1: 流式解题 + 即时答案提取
# ═══════════════════════════════════════════════════════════════════════════

async def _stream_and_extract(
    session: aiohttp.ClientSession,
    config: ModelConfig,
    question: str,
    answer_event: asyncio.Event,
    collected_answers: dict[str, str],
    agent_results: dict[str, AgentResult],
) -> None:
    """
    对单个 Agent 发起 streaming 请求。
    边接收边拼接文本，一旦检测到 ANSWER: xxx 就:
      1. 存入 collected_answers
      2. set answer_event（通知主循环有新答案到了）
    完成后把完整输出存入 agent_results。
    """
    result = AgentResult(agent_name=config.name)
    t0 = time.perf_counter()

    system_prompt = SOLVER_SYSTEM_PROMPTS.get(config.name, SOLVER_SYSTEM_PROMPTS["DeepSeek-V3.2"])
    user_prompt = SOLVER_USER_TEMPLATE.format(question=question)

    buffer = ""
    answer_extracted = False

    for attempt in range(1 + MAX_RETRIES):
        try:
            async for token in _stream_chat_api(session, config, system_prompt, user_prompt):
                buffer += token

                # 实时扫描答案 — 只对已完成的行做提取（buffer 中有 \n）
                # 避免 "ANSWER: 505" 在 "ANSWER: 5050\n" 完成前被误提取
                if not answer_extracted and "\n" in buffer:
                    # 只对已有换行的完整行做提取
                    complete_part = buffer[:buffer.rfind("\n") + 1]
                    raw_ans = extract_answer(complete_part)
                    if raw_ans:
                        norm = normalize_answer(raw_ans)
                        if norm:
                            answer_extracted = True
                            result.raw_answer = raw_ans
                            result.normalized_answer = norm
                            result.elapsed = time.perf_counter() - t0
                            collected_answers[config.name] = norm
                            answer_event.set()
                            log.info(f"  ✓ {config.name}: ANSWER={norm} ({result.elapsed:.1f}s)")
            # streaming 完毕
            break

        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as e:
            if attempt < MAX_RETRIES:
                log.warning(f"  {config.name} 重试 ({attempt+1}/{MAX_RETRIES}): {e}")
                buffer = ""
                answer_extracted = False
                await asyncio.sleep(0.5)
            else:
                result.error = str(e)
                log.warning(f"  ✗ {config.name}: {e}")
                agent_results[config.name] = result
                return
        except asyncio.CancelledError:
            # 被外部 cancel 时仍保存已有结果
            break

    result.raw_output = buffer
    result.success = True
    result.elapsed = time.perf_counter() - t0

    # 如果 streaming 过程中没提取到答案，最终再试一次
    if not answer_extracted:
        raw_ans = extract_answer(buffer)
        if raw_ans:
            norm = normalize_answer(raw_ans)
            result.raw_answer = raw_ans or ""
            result.normalized_answer = norm
            if norm:
                collected_answers[config.name] = norm
                answer_event.set()
                log.info(f"  ✓ {config.name}: ANSWER={norm} (完成后提取, {result.elapsed:.1f}s)")

    agent_results[config.name] = result


async def _collect_answers_streaming(
    question: str,
    session: aiohttp.ClientSession,
    min_count: int = 2,
    timeout: float = 10.0,
) -> tuple[dict[str, str], dict[str, AgentResult], list[asyncio.Task]]:
    """
    并行启动三个 streaming Agent，等待至少 min_count 个答案或超时。
    返回 (collected_answers, agent_results, tasks)。
    tasks 中可能还有正在运行的——调用方应在 Phase 2 等它们完成。
    """
    answer_event = asyncio.Event()
    collected_answers: dict[str, str] = {}     # agent_name → normalized_answer
    agent_results: dict[str, AgentResult] = {}

    tasks = [
        asyncio.create_task(
            _stream_and_extract(
                session, config, question,
                answer_event, collected_answers, agent_results,
            ),
            name=config.name,
        )
        for config in SOLVER_AGENTS
    ]

    # 等待逻辑：每次 answer_event 被 set 时检查数量
    deadline = time.perf_counter() + timeout
    while len(collected_answers) < min_count:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            break
        answer_event.clear()
        # 等 event 或超时
        try:
            await asyncio.wait_for(answer_event.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        # 检查是否所有 task 都已完成（提前结束等待）
        if all(t.done() for t in tasks):
            break

    return collected_answers, agent_results, tasks


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2: 流式报告生成
# ═══════════════════════════════════════════════════════════════════════════

async def _stream_report_model(
    session: aiohttp.ClientSession,
    question: str,
    final_answer: str,
    confidence: str,
    agent_results: dict[str, AgentResult],
) -> None:
    """方案 A：用模型 streaming 生成报告，逐 token 输出到终端"""
    agents = list(SOLVER_AGENTS)

    def _get(idx: int) -> tuple[str, str, str, str, str]:
        cfg = agents[idx]
        ar = agent_results.get(cfg.name)
        name = cfg.name
        if ar and ar.success:
            ans = ar.normalized_answer or "-"
            sol = ar.raw_output[:1500]  # 截断，避免 prompt 太长
            t = f"{ar.elapsed:.1f}"
            check = "✅" if answers_equivalent(ar.normalized_answer, final_answer) else "❌"
        else:
            ans, sol, t, check = "-", "(未返回)", "-", "❌"
        return name, ans, sol, t, check

    name_a, answer_a, solution_a, time_a, check_a = _get(0)
    name_b, answer_b, solution_b, time_b, check_b = _get(1)
    name_c, answer_c, solution_c, time_c, check_c = _get(2)

    agree_count = sum(
        1 for cfg in agents
        if cfg.name in agent_results
        and agent_results[cfg.name].success
        and answers_equivalent(agent_results[cfg.name].normalized_answer, final_answer)
    )

    user_prompt = REPORT_USER_TEMPLATE.format(
        question=question, final_answer=final_answer,
        confidence=confidence, agree_count=agree_count, total_count=len(agents),
        name_a=name_a, solution_a=solution_a, answer_a=answer_a, time_a=time_a, check_a=check_a,
        name_b=name_b, solution_b=solution_b, answer_b=answer_b, time_b=time_b, check_b=check_b,
        name_c=name_c, solution_c=solution_c, answer_c=answer_c, time_c=time_c, check_c=check_c,
    )

    try:
        async for token in _stream_chat_api(
            session, REPORT_MODEL, REPORT_SYSTEM, user_prompt,
        ):
            _write(token)
    except Exception as e:
        _write(f"\n[报告生成失败: {e}，回退到本地模板]\n")
        await _stream_report_local(question, final_answer, confidence, agent_results)

    _write("\n")


async def _stream_report_local(
    question: str,
    final_answer: str,
    confidence: str,
    agent_results: dict[str, AgentResult],
) -> None:
    """方案 B：本地模板拼接 + 打字机效果"""
    agents = list(SOLVER_AGENTS)

    # 统计一致性
    agree_count = sum(
        1 for cfg in agents
        if cfg.name in agent_results
        and agent_results[cfg.name].success
        and answers_equivalent(agent_results[cfg.name].normalized_answer, final_answer)
    )
    total_count = len(agents)

    # 找到与最终答案一致且最早完成的 Agent 的解题过程作为「解题思路」
    winning_solution = ""
    winning_name = ""
    for cfg in agents:
        ar = agent_results.get(cfg.name)
        if ar and ar.success and answers_equivalent(ar.normalized_answer, final_answer):
            winning_solution = ar.raw_output
            winning_name = cfg.name
            break
    if not winning_solution:
        # 没有匹配的，取第一个有输出的
        for cfg in agents:
            ar = agent_results.get(cfg.name)
            if ar and ar.success and ar.raw_output:
                winning_solution = ar.raw_output
                winning_name = cfg.name
                break

    # 从解题过程中去掉第一行的 ANSWER: 行，只保留过程
    solution_lines = winning_solution.split("\n")
    process_text = "\n".join(
        line for line in solution_lines
        if not line.strip().upper().startswith("ANSWER")
    ).strip()
    if len(process_text) > 800:
        process_text = process_text[:800] + "..."

    # 构造表格行
    table_rows = []
    for cfg in agents:
        ar = agent_results.get(cfg.name)
        if ar and ar.success:
            ans = ar.normalized_answer or "-"
            t = f"{ar.elapsed:.1f}s"
            check = "✅" if answers_equivalent(ar.normalized_answer, final_answer) else "❌"
        else:
            ans = "-"
            t = "超时" if (ar and ar.error) else "-"
            check = "❌"
        table_rows.append(f"| {cfg.name:16s} | {ans:>6s} | {t:>6s} | {check}  |")

    # 逐段输出
    sections = [
        "\n## 📋 解题报告\n\n",
        f"**题目**: {question[:120]}{'...' if len(question) > 120 else ''}\n",
        f"**答案**: {final_answer}\n",
        f"**置信度**: {confidence}（{agree_count}/{total_count} 模型一致）\n",
        f"\n### 解题思路 (by {winning_name})\n\n",
        f"{process_text}\n",
        "\n### 模型一致性\n\n",
        "| 模型              |   答案 |   耗时 | 正确 |\n",
        "|-------------------|--------|--------|------|\n",
        *[row + "\n" for row in table_rows],
    ]

    for section in sections:
        for ch in section:
            _write(ch)
            await asyncio.sleep(0.008)
        await asyncio.sleep(0.05)


# ═══════════════════════════════════════════════════════════════════════════
# 进度指示器
# ═══════════════════════════════════════════════════════════════════════════

class _ProgressLine:
    """
    实时刷新的单行进度：
    🔄 正在解题... DeepSeek ✓(3.2s) Qwen ✓(4.1s) GLM ⏳
    """
    def __init__(self, agent_names: list[str]) -> None:
        self.agents = {name: "⏳" for name in agent_names}
        self._printed = False

    def mark_done(self, name: str, elapsed: float) -> None:
        self.agents[name] = f"✓({elapsed:.1f}s)"
        self._refresh()

    def mark_fail(self, name: str) -> None:
        self.agents[name] = "✗"
        self._refresh()

    def _refresh(self) -> None:
        parts = " ".join(f"{n.split('-')[0]} {s}" for n, s in self.agents.items())
        line = f"\r🔄 正在解题... {parts}"
        # 用空格覆盖上一次可能更长的内容
        _write(f"{line:<80}")
        self._printed = True

    def finish(self) -> None:
        if self._printed:
            _write("\r" + " " * 80 + "\r")  # 清除进度行


# ═══════════════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════════════

async def solve_streaming(question: str) -> SolveResult:
    """
    流式解题：
      Phase 1 — 并行 streaming + 即时答案提取 + 投票 → 立即输出答案
      Phase 2 — 等解题过程完成 → 流式输出报告
    """
    result = SolveResult(question=question)
    t_start = time.perf_counter()

    progress = _ProgressLine([c.name for c in SOLVER_AGENTS])
    progress._refresh()  # 显示初始状态

    async with aiohttp.ClientSession() as session:

        # ── Phase 1: 流式收集答案 ──
        collected, agent_map, tasks = await _collect_answers_streaming(
            question, session,
            min_count=STREAM_MIN_ANSWERS,
            timeout=STREAM_ANSWER_TIMEOUT,
        )

        # 更新进度条
        for name, ar in agent_map.items():
            if ar.success and ar.normalized_answer:
                progress.mark_done(name, ar.elapsed)
            elif ar.error:
                progress.mark_fail(name)

        # 投票
        vote_entries = [
            (name, ans, ans)  # (agent_name, raw, normalized) — 这里 raw==normalized
            for name, ans in collected.items()
        ]
        if vote_entries:
            winning_answer, confidence, method = vote(vote_entries)
        else:
            winning_answer, confidence, method = "", "low", "no_answers"

        # 如果需要仲裁但我们在 streaming 模式中，先用最常见的答案
        if method == "arbitration_needed" and collected:
            # 三个全不同，取第一个到达的
            first_name = next(iter(collected))
            winning_answer = collected[first_name]
            confidence = "low"
            method = "first_arrival"

        answer_time = time.perf_counter() - t_start

        # ── 立即输出答案行 ──
        progress.finish()

        agree_count = sum(1 for v in collected.values() if answers_equivalent(v, winning_answer))
        total_with_answer = len(collected)

        if winning_answer:
            confidence_cn = {"high": "高", "medium": "中", "low": "低"}.get(confidence, confidence)
            _write_line(
                f"\n✅ 答案: {winning_answer}"
                f"（置信度: {confidence_cn}, "
                f"{agree_count}/{total_with_answer} 一致, "
                f"耗时 {answer_time:.1f}s）"
            )
        else:
            _write_line(f"\n⚠️  未能获取答案（耗时 {answer_time:.1f}s）")

        # ── Phase 2: 等剩余模型跑完 ──
        still_running = [t for t in tasks if not t.done()]
        if still_running:
            _write("⏳ 等待剩余模型完成...")
            remaining_budget = max(2.0, 20.0 - answer_time)
            done, pending = await asyncio.wait(still_running, timeout=remaining_budget)
            for t in pending:
                t.cancel()
            # 等 cancel 完成
            if pending:
                await asyncio.wait(pending, timeout=1.0)
            _write("\r" + " " * 40 + "\r")

        # 再次更新进度
        for name, ar in agent_map.items():
            if ar.success and ar.normalized_answer:
                progress.mark_done(name, ar.elapsed)

        # 填充 SolveResult
        result.final_answer = winning_answer
        result.confidence = confidence
        result.method = method
        for cfg in SOLVER_AGENTS:
            if cfg.name in agent_map:
                result.agent_results.append(agent_map[cfg.name])
            else:
                result.agent_results.append(AgentResult(agent_name=cfg.name, error="no_result"))

        # ── Phase 2: 流式报告 ──
        if REPORT_MODE == "model":
            await _stream_report_model(
                session, question, winning_answer, confidence, agent_map,
            )
        else:
            await _stream_report_local(
                question, winning_answer, confidence, agent_map,
            )

    result.total_elapsed = time.perf_counter() - t_start
    _write_line(f"\n⏱️  总耗时: {result.total_elapsed:.1f}s"
                f"（答案: {answer_time:.1f}s, 报告: {result.total_elapsed - answer_time:.1f}s）")

    return result


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="多Agent并行数学解题（流式输出）")
    parser.add_argument("--question", "-q", type=str, help="题目文本")
    parser.add_argument("--report", "-r", choices=["model", "local"], help="报告模式覆盖")
    args = parser.parse_args()

    if args.report:
        import math_solver.config as _cfg
        _cfg.REPORT_MODE = args.report

    if args.question:
        asyncio.run(solve_streaming(args.question))
    else:
        print("多Agent并行数学解题 — 流式交互模式")
        print("输入题目按回车，输入 quit 退出\n")
        while True:
            try:
                question = input("题目 > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question or question.lower() in ("quit", "exit", "q"):
                break
            asyncio.run(solve_streaming(question))
            print()


if __name__ == "__main__":
    main()
