from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipeline.pipeline as pipeline
from api.routes import _flatten_question
from api.schemas import FeedbackMode
from models.schemas import GradeResult, QuestionType
from questionbank.mark_scheme import QuestionMarkSchemeContext
from router.models import ModelRole


class DummyClient:
    role = ModelRole.base
    model_id = "dummy"
    provider = "test"

    def supports_images(self) -> bool:
        return False

    def call(self, request):
        raise AssertionError("test should not call a real model")


def test_process_one_question_carries_mark_scheme_context_to_grader(monkeypatch) -> None:
    captured = {}

    def fake_grade_question(question, client, task, base_grade=None, skip_verification=False, q_type=None):
        captured["mark_scheme_context"] = question.mark_scheme_context
        return GradeResult(
            question_number=question.question_number,
            question_type=QuestionType.algebra,
            is_correct=True,
            score=3.0,
            full_score=3.0,
            error_type="correct",
            knowledge_tags=["algebra"],
            needs_review=False,
            short_feedback="做对了。",
            grading_confidence=0.95,
            student_feedback="做对了。",
            teacher_feedback="掌握良好，无需额外关注。",
        )

    monkeypatch.setattr(pipeline, "grade_question", fake_grade_question)

    result = pipeline._process_one_question(
        {
            "question_number": "1",
            "bbox": [0, 0, 10, 10],
            "question_text": "Solve $x+1=2$.",
            "student_answer": "$x=1$",
            "working_steps": ["$x=1$"],
            "marks": 3,
            "image_quality": "good",
            "confidence": 0.99,
            "mark_scheme_context": "Official mark scheme context for Q1: M1 for method.",
        },
        DummyClient(),
        DummyClient(),
        "off",
        True,
        agent_clients=None,
        solution_client=None,
        generate_solution_inline=False,
    )

    assert captured["mark_scheme_context"] == "Official mark scheme context for Q1: M1 for method."
    assert result["record"]["grading"]["used_model"] == "dummy"


def test_attach_mark_scheme_contexts_uses_extracted_question_numbers(monkeypatch) -> None:
    def fake_context_map(*, catalog_match, question_numbers, paper_label=None, root=None):
        assert "1" in question_numbers
        return {
            "1": QuestionMarkSchemeContext(
                question_number="1",
                text="Official mark scheme context for Q1: B1 M1 A1.",
                confidence="high",
                reason="ok",
            )
        }

    monkeypatch.setattr(pipeline, "build_mark_scheme_context_map", fake_context_map)

    extracted = [
        {
            "question_number": "1(a)",
            "question_text": "Solve it.",
            "student_answer": "x=1",
            "working_steps": [],
        }
    ]
    pipeline._attach_mark_scheme_contexts(
        extracted,
        {
            "grading_route": "past_paper_mark_scheme",
            "paper_label": "CIE 9709/12 May/Jun 2016",
            "question_numbers": [],
            "catalog_match": {
                "ms_path": "data/papers/9709/2016/9709_s16_ms_12.pdf",
                "has_ms": True,
            },
        },
    )

    assert extracted[0]["mark_scheme_context"] == "Official mark scheme context for Q1: B1 M1 A1."
    assert extracted[0]["mark_scheme_confidence"] == "high"
    assert extracted[0]["grading_route"] == "past_paper_mark_scheme"


def test_mark_scheme_fallback_metadata_survives_pipeline_and_api_flatteners(monkeypatch) -> None:
    def fake_context_map(*, catalog_match, question_numbers, paper_label=None, root=None):
        return {
            "1": QuestionMarkSchemeContext(
                question_number="1",
                text="",
                confidence="low",
                reason="Could not locate question 1 in the mark scheme text.",
            )
        }

    def fake_grade_question(question, client, task, base_grade=None, skip_verification=False, q_type=None):
        return GradeResult(
            question_number=question.question_number,
            question_type=QuestionType.algebra,
            is_correct=False,
            score=1.0,
            full_score=3.0,
            error_type="unknown",
            knowledge_tags=["algebra"],
            needs_review=True,
            short_feedback="需要复核。",
            grading_confidence=0.4,
            student_feedback="这题需要复核。",
            teacher_feedback="建议老师复核。",
        )

    monkeypatch.setattr(pipeline, "build_mark_scheme_context_map", fake_context_map)
    monkeypatch.setattr(pipeline, "grade_question", fake_grade_question)

    extracted = [
        {
            "question_number": "1",
            "bbox": [0, 0, 10, 10],
            "question_text": "Solve it.",
            "student_answer": "x=1",
            "working_steps": [],
            "marks": 3,
            "image_quality": "good",
            "confidence": 0.99,
        }
    ]
    pipeline._attach_mark_scheme_contexts(
        extracted,
        {
            "grading_route": "past_paper_mark_scheme",
            "paper_label": "CIE 9709/12 May/Jun 2016",
            "question_numbers": ["1"],
            "catalog_match": {"ms_path": "unused", "has_ms": True},
        },
    )

    result = pipeline._process_one_question(
        extracted[0],
        DummyClient(),
        DummyClient(),
        "off",
        True,
        agent_clients=None,
        solution_client=None,
        generate_solution_inline=False,
    )

    record = result["record"]
    assert record["grading_route"] == "open_ai_grading"
    assert record["mark_scheme_context_error"] == "Could not locate question 1 in the mark scheme text."
    assert "mark_scheme:Could not locate question 1" in " ".join(record["grading"]["escalation_reasons"])

    stream_payload = pipeline._flatten_for_stream(record)
    assert stream_payload["grading_route"] == "open_ai_grading"
    assert stream_payload["mark_scheme_context_error"] == "Could not locate question 1 in the mark scheme text."

    api_payload = _flatten_question(record, FeedbackMode.both)
    assert api_payload.grading_route == "open_ai_grading"
    assert api_payload.mark_scheme_context_error == "Could not locate question 1 in the mark scheme text."
