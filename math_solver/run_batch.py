"""
多Agent并行数学解题系统 — 批量测试入口

读取 JSONL 题目文件，逐题解答，输出结果和统计报告。

用法:
    python -m math_solver.run_batch --input questions.jsonl --output results.jsonl
    python -m math_solver.run_batch --input questions.jsonl  # 结果输出到 stdout

questions.jsonl 格式:
    {"id": 1, "question": "...", "answer": "42"}
    {"id": 2, "question": "...", "answer": "100"}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from math_solver.main import solve
from math_solver.utils import log
from math_solver.voting import answers_equivalent, normalize_answer


async def run_batch(
    input_path: str,
    output_path: str | None = None,
    stream: bool = False,
) -> None:
    """批量解题并生成统计报告"""

    questions = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    log.info(f"加载 {len(questions)} 道题目")

    results = []
    correct_count = 0
    agent_correct: dict[str, int] = {}
    arbitration_count = 0
    total_time = 0.0

    out_file = open(output_path, "w", encoding="utf-8") if output_path else None

    try:
        for i, item in enumerate(questions, 1):
            qid = item.get("id", i)
            question = item["question"]
            correct_answer = normalize_answer(item.get("answer", ""))

            log.info(f"\n{'='*60}")
            log.info(f"[{i}/{len(questions)}] ID={qid}")

            if stream:
                from math_solver.stream_solver import solve_streaming
                # 在 batch 模式下，流式报告写入文件而非打印
                import math_solver.config as _cfg
                _cfg.REPORT_MODE = "local"
                result = await solve_streaming(question)
            else:
                result = await solve(question)

            # 判断正确性
            is_correct = answers_equivalent(result.final_answer, correct_answer) if correct_answer else None

            if is_correct:
                correct_count += 1

            if result.method in ("arbitration", "arbitration_failed_first_available"):
                arbitration_count += 1

            total_time += result.total_elapsed

            # 各 Agent 单独正确率统计
            for ar in result.agent_results:
                if ar.agent_name not in agent_correct:
                    agent_correct[ar.agent_name] = 0
                if ar.success and ar.normalized_answer and correct_answer:
                    if answers_equivalent(ar.normalized_answer, correct_answer):
                        agent_correct[ar.agent_name] += 1

            # 输出行
            out_record = {
                "id": qid,
                "question": question,
                "correct_answer": correct_answer,
                "model_answer": result.final_answer,
                "is_correct": is_correct,
                "confidence": result.confidence,
                "time_seconds": round(result.total_elapsed, 2),
                "method": result.method,
                "agent_answers": {
                    ar.agent_name: ar.normalized_answer or None
                    for ar in result.agent_results
                },
            }
            results.append(out_record)

            line_out = json.dumps(out_record, ensure_ascii=False)
            if out_file:
                out_file.write(line_out + "\n")
                out_file.flush()
            else:
                print(line_out)

            # 进度
            status = "✅" if is_correct else ("❌" if is_correct is False else "❓")
            log.info(
                f"  {status} ID={qid} | 答案={result.final_answer} "
                f"(正确={correct_answer}) | {result.method} | {result.total_elapsed:.1f}s"
            )

    finally:
        if out_file:
            out_file.close()

    # ── 统计报告 ──
    n = len(questions)
    has_answers = sum(1 for item in questions if item.get("answer"))

    print("\n" + "=" * 60)
    print("📊 批量测试统计报告")
    print("=" * 60)

    if has_answers > 0:
        print(f"  总题数:         {n}")
        print(f"  有标准答案:     {has_answers}")
        print(f"  系统正确:       {correct_count}/{has_answers} ({correct_count/has_answers*100:.1f}%)")
        print()

        print("  各 Agent 单独正确率:")
        for name, cnt in sorted(agent_correct.items()):
            pct = cnt / has_answers * 100 if has_answers else 0
            print(f"    {name:20s}: {cnt}/{has_answers} ({pct:.1f}%)")

        # 投票提升
        best_single = max(agent_correct.values()) if agent_correct else 0
        improvement = correct_count - best_single
        print(f"\n  投票/仲裁相比最佳单模型提升: +{improvement} 题 "
              f"({best_single} → {correct_count})")

    print(f"\n  仲裁触发次数:   {arbitration_count}/{n} ({arbitration_count/n*100:.1f}%)")
    print(f"  平均耗时:       {total_time/n:.1f}s")
    print(f"  总耗时:         {total_time:.1f}s")

    # 方法分布
    method_counts: dict[str, int] = {}
    for r in results:
        m = r["method"]
        method_counts[m] = method_counts.get(m, 0) + 1
    print(f"\n  决策方式分布:")
    for m, c in sorted(method_counts.items(), key=lambda x: -x[1]):
        print(f"    {m:30s}: {c} ({c/n*100:.1f}%)")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="多Agent并行数学解题系统 — 批量测试")
    parser.add_argument("--input", "-i", required=True, help="题目 JSONL 文件路径")
    parser.add_argument("--output", "-o", help="结果输出 JSONL 路径（默认输出到 stdout）")
    parser.add_argument("--stream", "-s", action="store_true", help="使用流式模式")
    args = parser.parse_args()

    asyncio.run(run_batch(args.input, args.output, stream=args.stream))


if __name__ == "__main__":
    main()
