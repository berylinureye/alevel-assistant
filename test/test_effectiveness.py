from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.effectiveness import compute_upload_corpus_effectiveness, latest_run_records_from_ai_events
from scripts.evaluate_upload_corpus import (
    _compact_track_meta,
    _consume_sse_blocks,
    _image_analyze_form_data,
    _phase_timings_from_event_timings,
    _summary_from_events,
    discover_assets,
)
from scripts.build_jpeg_benchmark_corpus import build_jpeg_corpus


def _question(
    number: str,
    *,
    is_correct: bool = True,
    score: float = 4,
    full_score: float = 4,
) -> dict:
    return {
        "question_number": number,
        "is_correct": is_correct,
        "score": score,
        "full_score": full_score,
        "unanswered": False,
        "needs_review": False,
    }


def test_upload_corpus_metrics_pass_when_records_meet_thresholds() -> None:
    records = [
        {
            "asset_path": "test/a.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 42_000,
            "first_question_ms": 12_000,
            "question_count": 2,
            "questions": [_question("1"), _question("2", score=3, full_score=4)],
            "recommendation": {
                "mode": "auto",
                "recommendations": [
                    {"question_id": 101, "topic": "quadratics", "paper_num": 1},
                ],
            },
        },
        {
            "asset_path": "test/b.pdf",
            "kind": "pdf",
            "status": "success",
            "elapsed_ms": 70_000,
            "first_question_ms": 18_000,
            "question_count": 1,
            "questions": [_question("1", is_correct=False, score=2, full_score=4)],
            "recommendation": {
                "mode": "ask_first",
                "recommendations": [],
            },
        },
    ]
    expectations = {
        "a.jpg": {
            "questions": {
                "1": {"is_correct": True, "score": 4},
                "2": {"is_correct": True, "score": 3},
            },
            "expected_recommendation_topic": "quadratics",
            "expected_paper_num": 1,
        },
        "b.pdf": {
            "questions": {
                "1": {"is_correct": False, "score": 2},
            },
        },
    }

    report = compute_upload_corpus_effectiveness(records, expectations=expectations)

    assert report["overall_status"] == "pass"
    assert report["overall_score"] >= 90
    assert report["metrics"]["upload_success_rate"]["status"] == "pass"
    assert report["metrics"]["parse_success_rate"]["status"] == "pass"
    assert report["metrics"]["expected_question_recall_rate"]["status"] == "pass"
    assert report["metrics"]["marked_correctness_match_rate"]["status"] == "pass"
    assert report["metrics"]["recommendation_relevance_rate"]["status"] == "pass"
    assert report["metrics"]["recommendation_real_hit_rate"]["status"] == "pass"


def test_sse_summary_parser_ignores_done_event() -> None:
    summary = {
        "total_questions": 2,
        "knowledge_tags_summary": {"transformations": 1},
        "priority_topics": [{"topic": "transformations"}],
    }

    assert _summary_from_events([("summary", summary), ("done", {})]) == summary


def test_labeled_quality_counts_missing_expected_questions_as_failures() -> None:
    records = [
        {
            "asset_path": "test/missing.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 20_000,
            "first_question_ms": 8_000,
            "question_count": 1,
            "questions": [_question("1", is_correct=True, score=2, full_score=2)],
            "recommendation": {"mode": "none", "recommendations": []},
        }
    ]
    expectations = {
        "missing.jpg": {
            "questions": {
                "1": {"is_correct": True, "score": 2},
                "2": {"is_correct": False, "score": 0},
            }
        }
    }

    report = compute_upload_corpus_effectiveness(records, expectations=expectations)

    assert report["metrics"]["expected_question_recall_rate"]["value"] == 0.5
    assert report["metrics"]["expected_question_recall_rate"]["status"] == "fail"
    assert report["metrics"]["marked_correctness_match_rate"]["value"] == 0.5
    assert report["metrics"]["marked_score_match_rate"]["value"] == 0.5
    assert report["overall_status"] == "fail"


