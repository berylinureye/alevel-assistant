from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import pipeline as pipeline_module
from pipeline.pipeline import run_pipeline_streaming
from models.schemas import GradeResult, QuestionType
from router.models import ModelRole


class _FakeClient:
    role = ModelRole.base
    model_id = "fake"
    provider = "test"

    def supports_images(self) -> bool:
        return True

    def call(self, request):
        return "[]"


def _fake_registry() -> dict:
    client = _FakeClient()
    return {
        ModelRole.base: client,
        ModelRole.review: client,
        ModelRole.vision: client,
    }


def _disable_grading_agents(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_module, "build_grading_agents", lambda: None)
    monkeypatch.setattr(pipeline_module, "_build_solution_client", lambda *_args: None)
    monkeypatch.setattr(pipeline_module, "_build_aggregator_client", lambda *_args: None)


def test_streaming_question_extracted_event_clips_long_question_text(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)
    long_question_text = "Find x. " + ("very long printed context " * 80)

    events = run_pipeline_streaming(
        "unused.jpg",
        grade=False,
        registry=_fake_registry(),
        prepared_extracted=[
            {
                "question_number": "1",
                "bbox": [0, 0, 10, 10],
                "question_text": long_question_text,
                "parent_stem": "",
                "student_answer": "",
                "working_steps": [],
                "marks": 2,
                "page": 1,
                "image_quality": "good",
                "confidence": 0.9,
            }
        ],
    )

    assert next(events)[0] == "segmentation"
    event_type, payload = next(events)

    assert event_type == "question_extracted"
    assert len(payload["question_text"]) <= 523
    assert payload["question_text"].endswith("...")


def test_streaming_segmentation_timeout_yields_fallback_quickly(
    tmp_path,
    monkeypatch,
) -> None:
    _disable_grading_agents(monkeypatch)
    image_path = tmp_path / "page.jpg"
    Image.new("RGB", (80, 60), "white").save(image_path)

    def slow_segment(*_args, **_kwargs):
        time.sleep(0.2)
        return [
            {
                "question_number": "late",
                "bbox": [0, 0, 80, 60],
                "question_text": "Late result",
                "student_answer": "",
                "working_steps": [],
                "image_quality": "good",
                "confidence": 0.9,
            }
        ]

    monkeypatch.setattr(pipeline_module, "_segment_with_grouping", slow_segment)

    started = time.monotonic()
    events = run_pipeline_streaming(
        str(image_path),
        grade=False,
        registry=_fake_registry(),
        recognition_timeout_seconds=0.01,
    )
    event_type, payload = next(events)
    elapsed = time.monotonic() - started

    assert event_type == "segmentation"
    assert elapsed < 0.15
    assert payload["recognition_timed_out"] is True
    assert payload["question_count"] == 1


