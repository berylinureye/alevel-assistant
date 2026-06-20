"""
多Agent并行数学解题系统 — 主入口

调度流程:
  1. 并行发送题目给三个解题 Agent（≤15s）
  2. 提取答案 → 投票（本地逻辑，瞬时）
  3. 若不一致 → 触发仲裁 Agent（≤13s）
  4. 若全超时 → 回退到 DeepSeek R1 单独解题

用法:
    python -m math_solver.main --question "求 1+2+...+100 的值"
    python -m math_solver.main  # 交互模式
"""
from __future__ import annotations

import argparse
import asyncio
import time

from math_solver.agents import run_all_solvers, run_arbitrator, run_fallback
from math_solver.config import ARBITRATOR_TIMEOUT, SOLVER_TIMEOUT
from math_solver.utils import AgentResult, SolveResult, log
from math_solver.voting import extract_answer, normalize_answer, vote


# ---------------------------------------------------------------------------
# 核心调度
# ---------------------------------------------------------------------------

async def solve(question: str) -> SolveResult:
    """
    解一道数学题。完整的三层流程:
    并行解题 → 投票 → 条件仲裁。
    """
    result = SolveResult(question=question)
    t_start = time.perf_counter()

    # ── 第一层：并行解题 ──
    log.info("=" * 60)
    log.info(f"📝 题目: {question[:80]}{'...' if len(question) > 80 else ''}")
    log.info("── 第一层: 并行解题 ──")

    agent_results = await run_all_solvers(question, timeout=SOLVER_TIMEOUT)
    result.agent_results = agent_results

    # 打印各 Agent 结果
    for ar in agent_results:
        status = "✅" if ar.success else "❌"
        ans_display = ar.normalized_answer or ar.error or "(无)"
        log.info(f"  {status} {ar.agent_name}: 答案={ans_display}  耗时={ar.elapsed:.1f}s")

    # 检查是否全部失败
    successful = [ar for ar in agent_results if ar.success and ar.normalized_answer]

    if len(successful) == 0:
        # 全超时/全失败 → 回退
        log.info("── 全部失败，回退到 DeepSeek R1 ──")
        remaining = max(28.0, 30.0 - (time.perf_counter() - t_start))
        fallback = await run_fallback(question, timeout=remaining)
        result.agent_results.append(fallback)
        result.final_answer = fallback.normalized_answer
        result.confidence = "low"
        result.method = "fallback"
        result.total_elapsed = time.perf_counter() - t_start
        log.info(f"  🔄 回退答案: {fallback.normalized_answer}  耗时={fallback.elapsed:.1f}s")
        return result

    # ── 第二层：投票 ──
    log.info("── 第二层: 投票 ──")

    vote_entries = [
        (ar.agent_name, ar.raw_answer, ar.normalized_answer)
        for ar in agent_results
        if ar.success
    ]

    winning_answer, confidence, method = vote(vote_entries)

    if method != "arbitration_needed":
        result.final_answer = winning_answer
        result.confidence = confidence
        result.method = method
        result.total_elapsed = time.perf_counter() - t_start
        log.info(f"  🗳  投票结果: {winning_answer}  置信度={confidence}  方式={method}")
        return result

    # ── 第三层：仲裁 ──
    log.info("── 第三层: 仲裁 (三答案不一致) ──")

    remaining_time = max(5.0, 30.0 - (time.perf_counter() - t_start) - 0.5)
    arb_timeout = min(ARBITRATOR_TIMEOUT, remaining_time)

    arb_answer, arb_output, arb_elapsed = await run_arbitrator(
        question, agent_results, timeout=arb_timeout,
    )
    result.arbitrator_output = arb_output
    result.arbitrator_elapsed = arb_elapsed

    if arb_answer:
        result.final_answer = arb_answer
        result.confidence = "medium"
        result.method = "arbitration"
        log.info(f"  ⚖️  仲裁答案: {arb_answer}  耗时={arb_elapsed:.1f}s")
    else:
        # 仲裁也失败了，从已有答案中选第一个
        result.final_answer = successful[0].normalized_answer
        result.confidence = "low"
        result.method = "arbitration_failed_first_available"
        log.warning(f"  ⚠️  仲裁失败，使用第一个可用答案: {result.final_answer}")

    result.total_elapsed = time.perf_counter() - t_start
    return result


# ---------------------------------------------------------------------------
# 结果展示
# ---------------------------------------------------------------------------

def print_result(result: SolveResult) -> None:
    """格式化打印解题结果"""
    print()
    print("=" * 60)
    print(f"📝 题目: {result.question}")
    print(f"✅ 最终答案: {result.final_answer}")
    print(f"🎯 置信度: {result.confidence}")
    print(f"📊 决策方式: {result.method}")
    print(f"⏱  总耗时: {result.total_elapsed:.2f}s")
    print()
    print("各 Agent 详情:")
    for ar in result.agent_results:
        status = "OK" if ar.success else f"FAIL({ar.error})"
        print(f"  {ar.agent_name:20s} | 答案: {ar.normalized_answer or '-':>10s} | "
              f"耗时: {ar.elapsed:5.1f}s | {status}")
    if result.arbitrator_output:
        print(f"\n仲裁 Agent (耗时 {result.arbitrator_elapsed:.1f}s):")
        # 只打印前 200 字符
        preview = result.arbitrator_output[:200]
        if len(result.arbitrator_output) > 200:
            preview += "..."
        print(f"  {preview}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="多Agent并行数学解题系统")
    parser.add_argument("--question", "-q", type=str, help="题目文本")
    parser.add_argument(
        "--stream", "-s", action="store_true",
        help="流式模式: 先秒出答案，再逐行输出报告",
    )
    parser.add_argument("--report", "-r", choices=["model", "local"], help="报告模式 (仅 --stream)")
    args = parser.parse_args()

    if args.stream:
        from math_solver.stream_solver import solve_streaming, main as stream_main
        if args.report:
            import math_solver.config as _cfg
            _cfg.REPORT_MODE = args.report
        if args.question:
            asyncio.run(solve_streaming(args.question))
        else:
            stream_main()
        return

    if args.question:
        result = asyncio.run(solve(args.question))
        print_result(result)
    else:
        # 交互模式
        print("多Agent并行数学解题系统 — 交互模式")
        print("输入题目按回车，输入 quit 退出\n")
        while True:
            try:
                question = input("题目 > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question or question.lower() in ("quit", "exit", "q"):
                break
            result = asyncio.run(solve(question))
            print_result(result)


if __name__ == "__main__":
    main()
