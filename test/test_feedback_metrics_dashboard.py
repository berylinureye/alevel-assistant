from api.feedback import compute_product_metrics


def event(event_type: str, meta=None, duration_ms: int = 0) -> dict:
    return {
        "event_type": event_type,
        "duration_ms": duration_ms,
        "meta": meta or {},
        "created_at": 1,
    }


def test_compute_product_metrics_builds_learning_loop_and_quality_rates() -> None:
    metrics = compute_product_metrics(
        [
            event("ui_page_view"),
            event("ui_file_selected", {"file_count": 2}),
            event("ui_upload_submit"),
            event("upload_received"),
            event("prepare_upload_done", {"status": "ready", "ocr_status": "ready"}, 12_000),
            event("paper_resolution_done", {
                "confidence": "high",
                "route": "past_paper_mark_scheme",
                "match_source": "manual",
            }),
            event("segment_done", {
                "question_count": 2,
                "empty_count": 1,
                "parent_stem_missing_count": 0,
            }),
            event("question_graded", {
                "is_correct": False,
                "score": 2,
                "full_score": 5,
                "grading_confidence": 0.6,
                "needs_review": True,
                "grading_route": "past_paper_mark_scheme",
            }),
            event("ui_result_seen", duration_ms=18_000),
            event("ui_question_expanded"),
            event("ui_practice_recommendation_seen"),
            event("ui_practice_started"),
            event("ui_practice_answer_submitted", {"is_correct": True}),
            event("feedback_quality_sampled", {
                "score_accuracy": 1,
                "explanation_quality": 1,
                "issue_tags": ["deduction_specific"],
            }),
            event("session_done"),
        ],
        [{"id": 1, "rating": 5}],
    )

    assert metrics["north_star"]["value"] == 1.0
    assert metrics["route_mix"]["past_paper_mark_scheme"] == 1
    assert metrics["quality_review"]["score_accuracy_rate"] == 1.0
    assert metrics["quality_review"]["explanation_quality_rate"] == 1.0
    assert metrics["quality_review"]["top_issue_tags"] == [("deduction_specific", 1)]

    node_lookup = {
        (item["node"], item["metric"]): item
        for item in metrics["node_metrics"]
    }
    assert node_lookup[("批改置信度", "低置信触发复核率")]["value"] == 1.0
    assert node_lookup[("结果页", "首题可见 P95 耗时")]["value"] == 18_000
    assert node_lookup[("系统稳定性", "pipeline_error 率")]["value"] == 0.0


def test_compute_product_metrics_marks_missing_rates_as_none() -> None:
    metrics = compute_product_metrics([], [])

    assert metrics["north_star"]["value"] is None
    assert metrics["learning_loop_funnel"][1]["rate_from_previous"] is None
    assert metrics["quality_review"]["sample_count"] == 0