def test_labeled_quality_normalizes_common_question_number_variants() -> None:
    records = [
        {
            "asset_path": "test/variant.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 20_000,
            "first_question_ms": 8_000,
            "question_count": 1,
            "questions": [_question("11(a)", is_correct=True, score=5, full_score=5)],
            "recommendation": {"mode": "none", "recommendations": []},
        }
    ]
    expectations = {
        "variant.jpg": {
            "questions": {
                "11a": {"is_correct": True, "score": 5},
            }
        }
    }

    report = compute_upload_corpus_effectiveness(records, expectations=expectations)

    assert report["metrics"]["expected_question_recall_rate"]["value"] == 1.0
    assert report["metrics"]["marked_correctness_match_rate"]["value"] == 1.0
    assert report["metrics"]["marked_score_match_rate"]["value"] == 1.0


def test_labeled_quality_checks_expected_question_order() -> None:
    records = [
        {
            "asset_path": "test/order.pdf",
            "kind": "pdf",
            "status": "success",
            "elapsed_ms": 20_000,
            "first_question_ms": 1_000,
            "question_count": 3,
            "questions": [
                _question("1(a)", is_correct=False, score=0, full_score=2),
                _question("2", is_correct=False, score=0, full_score=5),
                _question("1(b)", is_correct=False, score=0, full_score=2),
            ],
            "recommendation": {"mode": "none", "recommendations": []},
        }
    ]
    expectations = {
        "order.pdf": {
            "expected_question_order": ["1(a)", "1(b)", "2"],
        }
    }

    report = compute_upload_corpus_effectiveness(records, expectations=expectations)

    assert report["metrics"]["expected_question_order_rate"]["value"] == 0.0
    assert report["metrics"]["expected_question_order_rate"]["status"] == "fail"
    assert report["overall_status"] == "fail"


def test_recommendation_relevance_accepts_ask_first_detected_topic() -> None:
    records = [
        {
            "asset_path": "test/ask-first.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 20_000,
            "first_question_ms": 8_000,
            "question_count": 1,
            "questions": [_question("1", is_correct=True, score=1, full_score=1)],
            "recommendation": {
                "mode": "ask_first",
                "detected_topic": "transformations",
                "recommendations": [],
            },
        }
    ]
    expectations = {
        "ask-first.jpg": {
            "expected_recommendation_topic": "transformations",
        }
    }

    report = compute_upload_corpus_effectiveness(records, expectations=expectations)

    assert report["metrics"]["recommendation_relevance_rate"]["value"] == 1.0
    assert report["metrics"]["recommendation_relevance_rate"]["status"] == "pass"


def test_recommendation_relevance_accepts_topic_alias_group() -> None:
    records = [
        {
            "asset_path": "test/statistics.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 20_000,
            "first_question_ms": 8_000,
            "question_count": 1,
            "questions": [_question("11(ii)", is_correct=True, score=4, full_score=4)],
            "recommendation": {
                "mode": "ask_first",
                "detected_topic": "summary_statistics",
                "recommendations": [],
            },
        }
    ]
    expectations = {
        "statistics.jpg": {
            "expected_recommendation_topic": "combined_mean",
        }
    }

    report = compute_upload_corpus_effectiveness(records, expectations=expectations)

    assert report["metrics"]["recommendation_relevance_rate"]["value"] == 1.0
    assert report["metrics"]["recommendation_relevance_rate"]["status"] == "pass"


def test_recommendation_relevance_accepts_broad_detector_aliases() -> None:
    records = [
        {
            "asset_path": "test/sigma.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 20_000,
            "first_question_ms": 8_000,
            "question_count": 1,
            "questions": [_question("11(ii)", is_correct=True, score=4, full_score=4)],
            "recommendation": {
                "mode": "ask_first",
                "detected_topic": "sigma_notation",
                "recommendations": [],
            },
        },
        {
            "asset_path": "test/transformations.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 20_000,
            "first_question_ms": 8_000,
            "question_count": 1,
            "questions": [_question("11(b)", is_correct=True, score=2, full_score=2)],
            "recommendation": {
                "mode": "ask_first",
                "detected_topic": "algebraic_manipulation",
                "recommendations": [],
            },
        },
    ]
    expectations = {
        "sigma.jpg": {"expected_recommendation_topic": "combined_mean"},
        "transformations.jpg": {"expected_recommendation_topic": "transformations"},
    }

    report = compute_upload_corpus_effectiveness(records, expectations=expectations)

    assert report["metrics"]["recommendation_relevance_rate"]["value"] == 1.0
    assert report["metrics"]["recommendation_relevance_rate"]["status"] == "pass"


