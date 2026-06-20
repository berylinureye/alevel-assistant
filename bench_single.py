"""
单图测试脚本：运行新 pipeline，打印详细结果 + 时间。
"""
from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

# 关键日志等级
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
# 降噪不重要的
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from pipeline.pipeline import run_pipeline


def main():
    if len(sys.argv) < 2:
        print("usage: python3 bench_single.py <image_path> [image_path2 ...]")
        sys.exit(1)

    img_paths = [Path(p) for p in sys.argv[1:]]
    for p in img_paths:
        if not p.exists():
            print(f"file not found: {p}")
            sys.exit(1)

    print(f"=== Running pipeline on {len(img_paths)} image(s): {[p.name for p in img_paths]} ===")
    t0 = time.perf_counter()
    try:
        arg = str(img_paths[0]) if len(img_paths) == 1 else [str(p) for p in img_paths]
        result = run_pipeline(arg)
    except Exception as e:
        print(f"PIPELINE ERROR: {e}")
        raise
    elapsed = time.perf_counter() - t0

    questions = result.get("questions", [])
    print(f"\n=== DONE in {elapsed:.1f}s, {len(questions)} questions ===\n")

    for q in questions:
        qnum = q.get("question_number", "?")
        grading = q.get("grading", {})
        feedback = q.get("feedback", {})
        solution = q.get("solution_text", "") or ""

        print(f"--- Q{qnum} ---")
        print(f"  question_text: {(q.get('question_text') or '')[:200]}")
        print(f"  student_answer: {(q.get('student_answer') or '')[:200]}")
        print(f"  marks (extracted): {q.get('marks')}")
        print(f"  is_correct: {grading.get('is_correct')}")
        print(f"  score: {grading.get('score')}/{grading.get('full_score')}")
        print(f"  error_type: {grading.get('error_type')}")
        print(f"  correct_answer: {(grading.get('correct_answer') or '')[:150]}")
        print(f"  short_feedback: {(grading.get('short_feedback') or '')[:200]}")
        print(f"  grading_confidence: {grading.get('grading_confidence')}")
        print(f"  needs_review: {grading.get('needs_review')}")
        print(f"  used_model: {grading.get('used_model')}")
        if solution:
            print(f"  solution_text (first 300): {solution[:300]}")
        else:
            print(f"  solution_text: <none>")
        print()

    # --- Generate solutions for each question (to test deepseek-reasoner) ---
    print("=== Generating solutions with deepseek-reasoner ===\n")
    from grader.solution_explainer import generate_solution
    from models.schemas import QuestionData, GradeResult, QuestionType
    from pipeline.pipeline import _build_solution_client
    solution_client = _build_solution_client(None, None)
    print(f"  solution_client model: {solution_client.model_id}")

    for q in questions:
        qnum = q.get("question_number", "?")
        if q.get("grading", {}).get("unanswered"):
            continue
        print(f"--- Q{qnum} solution (reasoner) ---")
        t_sol = time.perf_counter()
        try:
            qd = QuestionData(
                question_number=qnum,
                bbox=q.get("bbox", [0, 0, 100, 100]),
                question_text=q.get("question_text", ""),
                student_answer=q.get("student_answer", ""),
                working_steps=q.get("working_steps", []),
                marks=q.get("marks", 0),
                image_quality=q.get("image_quality", "fair"),
                confidence=q.get("confidence", 0.5),
            )
            g = q.get("grading", {})
            gr = GradeResult(
                question_number=qnum,
                question_type=QuestionType(g.get("question_type", "unknown")),
                is_correct=g.get("is_correct", False),
                score=g.get("score", 0.0),
                full_score=g.get("full_score", 0.0),
                error_type=g.get("error_type"),
                knowledge_tags=g.get("knowledge_tags", []),
                needs_review=g.get("needs_review", False),
                short_feedback=g.get("short_feedback", ""),
                grading_confidence=g.get("grading_confidence", 0.5),
                correct_answer=g.get("correct_answer"),
                syllabus_topics=g.get("syllabus_topics", []),
                relevant_formulas=g.get("relevant_formulas", []),
            )
            sol = generate_solution(qd, gr, solution_client, timeout=120)
        except Exception as e:
            sol = f"ERROR: {e}"
        elapsed_sol = time.perf_counter() - t_sol
        print(f"  (generated in {elapsed_sol:.1f}s)")
        print(sol[:800] if sol else "<empty>")
        print()

    # Save full output
    stem = img_paths[0].stem if len(img_paths) == 1 else f"multi_{len(img_paths)}pages_{img_paths[0].stem}"
    out_path = Path(f"bench_out_{stem}.json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"elapsed_seconds": elapsed, "result": result}, f, ensure_ascii=False, indent=2, default=str)
    print(f"Full output saved to {out_path}")


if __name__ == "__main__":
    main()