def test_fast_batch_question_timeout_yields_review_result_quickly(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)
    monkeypatch.setattr(pipeline_module, "FAST_BATCH_QUESTION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(pipeline_module, "FAST_BATCH_TIMEOUT_GRACE_SECONDS", 0)

    def slow_question(*_args, **_kwargs):
        time.sleep(0.2)
        return {
            "record": {
                "question_number": "late",
                "bbox": [],
                "question_text": "",
                "student_answer": "",
                "working_steps": [],
                "image_quality": "good",
                "confidence": 0.9,
                "grading": {
                    "question_number": "late",
                    "is_correct": True,
                    "score": 1,
                    "full_score": 1,
                    "error_type": "correct",
                    "knowledge_tags": [],
                    "needs_review": False,
                    "short_feedback": "late",
                    "grading_confidence": 1,
                    "used_model": "fake",
                    "syllabus_topics": [],
                    "relevant_formulas": [],
                },
                "feedback": {
                    "question_number": "late",
                    "student_feedback": "late",
                    "teacher_feedback": "late",
                },
            },
            "grade": None,
        }

    monkeypatch.setattr(pipeline_module, "_process_one_question", slow_question)

    started = time.monotonic()
    events = list(
        run_pipeline_streaming(
            "unused.jpg",
            grade=True,
            registry=_fake_registry(),
            prepared_extracted=[
                {
                    "question_number": "1",
                    "bbox": [0, 0, 10, 10],
                    "question_text": "Find x.",
                    "parent_stem": "",
                    "student_answer": "x = 2",
                    "working_steps": [],
                    "marks": 2,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.9,
                }
            ],
            fast_batch=True,
        )
    )
    elapsed = time.monotonic() - started

    question_events = [payload for event_type, payload in events if event_type == "question"]
    assert elapsed < 0.15
    assert len(question_events) == 1
    assert question_events[0]["needs_review"] is True
    assert question_events[0]["error_type"] == "fast_batch_timeout"


def test_fast_batch_grace_drains_near_timeout_question_result(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)
    monkeypatch.setattr(pipeline_module, "FAST_BATCH_QUESTION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(pipeline_module, "FAST_BATCH_TIMEOUT_GRACE_SECONDS", 0.2)

    def near_timeout_question(*_args, **_kwargs):
        time.sleep(0.05)
        return {
            "record": {
                "question_number": "near",
                "bbox": [],
                "question_text": "",
                "student_answer": "",
                "working_steps": [],
                "image_quality": "good",
                "confidence": 0.9,
                "grading": {
                    "question_number": "near",
                    "is_correct": True,
                    "score": 1,
                    "full_score": 1,
                    "error_type": "correct",
                    "knowledge_tags": [],
                    "needs_review": False,
                    "short_feedback": "ok",
                    "grading_confidence": 1,
                    "used_model": "fake",
                    "syllabus_topics": [],
                    "relevant_formulas": [],
                },
                "feedback": {
                    "question_number": "near",
                    "student_feedback": "ok",
                    "teacher_feedback": "ok",
                },
            },
            "grade": None,
        }

    monkeypatch.setattr(pipeline_module, "_process_one_question", near_timeout_question)

    started = time.monotonic()
    events = list(
        run_pipeline_streaming(
            "unused.jpg",
            grade=True,
            registry=_fake_registry(),
            prepared_extracted=[
                {
                    "question_number": "near",
                    "bbox": [0, 0, 10, 10],
                    "question_text": "Find x.",
                    "parent_stem": "",
                    "student_answer": "x = 2",
                    "working_steps": [],
                    "marks": 1,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.9,
                }
            ],
            fast_batch=True,
        )
    )
    elapsed = time.monotonic() - started

    question_events = [payload for event_type, payload in events if event_type == "question"]
    assert elapsed < 0.15
    assert len(question_events) == 1
    assert question_events[0]["needs_review"] is False
    assert question_events[0]["error_type"] == "correct"


def test_high_confidence_correct_grade_suppresses_segmenter_review_flag(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)

    def trusted_grade(*_args, **_kwargs):
        return GradeResult(
            question_number="11(ii)",
            question_type=QuestionType.statistics,
            is_correct=True,
            score=4,
            full_score=4,
            error_type="correct",
            knowledge_tags=["statistics"],
            needs_review=False,
            short_feedback="答案正确，已通过独立统计公式校验。",
            grading_confidence=0.98,
            correct_answer="$16.0198$",
            syllabus_topics=[],
            relevant_formulas=[],
            student_feedback="答案正确。",
            teacher_feedback="统计数值校验确认学生作答正确。",
        )

    monkeypatch.setattr(pipeline_module, "grade_question", trusted_grade)

    events = list(
        run_pipeline_streaming(
            "unused.jpg",
            grade=True,
            registry=_fake_registry(),
            prepared_extracted=[
                {
                    "question_number": "11(ii)",
                    "bbox": [0, 0, 10, 10],
                    "question_text": "Find the standard deviation.",
                    "parent_stem": "",
                    "student_answer": "16.20",
                    "working_steps": ["~ 16.020"],
                    "marks": 4,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.7,
                    "needs_review": True,
                    "review_reason": "answer numbers not traceable: ['16.20']",
                }
            ],
            fast_batch=True,
        )
    )

    question_events = [payload for event_type, payload in events if event_type == "question"]
    summary_events = [payload for event_type, payload in events if event_type == "summary"]
    assert question_events[0]["is_correct"] is True
    assert question_events[0]["needs_review"] is False
    assert question_events[0]["routing_info"]["escalated"] is False
    assert summary_events[-1]["review_count"] == 0
    assert summary_events[-1]["overall_teacher_comment"] == "本页题目均已判对，无需复核。"


def test_fast_batch_after_first_question_window_times_out_pending_questions(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)
    monkeypatch.setattr(pipeline_module, "FAST_BATCH_QUESTION_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(pipeline_module, "FAST_BATCH_AFTER_FIRST_QUESTION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(pipeline_module, "FAST_BATCH_TIMEOUT_GRACE_SECONDS", 0)

    def fake_process(ext, *_args, **_kwargs):
        if ext["question_number"] == "slow":
            time.sleep(0.2)
        return {
            "record": {
                "question_number": ext["question_number"],
                "bbox": [],
                "question_text": ext.get("question_text", ""),
                "student_answer": ext.get("student_answer", ""),
                "working_steps": [],
                "image_quality": "good",
                "confidence": 0.9,
                "grading": {
                    "question_number": ext["question_number"],
                    "is_correct": True,
                    "score": 1,
                    "full_score": 1,
                    "error_type": "correct",
                    "knowledge_tags": [],
                    "needs_review": False,
                    "short_feedback": "ok",
                    "grading_confidence": 1,
                    "used_model": "fake",
                    "syllabus_topics": [],
                    "relevant_formulas": [],
                },
                "feedback": {
                    "question_number": ext["question_number"],
                    "student_feedback": "ok",
                    "teacher_feedback": "ok",
                },
            },
            "grade": None,
        }

    monkeypatch.setattr(pipeline_module, "_process_one_question", fake_process)

    started = time.monotonic()
    events = list(
        run_pipeline_streaming(
            "unused.jpg",
            grade=True,
            registry=_fake_registry(),
            prepared_extracted=[
                {
                    "question_number": "fast",
                    "bbox": [0, 0, 10, 10],
                    "question_text": "Fast.",
                    "parent_stem": "",
                    "student_answer": "x = 1",
                    "working_steps": [],
                    "marks": 1,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.9,
                },
                {
                    "question_number": "slow",
                    "bbox": [0, 0, 10, 10],
                    "question_text": "Slow.",
                    "parent_stem": "",
                    "student_answer": "x = 2",
                    "working_steps": [],
                    "marks": 1,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.9,
                },
            ],
            fast_batch=True,
        )
    )
    elapsed = time.monotonic() - started

    question_events = [payload for event_type, payload in events if event_type == "question"]
    by_number = {payload["question_number"]: payload for payload in question_events}
    assert elapsed < 0.15
    assert by_number["fast"]["error_type"] == "correct"
    assert by_number["slow"]["needs_review"] is True
    assert by_number["slow"]["error_type"] == "fast_batch_timeout"


def test_recognition_timeout_fallback_item_is_not_dropped_by_cleanup() -> None:
    from pipeline.segmenter import _drop_empty_fallback_items

    items = [
        {
            "question_number": "1",
            "question_text": "",
            "student_answer": "",
            "working_steps": [],
            "recognition_timeout": True,
        },
        {
            "question_number": "2",
            "question_text": "Find x.",
            "student_answer": "x=1",
            "working_steps": [],
        },
    ]

    _drop_empty_fallback_items(items)

    assert [item["question_number"] for item in items] == ["1", "2"]
    assert items[0]["recognition_timeout"] is True


def test_recognition_timeout_yields_explicit_error_type_quickly(
    tmp_path,
    monkeypatch,
) -> None:
    _disable_grading_agents(monkeypatch)
    image_path = tmp_path / "page.jpg"
    Image.new("RGB", (80, 60), "white").save(image_path)

    def slow_segment(*_args, **_kwargs):
        time.sleep(0.2)
        return []

    monkeypatch.setattr(pipeline_module, "_segment_with_grouping", slow_segment)

    events = list(
        run_pipeline_streaming(
            str(image_path),
            grade=True,
            registry=_fake_registry(),
            recognition_timeout_seconds=0.01,
        )
    )

    question_events = [payload for event_type, payload in events if event_type == "question"]
    assert len(question_events) == 1
    assert question_events[0]["error_type"] == "recognition_timeout"
    assert question_events[0]["needs_review"] is True


def test_non_fast_streaming_preserves_question_order(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)

    def fake_process(ext, *_args, **_kwargs):
        if ext["question_number"] == "1":
            time.sleep(0.05)
        return {
            "record": {
                "question_number": ext["question_number"],
                "bbox": ext.get("bbox", []),
                "question_text": ext.get("question_text", ""),
                "student_answer": ext.get("student_answer", ""),
                "working_steps": [],
                "image_quality": "good",
                "confidence": 0.9,
                "grading": {
                    "question_number": ext["question_number"],
                    "is_correct": True,
                    "score": 1,
                    "full_score": 1,
                    "error_type": "correct",
                    "knowledge_tags": [],
                    "needs_review": False,
                    "short_feedback": "ok",
                    "grading_confidence": 1,
                    "used_model": "fake",
                    "syllabus_topics": [],
                    "relevant_formulas": [],
                },
                "feedback": {
                    "question_number": ext["question_number"],
                    "student_feedback": "ok",
                    "teacher_feedback": "ok",
                },
            },
            "grade": None,
        }

    monkeypatch.setattr(pipeline_module, "_process_one_question", fake_process)

    events = list(
        run_pipeline_streaming(
            "unused.jpg",
            grade=True,
            registry=_fake_registry(),
            prepared_extracted=[
                {
                    "question_number": "1",
                    "bbox": [0, 0, 10, 10],
                    "question_text": "First.",
                    "parent_stem": "",
                    "student_answer": "a",
                    "working_steps": [],
                    "marks": 1,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.9,
                },
                {
                    "question_number": "2",
                    "bbox": [0, 0, 10, 10],
                    "question_text": "Second.",
                    "parent_stem": "",
                    "student_answer": "b",
                    "working_steps": [],
                    "marks": 1,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.9,
                },
            ],
            fast_batch=False,
        )
    )

    question_numbers = [
        payload["question_number"]
        for event_type, payload in events
        if event_type == "question"
    ]
    assert question_numbers == ["1", "2"]


def test_fast_batch_defaults_match_interactive_sla() -> None:
    assert pipeline_module.FAST_BATCH_PREPARE_MAX_WORKERS == 10
    assert pipeline_module.FAST_BATCH_MAX_WORKERS == 16
    assert pipeline_module.FAST_BATCH_IMAGE_MAX_DIMENSION == 1600
    assert pipeline_module.FAST_BATCH_PREPARE_TIMEOUT_SECONDS == 15
    assert pipeline_module.FAST_BATCH_QUESTION_TIMEOUT_SECONDS == 15
    assert pipeline_module.FAST_BATCH_AFTER_FIRST_QUESTION_TIMEOUT_SECONDS == 8
    assert pipeline_module.FAST_BATCH_TIMEOUT_GRACE_SECONDS == 2


def test_fast_batch_uses_individual_page_recognition(monkeypatch, tmp_path) -> None:
    _disable_grading_agents(monkeypatch)
    image_a = tmp_path / "a.jpg"
    image_b = tmp_path / "b.jpg"
    Image.new("RGB", (80, 60), "white").save(image_a)
    Image.new("RGB", (80, 60), "white").save(image_b)
    called = {"individual": False}

    def fail_grouping(*_args, **_kwargs):
        raise AssertionError("fast batch should not use whole-batch recognition")

    def fake_individual(*_args, **_kwargs):
        called["individual"] = True
        return [
            {
                "question_number": "1",
                "bbox": [0, 0, 10, 10],
                "question_text": "Find x.",
                "parent_stem": "",
                "student_answer": "",
                "working_steps": [],
                "marks": 2,
                "page": 1,
                "image_quality": "good",
                "confidence": 0.9,
            }
        ]

    monkeypatch.setattr(pipeline_module, "_segment_with_timeout", fail_grouping)
    monkeypatch.setattr(pipeline_module, "_segment_fast_batch_individual", fake_individual)

    events = list(
        run_pipeline_streaming(
            [str(image_a), str(image_b)],
            grade=False,
            registry=_fake_registry(),
            fast_batch=True,
            recognition_timeout_seconds=0.01,
        )
    )

    assert called["individual"] is True
    assert events[0] == ("segmentation", {
        "question_count": 1,
        "questions_preview": ["1"],
        "recognition_timed_out": False,
    })


def test_fast_batch_statistics_shortcut_grades_correct_answer_without_llm(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)

    def fail_grade(*_args, **_kwargs):
        raise AssertionError("statistics shortcut should avoid LLM grading")

    monkeypatch.setattr(pipeline_module, "grade_question", fail_grade)

    events = list(
        run_pipeline_streaming(
            "unused.jpg",
            grade=True,
            registry=_fake_registry(),
            prepared_extracted=[
                {
                    "question_number": "11(ii)",
                    "bbox": [0, 0, 10, 10],
                    "parent_stem": (
                        "The club has 12 Junior members and 20 Senior members. "
                        "For the Junior members, the mean age is 15.5 years and the "
                        "standard deviation is 1.2 years. The Senior members are "
                        "summarised by sum y = 910 and sum y^2 = 42850."
                    ),
                    "question_text": "Find the standard deviation of the ages of all 32 members.",
                    "student_answer": "16.02",
                    "working_steps": ["sqrt((2900.28 + 42850)/32 - 34.25^2) = 16.02"],
                    "marks": 4,
                    "page": 1,
                    "image_quality": "good",
                    "confidence": 0.9,
                }
            ],
            fast_batch=True,
        )
    )

    question_events = [payload for event_type, payload in events if event_type == "question"]
    assert len(question_events) == 1
    assert question_events[0]["is_correct"] is True
    assert question_events[0]["score"] == 4
    assert question_events[0]["routing_info"]["used_model"] == "statistics_verifier"