def test_consume_sse_blocks_records_first_question_time_once() -> None:
    calls = iter([100.25, 100.5, 100.75])
    events, first_question_ms = _consume_sse_blocks(
        [
            'event: segmentation\ndata: {"question_count": 1}\n\n'
            'event: question\ndata: {"question_number": "1"}',
            '\n\n',
            'event: question\ndata: {"question_number": "2"}\n\n',
        ],
        started=100.0,
        now=lambda: next(calls),
    )

    assert [name for name, _payload in events] == ["segmentation", "question", "question"]
    assert first_question_ms == 500


def test_consume_sse_blocks_records_phase_event_timings() -> None:
    calls = iter([200.10, 200.40, 200.90, 201.20])
    events, first_question_ms, event_timings = _consume_sse_blocks(
        [
            'event: ready\ndata: {}\n\n',
            'event: segmentation\ndata: {"question_count": 2}\n\n',
            'event: question\ndata: {"question_number": "1"}\n\n',
            'event: summary\ndata: {"total_questions": 2}\n\n',
        ],
        started=200.0,
        now=lambda: next(calls),
        include_event_timings=True,
    )

    phase_timings = _phase_timings_from_event_timings(event_timings)

    assert [name for name, _payload in events] == ["ready", "segmentation", "question", "summary"]
    assert first_question_ms == 900
    assert event_timings == {
        "first_event_ms": 99,
        "segmentation_ms": 400,
        "first_question_ms": 900,
        "summary_ms": 1199,
    }
    assert phase_timings == {
        "sse_first_event_ms": 99,
        "segmentation_done_ms": 400,
        "first_question_ms": 900,
        "first_grading_after_segmentation_ms": 500,
        "summary_after_first_question_ms": 299,
    }


def test_image_upload_corpus_uses_product_fast_first_path() -> None:
    data = _image_analyze_form_data()

    assert data["fast_batch"] == "true"
    assert data["review_mode"] == "auto"
    assert data["upload_intent"] == "unknown"


def test_unlabeled_quality_metrics_do_not_lower_overall_score() -> None:
    records = [
        {
            "asset_path": "test/unlabeled.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 30_000,
            "first_question_ms": 8_000,
            "question_count": 1,
            "questions": [_question("1", is_correct=False, score=1, full_score=4)],
            "recommendation": {"mode": "none", "recommendations": []},
        }
    ]

    report = compute_upload_corpus_effectiveness(records, expectations={})

    assert report["metrics"]["marked_correctness_match_rate"]["status"] == "unlabeled"
    assert report["metrics"]["recommendation_relevance_rate"]["status"] == "unlabeled"
    assert report["overall_status"] == "pass"
    assert report["overall_score"] >= 90


def test_phase_timing_metrics_are_reported_as_diagnostics() -> None:
    records = [
        {
            "asset_path": "test/timing.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 24_000,
            "first_question_ms": 9_000,
            "phase_timings": {
                "sse_first_event_ms": 120,
                "segmentation_done_ms": 5_000,
                "first_grading_after_segmentation_ms": 4_000,
                "summary_after_first_question_ms": 2_000,
            },
            "question_count": 1,
            "questions": [_question("1")],
            "recommendation": {"mode": "none", "recommendations": []},
        }
    ]

    report = compute_upload_corpus_effectiveness(records, expectations={})

    assert report["metrics"]["sse_first_event_p95_ms"]["value"] == 120
    assert report["metrics"]["segmentation_done_p95_ms"]["value"] == 5_000
    assert report["metrics"]["first_grading_after_segmentation_p95_ms"]["value"] == 4_000
    assert report["metrics"]["summary_after_first_question_p95_ms"]["value"] == 2_000
    assert report["metrics"]["segmentation_done_p95_ms"]["weight"] == 0
    assert report["overall_status"] == "pass"


