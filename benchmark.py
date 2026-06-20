"""Benchmark helper for test assets.

Examples:
    python3 benchmark.py
    python3 benchmark.py --run-pipeline
    python3 benchmark.py --run-pipeline --expectations benchmark_expectations.json --output benchmark_report.json
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image

from pipeline.pipeline import run_pipeline
from utils.image_utils import load_image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
PDF_SUFFIXES = {".pdf"}
FRONTEND_IMAGE_LIMIT = 20 * 1024 * 1024
FRONTEND_PDF_LIMIT = 20 * 1024 * 1024
BACKEND_IMAGE_LIMIT = 20 * 1024 * 1024


def _estimate_pdf_pages(path: Path) -> int | None:
    try:
        data = path.read_bytes()
    except Exception:
        return None
    count = data.count(b"/Type /Page")
    return count or None


def _safe_round(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def _frontend_accepts(path: Path) -> bool:
    suffix = path.suffix.lower()
    size = path.stat().st_size
    if suffix in IMAGE_SUFFIXES:
        return size <= FRONTEND_IMAGE_LIMIT
    if suffix in PDF_SUFFIXES:
        return size <= FRONTEND_PDF_LIMIT
    return False


def _backend_accepts(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES and path.stat().st_size <= BACKEND_IMAGE_LIMIT


def _inspect_image(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        with Image.open(path) as img:
            result["original_format"] = img.format
            result["original_size"] = [img.width, img.height]
    except Exception as exc:
        result["original_open_error"] = str(exc)

    try:
        processed = load_image(str(path))
        result["backend_can_open"] = True
        result["processed_size"] = [processed.width, processed.height]
    except Exception as exc:
        result["backend_can_open"] = False
        result["backend_open_error"] = str(exc)
    return result


def _compare_expectations(
    result: dict[str, Any],
    expected: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not expected or "pipeline" not in result:
        return None
    pipeline = result["pipeline"]
    if pipeline.get("status") != "ok":
        return {"status": "skipped", "reason": pipeline.get("status")}

    comparison: dict[str, Any] = {}
    expected_qcount = expected.get("question_count")
    if isinstance(expected_qcount, int):
        comparison["question_count_match"] = expected_qcount == pipeline.get("question_count")

    expected_questions = expected.get("questions", {})
    if isinstance(expected_questions, dict):
        actual_by_qn = {
            q.get("question_number"): q
            for q in pipeline.get("questions", [])
            if isinstance(q, dict) and q.get("question_number")
        }
        judged = 0
        correct_matches = 0
        score_matches = 0
        for qn, exp_question in expected_questions.items():
            if not isinstance(exp_question, dict):
                continue
            actual = actual_by_qn.get(qn)
            if not actual:
                continue
            judged += 1
            if "is_correct" in exp_question and exp_question["is_correct"] == actual.get("is_correct"):
                correct_matches += 1
            if "score" in exp_question and exp_question["score"] == actual.get("score"):
                score_matches += 1
        comparison["judged_questions"] = judged
        if judged > 0:
            comparison["correctness_match_rate"] = _safe_round(correct_matches / judged)
            comparison["score_match_rate"] = _safe_round(score_matches / judged)

    return comparison or None


def _run_pipeline_once(path: Path) -> dict[str, Any]:
    start = time.perf_counter()
    output = run_pipeline(str(path))
    elapsed = time.perf_counter() - start

    questions = output.get("questions", [])
    question_records = [
        {
            "question_number": q.get("question_number"),
            "confidence": q.get("confidence"),
            "is_correct": q.get("grading", {}).get("is_correct"),
            "score": q.get("grading", {}).get("score"),
            "needs_review": q.get("grading", {}).get("needs_review"),
        }
        for q in questions
        if isinstance(q, dict)
    ]
    confidences = [q["confidence"] for q in question_records if isinstance(q.get("confidence"), (int, float))]

    return {
        "status": "ok",
        "elapsed_seconds": _safe_round(elapsed),
        "question_count": len(question_records),
        "avg_confidence": _safe_round(sum(confidences) / len(confidences)) if confidences else None,
        "review_count": sum(1 for q in question_records if q.get("needs_review")),
        "questions": question_records,
        "page_summary": output.get("page_summary", {}),
    }


def build_report(
    input_dir: Path,
    run_pipeline_flag: bool,
    expectations: dict[str, Any] | None,
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    pipeline_times: list[float] = []
    pipeline_confidences: list[float] = []
    pipeline_executed = 0
    expected_accuracy_rows = 0
    correctness_rates: list[float] = []
    score_rates: list[float] = []

    can_run_pipeline = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    for path in sorted(p for p in input_dir.iterdir() if p.is_file()):
        suffix = path.suffix.lower()
        kind = "image" if suffix in IMAGE_SUFFIXES else "pdf" if suffix in PDF_SUFFIXES else "other"
        result: dict[str, Any] = {
            "filename": path.name,
            "kind": kind,
            "size_mb": _safe_round(path.stat().st_size / 1024 / 1024),
            "mime_type": mimetypes.guess_type(path.name)[0],
            "frontend_accepts": _frontend_accepts(path),
            "backend_accepts": _backend_accepts(path),
        }

        if kind == "image":
            result.update(_inspect_image(path))
        elif kind == "pdf":
            result["estimated_pages"] = _estimate_pdf_pages(path)

        if run_pipeline_flag and kind == "image" and result.get("backend_accepts"):
            if can_run_pipeline:
                try:
                    result["pipeline"] = _run_pipeline_once(path)
                    pipeline_executed += 1
                    elapsed = result["pipeline"].get("elapsed_seconds")
                    avg_conf = result["pipeline"].get("avg_confidence")
                    if isinstance(elapsed, (int, float)):
                        pipeline_times.append(float(elapsed))
                    if isinstance(avg_conf, (int, float)):
                        pipeline_confidences.append(float(avg_conf))
                except Exception as exc:
                    result["pipeline"] = {"status": "error", "message": str(exc)}
            else:
                result["pipeline"] = {
                    "status": "skipped",
                    "message": "Missing ANTHROPIC_API_KEY; pipeline benchmark not executed.",
                }

        if expectations:
            comparison = _compare_expectations(result, expectations.get(path.name))
            if comparison:
                result["expectation_check"] = comparison
                if isinstance(comparison.get("judged_questions"), int) and comparison["judged_questions"] > 0:
                    expected_accuracy_rows += comparison["judged_questions"]
                    if isinstance(comparison.get("correctness_match_rate"), (int, float)):
                        correctness_rates.append(float(comparison["correctness_match_rate"]))
                    if isinstance(comparison.get("score_match_rate"), (int, float)):
                        score_rates.append(float(comparison["score_match_rate"]))

        assets.append(result)

    summary = {
        "total_assets": len(assets),
        "image_assets": sum(1 for a in assets if a["kind"] == "image"),
        "pdf_assets": sum(1 for a in assets if a["kind"] == "pdf"),
        "frontend_rejected": sum(1 for a in assets if not a["frontend_accepts"]),
        "backend_rejected": sum(1 for a in assets if a["kind"] == "image" and not a["backend_accepts"]),
        "backend_open_failures": sum(
            1
            for a in assets
            if a["kind"] == "image" and a.get("backend_accepts") and not a.get("backend_can_open", False)
        ),
        "pipeline_executed": pipeline_executed,
        "avg_pipeline_seconds": _safe_round(sum(pipeline_times) / len(pipeline_times)) if pipeline_times else None,
        "avg_pipeline_confidence": _safe_round(sum(pipeline_confidences) / len(pipeline_confidences)) if pipeline_confidences else None,
        "accuracy_rows_compared": expected_accuracy_rows,
        "avg_correctness_match_rate": _safe_round(sum(correctness_rates) / len(correctness_rates)) if correctness_rates else None,
        "avg_score_match_rate": _safe_round(sum(score_rates) / len(score_rates)) if score_rates else None,
    }

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_dir": str(input_dir),
        "settings": {
            "run_pipeline": run_pipeline_flag,
            "frontend_image_limit_mb": FRONTEND_IMAGE_LIMIT / 1024 / 1024,
            "backend_image_limit_mb": BACKEND_IMAGE_LIMIT / 1024 / 1024,
            "frontend_pdf_limit_mb": FRONTEND_PDF_LIMIT / 1024 / 1024,
        },
        "summary": summary,
        "assets": assets,
    }


def main() -> None:
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(description="Benchmark test assets for the A-Level 作业助手.")
    parser.add_argument("--input-dir", default="test", help="Directory containing benchmark assets.")
    parser.add_argument("--run-pipeline", action="store_true", help="Run the full grading pipeline on image assets.")
    parser.add_argument("--expectations", help="Optional JSON file with expected outputs for accuracy comparison.")
    parser.add_argument("--output", help="Optional path to save the JSON report.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    expectations: dict[str, Any] | None = None
    if args.expectations:
        expectations = json.loads(Path(args.expectations).read_text(encoding="utf-8"))

    report = build_report(input_dir, args.run_pipeline, expectations)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"[done] benchmark report written to {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
