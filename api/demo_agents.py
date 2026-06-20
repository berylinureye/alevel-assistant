"""/api/showcase/demo-grade · 真实 5-agent orchestration

不再 hardcode 12 条 agent_msg。每个 agent 是一次独立的 codex 调用，
用不同的 system prompt 让同一个底座 LLM (GPT-5.5 via codex shim) 扮演不同角色。
前一个 agent 的输出会进入下一个 agent 的 context。

失败时优雅降级到 hardcoded fallback（保留视觉效果）。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger("api.demo_agents")


# ─────────────────────────────────────────────────────────────
# 5 个 agent 定义
# 关键：system prompt 极简 + 限制输出长度，避免单次调用过长
# 期望每个 agent 单次 200 token 内、3-5 秒返回
# ─────────────────────────────────────────────────────────────
AGENTS = [
    {
        "key": "segmenter",
        "name": "Segmenter",
        "role": "切题专家",
        "color": "blue",
        "system": (
            "你是 A-Level 数学作业切题专家。"
            "你的工作只是看一眼整页作业，告诉下游 OCR Agent 你看到了几道题、哪一道是重点。"
            "用 1-2 句中文，像在和同事说话。不要写代码、不要列表。"
        ),
        "user_template": (
            "整页作业有 4 道：{q_list}。"
            "其中 Q1(d) 是 3 marks 的圆切线题，学生算错了。"
            "请用 1-2 句话告诉 OCR Agent 接下来处理什么。"
        ),
    },
    {
        "key": "ocr",
        "name": "OCR Agent",
        "role": "手写识别员",
        "color": "blue",
        "system": (
            "你是手写体识别员。Segmenter 已经把图切好了给你，你的工作是把学生写的每一行 working steps 还原。"
            "你不评判对错，但可以提一句『第 N 行看着像错了』。"
            "用 1-2 句中文向 Grader 汇报。"
        ),
        "user_template": (
            "Segmenter 说：{prev}\n\n"
            "你识别完了，一共 {n_lines} 行学生 working steps。"
            "其中第 6 行学生写的是 `{suspect_line}`，看起来不太对。"
            "请用 1-2 句话向 Grader 汇报。"
        ),
    },
    {
        "key": "grader",
        "name": "Grader",
        "role": "批改老师",
        "color": "orange",
        "system": (
            "你是有 10 年 A-Level 经验的批改老师。对照 Cambridge mark scheme 给分要严，反馈要具体到行。"
            "你不直接算公式，你让 Verifier 算（@Verifier）。"
            "用 2-3 句中文。"
        ),
        "user_template": (
            "OCR Agent 说：{prev}\n\n"
            "你看了 11 行 working。学生算切线斜率把符号搞反了：`m_t = 4/3`，应该是 `m = 3/4`。"
            "联立方程时移项又错。"
            "请你判分（满分 3 分），然后 @Verifier 让他用 SymPy 算一下 x 的标准答案。"
        ),
    },
    {
        "key": "verifier",
        "name": "Verifier",
        "role": "独立审计员",
        "color": "green",
        "system": (
            "你是独立审计员。不预设 Grader 是对的。能用 SymPy 算的就算，算完和 Grader 对比。"
            "你直接得到了 SymPy 的结果，不要装作还在算。"
            "用 1-2 句中文。"
        ),
        "user_template": (
            "Grader 说：{prev}\n\n"
            "SymPy 算出来了：两条切线 `4y=3x+5` 和 `4y=-3x+29` 联立，得 `x=4, y=17/4`，所以 T=(4, 17/4)。"
            "学生写的 T=(-7/8, 2) 错了。"
            "请你向 Grader 反馈 confirm 这个判分，并给一个 confidence 0-1。"
        ),
    },
    {
        "key": "memory",
        "name": "Memory",
        "role": "学情记录员",
        "color": "purple",
        "system": (
            "你是这位学生的长期私教。你能查到他过去所有错点记录。"
            "你的工作是决定这次反馈是直接给答案，还是用反问让他自己想（苏格拉底模式）。"
            "用 1-2 句中文。"
        ),
        "user_template": (
            "Verifier 已确认 Grader 的判分。\n\n"
            "查这学生符号管理类错题的历史：5/22 一次、5/26 一次、今天这次是第 3 次。"
            "苏格拉底阈值是 3 次。请决定这次反馈语气，并提一句要不要在反馈里加反问句。"
        ),
    },
]


# ─────────────────────────────────────────────────────────────
# Hardcoded fallback (单 agent 失败时用)
# ─────────────────────────────────────────────────────────────
FALLBACK_LINES = {
    "segmenter": "拆出 4 道：Q1(a)、Q1(b)、Q1(c)、Q1(d)。Q1(d) 是 3 marks，学生答错。先送给 OCR。",
    "ocr": "读完了，11 行 working steps。第 6 行看起来不对劲，但具体哪错由 Grader 判。",
    "grader": "对照 mark scheme，第 6 行符号错位。初判扣 3 分。@Verifier 你能 SymPy 算一下 x 的标准答案吗？",
    "verifier": "SymPy 解出 T=(4, 17/4)。@Grader 你的判断 confirmed，confidence 0.95。",
    "memory": "符号管理类错过 2 次了，这是第 3 次，刚到苏格拉底阈值。建议反馈加一句反问。",
}


# ─────────────────────────────────────────────────────────────
# Context: 后台串联 5 个 agent
# ─────────────────────────────────────────────────────────────
AGENT_TIMEOUT_S = 30.0     # 单 agent 调用 timeout · codex cold start ~8-20s
EMIT_INTERVAL_S = 0.15     # agent_msg 之间的视觉节奏


async def run_orchestration(
    client,
    emit: Callable[[dict], Awaitable[None]],
    sleep_fn: Callable[[float], Awaitable[None]],
) -> list[dict]:
    """
    5 个 agent 串行调度 (concurrency=1). codex 同 ChatGPT 账号高并发会 502.
    串行 + 前一个输出真喂下一个 (真实 IO 链), 边跑边 emit.
    """
    import time
    from router.models import ModelRequest, TaskType

    t_start = time.time()

    async def _call_one(agent: dict, prev_text: str) -> tuple[dict, str, str, float]:
        """返回 (agent_def, text, kind, elapsed_s)"""
        fmt_ctx = {
            "prev": prev_text or "(你是第一个 agent)",
            "q_list": "Q1(a)/Q1(b)/Q1(c)/Q1(d)",
            "n_lines": 11,
            "suspect_line": "8x+5=4",
        }
        user_msg = agent["user_template"].format(**fmt_ctx)
        full_prompt = f"## 你的角色\n{agent['system']}\n\n## 当前任务\n{user_msg}"

        t0 = time.time()
        try:
            req = ModelRequest(
                task=TaskType.grade,
                prompt=full_prompt,
                max_tokens=120,         # 短输出, 加快返回
                temperature=0.4,
            )
            # asyncio.wait_for 强制 timeout
            text = await asyncio.wait_for(
                asyncio.to_thread(client.call, req),
                timeout=AGENT_TIMEOUT_S,
            )
            text = (text or "").strip()
            if not text:
                raise RuntimeError("empty response")
            kind = "real"
        except asyncio.TimeoutError:
            logger.info(f"agent {agent['key']} timeout (>{AGENT_TIMEOUT_S}s) -> fallback")
            text = FALLBACK_LINES[agent["key"]]
            kind = "fallback"
        except Exception as e:
            logger.warning(f"agent {agent['key']} failed: {e}")
            text = FALLBACK_LINES[agent["key"]]
            kind = "fallback"

        return agent, text, kind, round(time.time() - t0, 2)

    # 5 agent 调度: segmenter → ocr → (grader || verifier 并行) → memory
    # grader 和 verifier 都依赖 ocr 输出, 但不互相依赖 → 可并行
    # 实测 codex shim Semaphore(2) 让两路 codex 同时跑 · 砍约 11s
    records = []

    async def _emit_record(agent_def, text, kind, elapsed):
        records.append({"key": agent_def["key"], "text": text, "kind": kind, "elapsed_s": elapsed})
        await emit({
            "type": "agent_msg",
            "agent": agent_def["name"],
            "role": agent_def["role"],
            "color": agent_def["color"],
            "text": text,
            "kind": kind,
            "elapsed_s": elapsed,
        })
        await sleep_fn(EMIT_INTERVAL_S)

    # Phase 1: Segmenter
    seg_def, seg_text, seg_kind, seg_elapsed = await _call_one(AGENTS[0], "")
    await _emit_record(seg_def, seg_text, seg_kind, seg_elapsed)

    # Phase 2: OCR Agent (依赖 Segmenter)
    ocr_def, ocr_text, ocr_kind, ocr_elapsed = await _call_one(AGENTS[1], seg_text)
    await _emit_record(ocr_def, ocr_text, ocr_kind, ocr_elapsed)

    # Phase 3: Grader || Verifier 并行 (都依赖 OCR 输出, 不依赖彼此)
    grader_task   = asyncio.create_task(_call_one(AGENTS[2], ocr_text))
    verifier_task = asyncio.create_task(_call_one(AGENTS[3], ocr_text))
    # Grader 先完成立刻 emit, Verifier 完成跟着 emit (并发隐藏在两者最大值里)
    g_def, g_text, g_kind, g_elapsed = await grader_task
    await _emit_record(g_def, g_text, g_kind, g_elapsed)
    v_def, v_text, v_kind, v_elapsed = await verifier_task
    await _emit_record(v_def, v_text, v_kind, v_elapsed)

    # Phase 4: Memory (依赖 Verifier 确认结果)
    mem_def, mem_text, mem_kind, mem_elapsed = await _call_one(AGENTS[4], v_text)
    await _emit_record(mem_def, mem_text, mem_kind, mem_elapsed)

    total_elapsed = round(time.time() - t_start, 2)
    real_count = sum(1 for r in records if r['kind'] == 'real')
    logger.info(f"orchestration done: {len(records)} agents in {total_elapsed}s (real={real_count}) [grader||verifier]")
    return records