def test_repeat_stability_fails_when_same_asset_varies_too_much() -> None:
    records = [
        {
            "asset_path": "test/flaky.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 30_000,
            "first_question_ms": 8_000,
            "question_count": 2,
            "questions": [_question("1"), _question("2")],
            "recommendation": {"mode": "auto", "recommendations": [{"question_id": 1}]},
        },
        {
            "asset_path": "test/flaky.jpg",
            "kind": "image",
            "status": "success",
            "elapsed_ms": 31_000,
            "first_question_ms": 8_500,
            "question_count": 5,
            "questions": [_question(str(i)) for i in range(1, 6)],
            "recommendation": {"mode": "none", "recommendations": []},
        },
    ]

    report = compute_upload_corpus_effectiveness(records, expectations={})

    assert report["metrics"]["repeat_question_count_stability"]["status"] == "fail"
    assert report["metrics"]["repeat_recommendation_mode_stability"]["status"] == "fail"
    assert report["overall_status"] == "fail"


def test_ten_image_batch_metric_uses_one_minute_target() -> None:
    records = [
        {
            "asset_path": "batch:test",
            "kind": "image_batch",
            "batch_size": 10,
            "status": "success",
            "elapsed_ms": 59_000,
            "first_question_ms": 18_000,
            "question_count": 10,
            "questions": [_question(str(i)) for i in range(1, 11)],
            "recommendation": {"mode": "auto", "recommendations": [{"question_id": 101}]},
        }
    ]

    report = compute_upload_corpus_effectiveness(records, expectations={})

    assert report["metrics"]["ten_image_batch_p95_ms"]["value"] == 59_000
    assert report["metrics"]["ten_image_batch_p95_ms"]["target"] == 60_000
    assert report["metrics"]["ten_image_batch_p95_ms"]["status"] == "pass"


def test_unreadable_fallback_questions_do_not_count_as_parse_success() -> None:
    records = [
        {
            "asset_path": "batch:test",
            "kind": "image_batch_prepared",
            "batch_size": 10,
            "status": "success",
            "elapsed_ms": 23_000,
            "first_question_ms": 2_000,
            "question_count": 10,
            "questions": [
                {
                    "question_number": str(i),
                    "is_correct": False,
                    "score": 0,
                    "full_score": 0,
                    "needs_review": True,
                    "error_type": "unreadable",
                }
                for i in range(10)
            ],
            "recommendation": {"mode": "none", "recommendations": []},
        }
    ]

    report = compute_upload_corpus_effectiveness(records, expectations={})

    assert report["metrics"]["upload_success_rate"]["status"] == "pass"
    assert report["metrics"]["parse_success_rate"]["status"] == "fail"
    assert report["metrics"]["readable_question_rate"]["value"] == 0.0
    assert report["metrics"]["readable_question_rate"]["status"] == "fail"
    assert report["overall_status"] == "fail"


def test_timeout_and_unreadable_counts_are_hard_gates() -> None:
    records = [
        {
            "asset_path": "batch:test",
            "kind": "image_batch_prepared",
            "batch_size": 10,
            "status": "success",
            "elapsed_ms": 55_000,
            "first_question_ms": 20_000,
            "question_count": 3,
            "questions": [
                _question("1"),
                {**_question("2", is_correct=False, score=0), "error_type": "fast_batch_timeout"},
                {**_question("3", is_correct=False, score=0), "error_type": "recognition_timeout"},
            ],
            "recommendation": {"mode": "none", "recommendations": []},
        }
    ]

    report = compute_upload_corpus_effectiveness(records, expectations={})

    assert report["metrics"]["fast_batch_timeout_count"]["value"] == 1
    assert report["metrics"]["fast_batch_timeout_count"]["target"] == 0
    assert report["metrics"]["fast_batch_timeout_count"]["status"] == "fail"
    assert report["metrics"]["recognition_timeout_count"]["value"] == 1
    assert report["metrics"]["recognition_timeout_count"]["status"] == "fail"
    assert report["overall_status"] == "fail"


