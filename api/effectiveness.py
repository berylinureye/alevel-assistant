"""Effectiveness metrics for upload-corpus and practice-loop evaluation."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


MetricStatus = str

PASS = "pass"
FAIL = "fail"
UNLABELED = "unlabeled"
INSUFFICIENT = "insufficient_data"

UPLOAD_TARGET = 0.95
PARSE_TARGET = 0.90
READABLE_QUESTION_TARGET = 0.85
MARKED_CORRECTNESS_TARGET = 0.90
MARKED_SCORE_TARGET = 0.85
RECOMMENDATION_RELEVANCE_TARGET = 0.90
RECOMMENDATION_REAL_HIT_TARGET = 1.0
PAPER_COMPLIANCE_TARGET = 1.0
EXPECTED_QUESTION_RECALL_TARGET = 0.95
EXPECTED_QUESTION_ORDER_TARGET = 0.95
QUESTION_COUNT_STABILITY_TARGET = 0.90
RECOMMENDATION_MODE_STABILITY_TARGET = 0.90
IMAGE_P95_TARGET_MS = 60_000
PDF_P95_TARGET_MS = 90_000
FIRST_QUESTION_P95_TARGET_MS = 30_000
BATCH_10_IMAGE_TARGET_MS = 60_000
SSE_FIRST_EVENT_TARGET_MS = 5_000
SEGMENTATION_DONE_TARGET_MS = 20_000
FIRST_GRADING_AFTER_SEGMENTATION_TARGET_MS = 15_000
SUMMARY_AFTER_FIRST_QUESTION_TARGET_MS = 15_000
OVERALL_PASS_SCORE = 90
ZERO_HARD_FAILURE_TARGET = 0

TOPIC_ALIAS_GROUPS = (
    {
        "combined_mean",
        "combined_means",
        "mean",
        "summary_statistics",
        "standard_deviation",
        "variance",
        "sigma_notation",
        "statistics",
        "data_summary",
    },
    {
        "transformations",
        "graph_transformations",
        "inverse_functions",
        "function_transformations",
        "algebraic_manipulation",
        "reflections",
        "translations",
        "stretches",
        "graphs",
    },
)


def _safe_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 4)


def _p95(values: Iterable[int | float | None]) -> int | None:
    clean = sorted(int(v) for v in values if isinstance(v, (int, float)) and v >= 0)
    if not clean:
        return None
    index = min(len(clean) - 1, int(len(clean) * 0.95))
    return clean[index]


def _status_for_rate(value: float | None, target: float, *, empty_status: MetricStatus = INSUFFICIENT) -> MetricStatus:
    if value is None:
        return empty_status
    return PASS if value >= target else FAIL


def _status_for_max(value: int | None, target: int, *, empty_status: MetricStatus = INSUFFICIENT) -> MetricStatus:
    if value is None:
        return empty_status
    return PASS if value <= target else FAIL


def _metric(
    *,
    label: str,
    value: float | int | None,
    target: float | int | None,
    status: MetricStatus,
    sample_size: int,
    unit: str = "rate",
    weight: int = 1,
    hard_gate: bool = False,
) -> dict[str, Any]:
    return {
        "label": label,
        "value": value,
        "target": target,
        "status": status,
        "sample_size": sample_size,
        "unit": unit,
        "weight": weight,
        "hard_gate": hard_gate,
    }


def _asset_key(record: dict[str, Any]) -> str:
    path = str(record.get("asset_path") or record.get("filename") or "")
    return Path(path).name if path else ""


def _normalize_question_number(value: object) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    return "".join(ch for ch in raw if ch.isalnum())


def _questions_by_number(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    questions = record.get("questions")
    if not isinstance(questions, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for question in questions:
        if not isinstance(question, dict):
            continue
        number = str(question.get("question_number") or "").strip()
        if number:
            result[number] = question
            normalized = _normalize_question_number(number)
            if normalized and normalized not in result:
                result[normalized] = question
    return result


def _questions_list(record: dict[str, Any]) -> list[dict[str, Any]]:
    questions = record.get("questions")
    if not isinstance(questions, list):
        return []
    return [question for question in questions if isinstance(question, dict)]


def _question_count(record: dict[str, Any]) -> int:
    questions = _questions_list(record)
    if questions:
        return len(questions)
    return int(record.get("question_count") or 0)


def _readable_question_count(record: dict[str, Any]) -> int:
    questions = _questions_list(record)
    if not questions:
        return int(record.get("question_count") or 0)
    unreadable_errors = {"unreadable", "recognition_timeout"}
    return sum(
        1
        for question in questions
        if str(question.get("error_type") or "").strip().lower() not in unreadable_errors
    )


def _question_error_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        for question in _questions_list(record):
            error_type = str(question.get("error_type") or "").strip().lower()
            if error_type:
                counts[error_type] += 1
            elif question.get("recognition_timeout"):
                counts["recognition_timeout"] += 1
    return dict(counts)


def _phase_timing(record: dict[str, Any], key: str) -> int | None:
    phase_timings = record.get("phase_timings")
    if not isinstance(phase_timings, dict):
        return None
    value = phase_timings.get(key)
    if isinstance(value, (int, float)) and value >= 0:
        return int(value)
    return None


def _hard_count_metric(
    *,
    label: str,
    value: int,
    sample_size: int,
) -> dict[str, Any]:
    return _metric(
        label=label,
        value=value,
        target=ZERO_HARD_FAILURE_TARGET,
        status=(
            _status_for_max(value, ZERO_HARD_FAILURE_TARGET)
            if sample_size > 0
            else INSUFFICIENT
        ),
        sample_size=sample_size,
        unit="count",
        weight=0,
        hard_gate=True,
    )


def _question_score(question: dict[str, Any]) -> float | None:
    return _safe_float(question.get("score"))


def _full_score(question: dict[str, Any]) -> float | None:
    return _safe_float(question.get("full_score"))


def _recommendation(record: dict[str, Any]) -> dict[str, Any]:
    recommendation = record.get("recommendation")
    return recommendation if isinstance(recommendation, dict) else {}


def _recommendation_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    items = _recommendation(record).get("recommendations")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _normalize_topic(value: object) -> str:
    raw = str(value or "").strip().lower()
    return "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")


def _topic_matches(actual: object, expected: str) -> bool:
    actual_topic = _normalize_topic(actual)
    expected_topic = _normalize_topic(expected)
    if not actual_topic or not expected_topic:
        return False
    if actual_topic == expected_topic:
        return True
    for group in TOPIC_ALIAS_GROUPS:
        if actual_topic in group and expected_topic in group:
            return True
    return False


def _matches_topic(item: dict[str, Any], expected_topic: object) -> bool:
    if expected_topic is None:
        return False
    expected = _normalize_topic(expected_topic)
    if not expected:
        return False
    fields = [item.get("topic"), item.get("subtopic")]
    tags = item.get("tags")
    if isinstance(tags, list):
        fields.extend(tags)
    return any(_topic_matches(field, expected) for field in fields)


def _recommendation_matches_topic(record: dict[str, Any], expected_topic: object) -> bool:
    recommendation = _recommendation(record)
    if _matches_topic({"topic": recommendation.get("detected_topic")}, expected_topic):
        return True
    return any(_matches_topic(item, expected_topic) for item in _recommendation_items(record))


def _matches_paper(item: dict[str, Any], expected_paper: object) -> bool:
    expected = _safe_float(expected_paper)
    actual = _safe_float(item.get("paper_num"))
    return expected is not None and actual is not None and int(expected) == int(actual)


def _compute_marked_quality(
    records: list[dict[str, Any]],
    expectations: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    judged_correctness = 0
    matched_correctness = 0
    judged_score = 0
    matched_score = 0
    expected_question_total = 0
    found_questions = 0
    order_judged = 0
    order_matched = 0

    for record in records:
        expected = expectations.get(_asset_key(record))
        if not isinstance(expected, dict):
            continue
        expected_questions_map = expected.get("questions")
        actual_by_number = _questions_by_number(record)

        if isinstance(expected_questions_map, dict):
            for number, expected_question in expected_questions_map.items():
                if not isinstance(expected_question, dict):
                    continue
                expected_question_total += 1
                actual = actual_by_number.get(str(number)) or actual_by_number.get(_normalize_question_number(number))
                if actual:
                    found_questions += 1
                if "is_correct" in expected_question:
                    judged_correctness += 1
                    if actual and bool(actual.get("is_correct")) is bool(expected_question.get("is_correct")):
                        matched_correctness += 1
                if "score" in expected_question:
                    expected_score = _safe_float(expected_question.get("score"))
                    actual_score = _question_score(actual) if actual else None
                    if expected_score is not None:
                        judged_score += 1
                        if actual_score is not None and abs(actual_score - expected_score) < 1e-9:
                            matched_score += 1

        expected_order = expected.get("expected_question_order")
        if isinstance(expected_order, list) and expected_order:
            actual_order = [
                _normalize_question_number(question.get("question_number"))
                for question in _questions_list(record)
            ]
            expected_norm = [_normalize_question_number(number) for number in expected_order]
            expected_norm = [number for number in expected_norm if number]
            if expected_norm:
                order_judged += 1
                actual_positions = [
                    actual_order.index(number)
                    for number in expected_norm
                    if number in actual_order
                ]
                if (
                    len(actual_positions) == len(expected_norm)
                    and actual_positions == sorted(actual_positions)
                ):
                    order_matched += 1

    question_recall_rate = _ratio(found_questions, expected_question_total)
    order_rate = _ratio(order_matched, order_judged)
    correctness_rate = _ratio(matched_correctness, judged_correctness)
    score_rate = _ratio(matched_score, judged_score)
    return (
        _metric(
            label="标注题目召回率",
            value=question_recall_rate,
            target=EXPECTED_QUESTION_RECALL_TARGET,
            status=_status_for_rate(question_recall_rate, EXPECTED_QUESTION_RECALL_TARGET, empty_status=UNLABELED),
            sample_size=expected_question_total,
            weight=3,
        ),
        _metric(
            label="标注题目顺序一致率",
            value=order_rate,
            target=EXPECTED_QUESTION_ORDER_TARGET,
            status=_status_for_rate(order_rate, EXPECTED_QUESTION_ORDER_TARGET, empty_status=UNLABELED),
            sample_size=order_judged,
            weight=3,
        ),
        _metric(
            label="标注正确性一致率",
            value=correctness_rate,
            target=MARKED_CORRECTNESS_TARGET,
            status=_status_for_rate(correctness_rate, MARKED_CORRECTNESS_TARGET, empty_status=UNLABELED),
            sample_size=judged_correctness,
            weight=2,
        ),
        _metric(
            label="标注精确分数一致率",
            value=score_rate,
            target=MARKED_SCORE_TARGET,
            status=_status_for_rate(score_rate, MARKED_SCORE_TARGET, empty_status=UNLABELED),
            sample_size=judged_score,
            weight=2,
        ),
    )


def _compute_recommendation_quality(
    records: list[dict[str, Any]],
    expectations: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    relevant = 0
    relevant_judged = 0
    real_hit = 0
    real_hit_judged = 0
    paper_ok = 0
    paper_judged = 0

    for record in records:
        items = _recommendation_items(record)
        if items:
            real_hit_judged += len(items)
            real_hit += sum(1 for item in items if item.get("question_id") is not None)

        expected = expectations.get(_asset_key(record))
        if not isinstance(expected, dict):
            continue
        expected_topic = expected.get("expected_recommendation_topic")
        expected_paper = expected.get("expected_paper_num")

        if expected_topic is not None:
            relevant_judged += 1
            if _recommendation_matches_topic(record, expected_topic):
                relevant += 1

        if expected_paper is not None and items:
            paper_judged += len(items)
            paper_ok += sum(1 for item in items if _matches_paper(item, expected_paper))

    relevance_rate = _ratio(relevant, relevant_judged)
    real_hit_rate = _ratio(real_hit, real_hit_judged)
    paper_rate = _ratio(paper_ok, paper_judged)
    return (
        _metric(
            label="标注推荐相关性",
            value=relevance_rate,
            target=RECOMMENDATION_RELEVANCE_TARGET,
            status=_status_for_rate(relevance_rate, RECOMMENDATION_RELEVANCE_TARGET, empty_status=UNLABELED),
            sample_size=relevant_judged,
            weight=2,
        ),
        _metric(
            label="推荐真实题库命中率",
            value=real_hit_rate,
            target=RECOMMENDATION_REAL_HIT_TARGET,
            status=_status_for_rate(real_hit_rate, RECOMMENDATION_REAL_HIT_TARGET),
            sample_size=real_hit_judged,
            weight=2,
        ),
        _metric(
            label="Paper 合规率",
            value=paper_rate,
            target=PAPER_COMPLIANCE_TARGET,
            status=_status_for_rate(paper_rate, PAPER_COMPLIANCE_TARGET, empty_status=UNLABELED),
            sample_size=paper_judged,
            weight=2,
        ),
    )


def _compute_stability(records: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = _asset_key(record)
        if key:
            groups[key].append(record)

    question_stable = 0
    question_judged = 0
    mode_stable = 0
    mode_judged = 0

    for same_asset in groups.values():
        if len(same_asset) < 2:
            continue
        question_judged += 1
        counts = [
            int(record.get("question_count") or len(_questions_by_number(record)))
            for record in same_asset
            if record.get("status") == "success"
        ]
        if counts and max(counts) - min(counts) <= 1:
            question_stable += 1

        mode_judged += 1
        modes = [
            str(_recommendation(record).get("mode") or "")
            for record in same_asset
            if record.get("status") == "success"
        ]
        if modes and len(set(modes)) == 1:
            mode_stable += 1

    question_rate = _ratio(question_stable, question_judged)
    mode_rate = _ratio(mode_stable, mode_judged)
    return (
        _metric(
            label="重复运行题目数稳定率",
            value=question_rate,
            target=QUESTION_COUNT_STABILITY_TARGET,
            status=_status_for_rate(question_rate, QUESTION_COUNT_STABILITY_TARGET),
            sample_size=question_judged,
            weight=1,
        ),
        _metric(
            label="重复运行推荐模式稳定率",
            value=mode_rate,
            target=RECOMMENDATION_MODE_STABILITY_TARGET,
            status=_status_for_rate(mode_rate, RECOMMENDATION_MODE_STABILITY_TARGET),
            sample_size=mode_judged,
            weight=1,
        ),
    )


def _score_metrics(metrics: dict[str, dict[str, Any]]) -> tuple[int, MetricStatus]:
    scored = [
        metric
        for metric in metrics.values()
        if metric["status"] not in {UNLABELED, INSUFFICIENT}
        and int(metric.get("weight") if metric.get("weight") is not None else 1) > 0
    ]
    hard_gate_failed = any(
        bool(metric.get("hard_gate")) and metric["status"] == FAIL
        for metric in metrics.values()
    )
    if not scored:
        return 0, FAIL if hard_gate_failed else INSUFFICIENT
    total_weight = sum(int(metric.get("weight") if metric.get("weight") is not None else 1) for metric in scored)
    pass_weight = sum(
        int(metric.get("weight") if metric.get("weight") is not None else 1)
        for metric in scored
        if metric["status"] == PASS
    )
    score = round(pass_weight / total_weight * 100)
    status = PASS if score >= OVERALL_PASS_SCORE else FAIL
    if hard_gate_failed:
        status = FAIL
    return score, status


def compute_upload_corpus_effectiveness(
    records: list[dict[str, Any]],
    *,
    expectations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute thresholded effectiveness metrics for batch upload evaluation.

    Unlabeled quality metrics are reported as ``unlabeled`` and excluded from the
    overall score, so an unannotated corpus can still validate experience and
    system-health gates.
    """
    expectations = expectations or {}
    total = len(records)
    successful = [record for record in records if record.get("status") == "success"]
    parse_successes = [
        record
        for record in successful
        if _readable_question_count(record) > 0
    ]
    total_questions = sum(_question_count(record) for record in successful)
    readable_questions = sum(_readable_question_count(record) for record in successful)
    error_counts = _question_error_counts(successful)
    readable_question_rate = _ratio(readable_questions, total_questions)
    image_p95 = _p95(record.get("elapsed_ms") for record in successful if record.get("kind") == "image")
    pdf_p95 = _p95(record.get("elapsed_ms") for record in successful if record.get("kind") == "pdf")
    batch_10_p95 = _p95(
        record.get("elapsed_ms")
        for record in successful
        if record.get("kind") in {"image_batch", "image_batch_prepared"} and int(record.get("batch_size") or 0) >= 10
    )
    first_question_p95 = _p95(record.get("first_question_ms") for record in successful)
    sse_first_event_p95 = _p95(_phase_timing(record, "sse_first_event_ms") for record in successful)
    segmentation_done_p95 = _p95(_phase_timing(record, "segmentation_done_ms") for record in successful)
    first_grading_after_segmentation_p95 = _p95(
        _phase_timing(record, "first_grading_after_segmentation_ms") for record in successful
    )
    summary_after_first_question_p95 = _p95(
        _phase_timing(record, "summary_after_first_question_ms") for record in successful
    )
    upload_success_rate = _ratio(len(successful), total)
    parse_success_rate = _ratio(len(parse_successes), len(successful))

    question_recall_metric, question_order_metric, correctness_metric, score_metric = _compute_marked_quality(records, expectations)
    relevance_metric, real_hit_metric, paper_metric = _compute_recommendation_quality(records, expectations)
    question_stability_metric, mode_stability_metric = _compute_stability(records)

    metrics = {
        "upload_success_rate": _metric(
            label="上传成功率",
            value=upload_success_rate,
            target=UPLOAD_TARGET,
            status=_status_for_rate(upload_success_rate, UPLOAD_TARGET),
            sample_size=total,
            weight=3,
        ),
        "parse_success_rate": _metric(
            label="可解析率",
            value=parse_success_rate,
            target=PARSE_TARGET,
            status=_status_for_rate(parse_success_rate, PARSE_TARGET),
            sample_size=len(successful),
            weight=3,
        ),
        "readable_question_rate": _metric(
            label="可读题目率",
            value=readable_question_rate,
            target=READABLE_QUESTION_TARGET,
            status=_status_for_rate(readable_question_rate, READABLE_QUESTION_TARGET),
            sample_size=total_questions,
            weight=3,
        ),
        "image_end_to_end_p95_ms": _metric(
            label="图片端到端 P95",
            value=image_p95,
            target=IMAGE_P95_TARGET_MS,
            status=_status_for_max(image_p95, IMAGE_P95_TARGET_MS),
            sample_size=sum(1 for record in successful if record.get("kind") == "image"),
            unit="ms",
            weight=1,
        ),
        "pdf_end_to_end_p95_ms": _metric(
            label="PDF 端到端 P95",
            value=pdf_p95,
            target=PDF_P95_TARGET_MS,
            status=_status_for_max(pdf_p95, PDF_P95_TARGET_MS),
            sample_size=sum(1 for record in successful if record.get("kind") == "pdf"),
            unit="ms",
            weight=1,
        ),
        "first_question_p95_ms": _metric(
            label="首题返回 P95",
            value=first_question_p95,
            target=FIRST_QUESTION_P95_TARGET_MS,
            status=_status_for_max(first_question_p95, FIRST_QUESTION_P95_TARGET_MS),
            sample_size=len(successful),
            unit="ms",
            weight=1,
        ),
        "ten_image_batch_p95_ms": _metric(
            label="10 图一次上传 P95",
            value=batch_10_p95,
            target=BATCH_10_IMAGE_TARGET_MS,
            status=_status_for_max(batch_10_p95, BATCH_10_IMAGE_TARGET_MS),
            sample_size=sum(
                1
                for record in successful
                if record.get("kind") in {"image_batch", "image_batch_prepared"} and int(record.get("batch_size") or 0) >= 10
            ),
            unit="ms",
            weight=3,
        ),
        "sse_first_event_p95_ms": _metric(
            label="SSE 首事件 P95",
            value=sse_first_event_p95,
            target=SSE_FIRST_EVENT_TARGET_MS,
            status=_status_for_max(sse_first_event_p95, SSE_FIRST_EVENT_TARGET_MS),
            sample_size=sum(1 for record in successful if _phase_timing(record, "sse_first_event_ms") is not None),
            unit="ms",
            weight=0,
        ),
        "segmentation_done_p95_ms": _metric(
            label="识别完成 P95",
            value=segmentation_done_p95,
            target=SEGMENTATION_DONE_TARGET_MS,
            status=_status_for_max(segmentation_done_p95, SEGMENTATION_DONE_TARGET_MS),
            sample_size=sum(1 for record in successful if _phase_timing(record, "segmentation_done_ms") is not None),
            unit="ms",
            weight=0,
        ),
        "first_grading_after_segmentation_p95_ms": _metric(
            label="首题批改等待 P95",
            value=first_grading_after_segmentation_p95,
            target=FIRST_GRADING_AFTER_SEGMENTATION_TARGET_MS,
            status=_status_for_max(
                first_grading_after_segmentation_p95,
                FIRST_GRADING_AFTER_SEGMENTATION_TARGET_MS,
            ),
            sample_size=sum(1 for record in successful if _phase_timing(record, "first_grading_after_segmentation_ms") is not None),
            unit="ms",
            weight=0,
        ),
        "summary_after_first_question_p95_ms": _metric(
            label="首题后汇总 P95",
            value=summary_after_first_question_p95,
            target=SUMMARY_AFTER_FIRST_QUESTION_TARGET_MS,
            status=_status_for_max(summary_after_first_question_p95, SUMMARY_AFTER_FIRST_QUESTION_TARGET_MS),
            sample_size=sum(1 for record in successful if _phase_timing(record, "summary_after_first_question_ms") is not None),
            unit="ms",
            weight=0,
        ),
        "recognition_timeout_count": _hard_count_metric(
            label="识别超时题数",
            value=error_counts.get("recognition_timeout", 0),
            sample_size=total_questions,
        ),
        "unreadable_question_count": _hard_count_metric(
            label="不可读题数",
            value=error_counts.get("unreadable", 0),
            sample_size=total_questions,
        ),
        "fast_batch_timeout_count": _hard_count_metric(
            label="快批超时题数",
            value=error_counts.get("fast_batch_timeout", 0),
            sample_size=total_questions,
        ),
        "expected_question_recall_rate": question_recall_metric,
        "expected_question_order_rate": question_order_metric,
        "marked_correctness_match_rate": correctness_metric,
        "marked_score_match_rate": score_metric,
        "recommendation_relevance_rate": relevance_metric,
        "recommendation_real_hit_rate": real_hit_metric,
        "paper_compliance_rate": paper_metric,
        "repeat_question_count_stability": question_stability_metric,
        "repeat_recommendation_mode_stability": mode_stability_metric,
    }

    overall_score, overall_status = _score_metrics(metrics)
    failures = [
        {"metric": key, "label": metric["label"], "value": metric["value"], "target": metric["target"]}
        for key, metric in metrics.items()
        if metric["status"] == FAIL
    ]

    return {
        "overall_score": overall_score,
        "overall_status": overall_status,
        "metrics": metrics,
        "failures": failures,
        "summary": {
            "records": total,
            "successful_records": len(successful),
            "parsed_records": len(parse_successes),
            "asset_count": len({_asset_key(record) for record in records if _asset_key(record)}),
            "question_error_counts": error_counts,
        },
    }


def records_from_ai_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract upload-corpus asset records from ``ai_events`` rows."""
    records: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") not in {"ui_upload_corpus_asset_result", "upload_corpus_asset_result"}:
            continue
        meta = event.get("meta")
        if isinstance(meta, str):
            import json

            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if isinstance(meta, dict):
            records.append(meta)
    return records


def latest_run_records_from_ai_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return records from the latest upload-corpus run when run ids exist.

    Early local experiments may have no ``run_id``. Once the evaluator writes
    run ids, the dashboard should represent the latest run instead of mixing
    failed setup attempts with the current benchmark.
    """
    records = records_from_ai_events(events)
    run_ids = sorted({str(record.get("run_id")) for record in records if record.get("run_id")})
    if not run_ids:
        return records
    latest = run_ids[-1]
    return [record for record in records if str(record.get("run_id")) == latest]
