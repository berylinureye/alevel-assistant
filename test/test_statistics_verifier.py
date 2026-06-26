from __future__ import annotations

import json

from grader.grader import grade_question
from models.schemas import QuestionData, QuestionType
from router.models import ModelRequest, ModelRole, TaskType
from verifier.statistics_verifier import verify_statistics


class FailingClient:
    role = ModelRole.base
    model_id = "failing"
    provider = "test"

    def supports_images(self) -> bool:
        return False

    def call(self, request):
        raise RuntimeError("没有可用token")


class CountingClient:
    role = ModelRole.base
    model_id = "counting"
    provider = "test"

    def __init__(self) -> None:
        self.calls = 0

    def supports_images(self) -> bool:
        return False

    def call(self, request: ModelRequest):
        self.calls += 1
        return "{}"


class WrongStatsGradeClient:
    role = ModelRole.base
    model_id = "wrong-stats"
    provider = "test"

    def __init__(self) -> None:
        self.calls: list[TaskType] = []

    def supports_images(self) -> bool:
        return False

    def call(self, request: ModelRequest):
        self.calls.append(request.task)
        return json.dumps({
            "question_number": "11(i)",
            "question_type": "statistics",
            "is_correct": False,
            "score": 1,
            "full_score": 2,
            "error_type": "arithmetic_error",
            "knowledge_tags": ["statistics"],
            "needs_review": False,
            "short_feedback": "The mean is not correct.",
            "grading_confidence": 0.6,
            "correct_answer": "34.25",
            "student_feedback": "This calculation is wrong.",
            "teacher_feedback": "Student made an arithmetic error.",
            "syllabus_topics": [],
            "relevant_formulas": [],
        })


def test_combined_standard_deviation_uses_local_fallback_when_extractor_fails() -> None:
    parent_stem = (
        "A sample of 12 gulls has mean age 15.5 years and standard deviation 1.2 years. "
        "For a sample of 20 herons, sum y = 910 and sum y^2 = 42850."
    )
    question_text = "Find the standard deviation of the ages of all 32 birds."

    result = verify_statistics(
        question_text=question_text,
        parent_stem=parent_stem,
        student_answer="16.02",
        working_steps=[],
        client=FailingClient(),
    )

    assert result.verified is True
    assert result.student_matches is True
    assert result.primary_answer == "16.0198"
    assert "local_fallback" in result.detail


def test_combined_statistics_prefers_local_extraction_before_llm() -> None:
    parent_stem = (
        "The club has 12 Junior members with mean 15.5 and standard deviation 1.2. "
        "For 20 Senior members, sum y = 910 and sum y^2 = 42850."
    )
    client = CountingClient()

    result = verify_statistics(
        question_text="Find the mean age of all 32 members.",
        parent_stem=parent_stem,
        student_answer="34.25",
        working_steps=[],
        client=client,
    )

    assert result.verified is True
    assert result.student_matches is True
    assert result.primary_answer == "34.25"
    assert client.calls == 0


def test_single_model_statistics_grading_is_corrected_by_verifier() -> None:
    parent_stem = (
        "The Quivers Archery club has 12 Junior members and 20 Senior members. "
        "For the Junior members, the mean age is 15.5 years and the standard deviation "
        "of the ages is 1.2 years. The ages of the Senior members are summarised by "
        "sum y = 910 and sum y^2 = 42850."
    )
    question = QuestionData(
        question_number="11(i)",
        bbox=[0, 0, 10, 10],
        parent_stem=parent_stem,
        question_text="Find the mean age of all 32 members of the club.",
        student_answer="34.25",
        working_steps=["(12 * 15.5 + 910) / 32 = 34.25"],
        marks=2,
        image_quality="good",
        confidence=0.95,
    )
    client = WrongStatsGradeClient()

    grade = grade_question(
        question,
        client,
        task=TaskType.grade,
        q_type=QuestionType.statistics,
        allow_llm_classification=False,
        parse_attempts=1,
        request_retries=0,
    )

    assert grade.is_correct is True
    assert grade.score == grade.full_score
    assert grade.error_type == "correct"
    assert grade.needs_review is False
    assert "正确" in grade.short_feedback
    assert "错误" not in grade.short_feedback
    assert grade.student_feedback is not None
    assert "正确" in grade.student_feedback
    assert "wrong" not in grade.student_feedback.lower()
    assert grade.teacher_feedback is not None
    assert "覆盖原模型" in grade.teacher_feedback
    assert len(client.calls) == 1


def test_standard_deviation_accepts_computed_working_when_final_answer_misread() -> None:
    parent_stem = (
        "The club has 12 Junior members and 20 Senior members. "
        "For the Junior members, the mean age is 15.5 years and the standard deviation "
        "is 1.2 years. The Senior members are summarised by sum y = 910 and sum y^2 = 42850."
    )

    result = verify_statistics(
        question_text="Find the standard deviation of the ages of all 32 members.",
        parent_stem=parent_stem,
        student_answer="16.20",
        working_steps=["s.d = sqrt((2900.28 + 42850) / 32 - (34.25)^2)"],
        client=CountingClient(),
        allow_llm=False,
    )

    assert result.verified is True
    assert result.student_matches is True
    assert result.primary_answer == "16.0198"
    assert "working_expr" in result.detail


def test_combined_statistics_accepts_sigma_misread_for_sum_symbol() -> None:
    parent_stem = (
        "The club has 12 Junior members and 20 Senior members. "
        "For the Junior members, the mean age is 15.5 years and the standard deviation "
        "is 1.2 years. The Senior members are summarised by σy = 910 and σy^2 = 42 850."
    )

    result = verify_statistics(
        question_text="Find the mean age of all 32 members.",
        parent_stem=parent_stem,
        student_answer="34.25",
        working_steps=[],
        client=CountingClient(),
        allow_llm=False,
    )

    assert result.verified is True
    assert result.student_matches is True
    assert result.primary_answer == "34.25"