def test_discover_assets_finds_uploadable_images_and_pdfs(tmp_path: Path) -> None:
    for name in ["a.jpg", "b.JPEG", "c.HEIC", "d.pdf", "ignore.txt"]:
        (tmp_path / name).write_bytes(b"x")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "e.webp").write_bytes(b"x")

    assets = discover_assets(tmp_path)

    assert [asset.path.name for asset in assets] == ["a.jpg", "b.JPEG", "c.HEIC", "d.pdf", "e.webp"]
    assert [asset.kind for asset in assets] == ["image", "image", "image", "pdf", "image"]


def test_build_jpeg_corpus_creates_manifest_and_expected_categories(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (800, 1000), "white")
    draw = ImageDraw.Draw(image)
    draw.text((80, 80), "1  Solve x^2 - 5x + 6 = 0", fill="black")
    draw.text((80, 150), "Student: x = 2 or 3", fill="black")
    image.save(source, quality=92)

    manifest = build_jpeg_corpus(
        sources=[source],
        output_dir=tmp_path / "corpus",
        count=10,
    )

    categories = {item["category"] for item in manifest["items"]}

    assert manifest["count"] == 10
    assert len(manifest["items"]) == 10
    assert {"normal", "low_clarity", "tilted_shadow", "cross_page", "blank_edge"}.issubset(categories)
    assert (tmp_path / "corpus" / "manifest.json").exists()
    for item in manifest["items"]:
        assert item["filename"].endswith(".jpg")
        assert (tmp_path / "corpus" / item["filename"]).exists()


def test_latest_run_records_ignore_older_setup_attempts() -> None:
    events = [
        {
            "event_type": "ui_upload_corpus_asset_result",
            "meta": {"asset_path": "old.jpg", "status": "error"},
        },
        {
            "event_type": "ui_upload_corpus_asset_result",
            "meta": {"run_id": "20260624_120000", "asset_path": "first.jpg", "status": "success"},
        },
        {
            "event_type": "ui_upload_corpus_asset_result",
            "meta": {"run_id": "20260624_130000", "asset_path": "latest.jpg", "status": "success"},
        },
    ]

    records = latest_run_records_from_ai_events(events)

    assert records == [{"run_id": "20260624_130000", "asset_path": "latest.jpg", "status": "success"}]


def test_track_meta_is_compact_but_keeps_effectiveness_fields() -> None:
    result = {
        "run_id": "20260625_001709",
        "asset_path": "prepared-batch:" + ",".join(f"/tmp/page_{i}.jpg" for i in range(10)),
        "filename": "prepared_batch_10_images",
        "filenames": [f"page_{i}.jpg" for i in range(10)],
        "kind": "image_batch_prepared",
        "batch_size": 10,
        "status": "success",
        "elapsed_ms": 41_774,
        "first_question_ms": 3_797,
        "question_count": 40,
        "questions": [
            {
                "question_number": str(i),
                "is_correct": i % 2 == 0,
                "score": 1,
                "full_score": 2,
                "needs_review": False,
                "knowledge_tags": [f"very-long-topic-{j}" for j in range(20)],
            }
            for i in range(40)
        ],
        "recommendation": {
            "mode": "auto",
            "recommendations": [
                {"question_id": i, "topic": "quadratics", "subtopic": "factorising", "paper_num": 1}
                for i in range(20)
            ],
        },
    }

    meta = _compact_track_meta(result)

    assert len(json.dumps(meta, ensure_ascii=False)) <= 4096
    assert meta["run_id"] == "20260625_001709"
    assert meta["kind"] == "image_batch_prepared"
    assert meta["batch_size"] == 10
    assert meta["elapsed_ms"] == 41_774
    assert meta["first_question_ms"] == 3_797
    assert meta["question_count"] == 40
