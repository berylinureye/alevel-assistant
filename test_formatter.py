"""
Formatter 单元测试（不依赖真实 API）

运行：
    python3 test_formatter.py
"""
from __future__ import annotations

import json

from models.schemas import GradeResult, QuestionFeedback, QuestionType
from formatter.feedback import generate_feedback, _fallback_feedback, _correct_feedback
from formatter.summarizer import (
    build_summary,
    compute_common_error_types,
    compute_knowledge_tags_summary,
    FALLBACK_COMMENT,
)
from router.models import ModelRole, ModelRequest, TaskType


# ---------------------------------------------------------------------------
# Mock clients
# ---------------------------------------------------------------------------

class _OKClient:
    """返回预设 JSON 字符串的 mock client"""
    role     = ModelRole.base
    model_id = "mock-ok"
    provider = "mock"

    def __init__(self, response: str) -> None:
        self._response = response

    def supports_images(self) -> bool:
        return False

    def call(self, request: ModelRequest) -> str:
        return self._response


class _FailClient:
    """每次调用都抛异常的 mock client"""
    role     = ModelRole.base
    model_id = "mock-fail"
    provider = "mock"

    def supports_images(self) -> bool:
        return False

    def call(self, request: ModelRequest) -> str:
        raise RuntimeError("mock API error")


# ---------------------------------------------------------------------------
# 样本 GradeResult
# ---------------------------------------------------------------------------

def _make_grade(
    question_number: str = "1a",
    is_correct: bool = False,
    error_type: str | None = "missing_constant",
    knowledge_tags: list[str] | None = None,
    needs_review: bool = False,
    score: float = 2.0,
    full_score: float = 3.0,
) -> GradeResult:
    return GradeResult(
        question_number    = question_number,
        question_type      = QuestionType.integration,
        is_correct         = is_correct,
        score              = score,
        full_score         = full_score,
        error_type         = error_type,
        knowledge_tags     = knowledge_tags or ["reverse_power_rule", "constant_of_integration"],
        needs_review       = needs_review,
        short_feedback     = "Missing +C.",
        grading_confidence = 0.95,
        escalation_reasons = [],
    )


# ---------------------------------------------------------------------------
# T1: 统计字段单元测试
# ---------------------------------------------------------------------------

def test_compute_stats_counts() -> None:
    grades = [
        _make_grade("1a", is_correct=True,  error_type="correct",  score=3, full_score=3),
        _make_grade("1b", is_correct=False, error_type="sign_error", score=1, full_score=2),
        _make_grade("2a", is_correct=False, error_type="missing_constant", score=2, full_score=3,
                    needs_review=True),
    ]
    from formatter.summarizer import _compute_stats
    stats = _compute_stats(grades)

    assert stats["total_questions"]  == 3,   f"total_questions: {stats['total_questions']}"
    assert stats["correct_count"]    == 1,   f"correct_count: {stats['correct_count']}"
    assert stats["incorrect_count"]  == 2,   f"incorrect_count: {stats['incorrect_count']}"
    assert stats["review_count"]     == 1,   f"review_count: {stats['review_count']}"
    assert stats["score_total"]      == 6.0, f"score_total: {stats['score_total']}"
    assert stats["full_score_total"] == 8.0, f"full_score_total: {stats['full_score_total']}"
    print("T1 PASS: compute_stats_counts")


def test_compute_stats_unanswered_separate_bucket() -> None:
    grades = [
        _make_grade("1a", is_correct=True, error_type="correct", score=3, full_score=3),
        GradeResult(
            question_number="1b",
            question_type=QuestionType.integration,
            is_correct=False,
            score=0,
            full_score=4,
            error_type="unanswered",
            knowledge_tags=[],
            needs_review=False,
            short_feedback="此题未作答。",
            grading_confidence=1.0,
            unanswered=True,
            escalation_reasons=[],
        ),
        _make_grade("2a", is_correct=False, error_type="sign_error", score=1, full_score=2),
    ]
    from formatter.summarizer import _compute_stats
    stats = _compute_stats(grades)

    assert stats["total_questions"] == 3, f"total_questions: {stats['total_questions']}"
    assert stats["correct_count"] == 1, f"correct_count: {stats['correct_count']}"
    assert stats["incorrect_count"] == 1, f"incorrect_count: {stats['incorrect_count']}"
    assert stats["unanswered_count"] == 1, f"unanswered_count: {stats['unanswered_count']}"
    print("T1b PASS: unanswered counted separately")


# ---------------------------------------------------------------------------
# T2: common_error_types 统计规则
# ---------------------------------------------------------------------------

def test_common_error_types_exclusion() -> None:
    grades = [
        _make_grade(error_type="missing_constant"),
        _make_grade(error_type="correct"),
        _make_grade(error_type="missing_constant"),
        _make_grade(error_type="unknown"),
        _make_grade(error_type=None),
    ]
    result = compute_common_error_types(grades)
    assert result == ["missing_constant"], f"got: {result}"
    print("T2a PASS: exclusion of correct/unknown/None")


def test_common_error_types_min_frequency() -> None:
    grades = [
        _make_grade(error_type="sign_error"),
        _make_grade(error_type="wrong_rule"),
    ]
    result = compute_common_error_types(grades)
    assert result == [], f"got: {result}"
    print("T2b PASS: min_frequency=2 enforced")


# ---------------------------------------------------------------------------
# T3: knowledge_tags 归一化
# ---------------------------------------------------------------------------

def test_knowledge_tags_normalization() -> None:
    grades = [
        _make_grade(knowledge_tags=["Power Rule"]),
        _make_grade(knowledge_tags=["power_rule"]),
        _make_grade(knowledge_tags=["POWER_RULE"]),
    ]
    result = compute_knowledge_tags_summary(grades)
    assert result.get("power_rule") == 3, f"got: {result}"
    print("T3 PASS: knowledge_tags normalization")


def test_knowledge_tags_empty_protection() -> None:
    # 直接构造 knowledge_tags 为空的 GradeResult，绕开 _make_grade 的默认值
    def _bare(tags):
        return GradeResult(
            question_number="x", question_type=QuestionType.integration,
            is_correct=False, score=0, full_score=3,
            error_type="unknown", knowledge_tags=tags,
            needs_review=False, short_feedback="",
            grading_confidence=0.5, escalation_reasons=[],
        )
    grades = [_bare([]), _bare([])]
    result = compute_knowledge_tags_summary(grades)
    assert result == {}, f"got: {result}"
    print("T3b PASS: knowledge_tags empty protection")


# ---------------------------------------------------------------------------
# T4: 单题 feedback 失败回退
# ---------------------------------------------------------------------------

def test_generate_feedback_fallback_on_error() -> None:
    grade  = _make_grade(is_correct=False)
    client = _FailClient()
    result = generate_feedback(grade, client, max_retries=1)

    assert result.question_number == "1a"
    assert "Missing +C." in result.student_feedback
    assert "Error: missing_constant" in result.teacher_feedback
    print("T4 PASS: generate_feedback fallback on API error")


def test_generate_feedback_correct_no_llm() -> None:
    grade  = _make_grade(is_correct=True, error_type="correct", score=3, full_score=3)
    client = _FailClient()   # 即使 client 会失败，正确题也不调用
    result = generate_feedback(grade, client, max_retries=0)

    assert result.student_feedback == "- 积分计算准确。"
    print("T4b PASS: correct question skips LLM")


# ---------------------------------------------------------------------------
# T5: summary comment 失败回退
# ---------------------------------------------------------------------------

def test_build_summary_comment_fallback() -> None:
    grades  = [_make_grade("1a"), _make_grade("1b")]
    client  = _FailClient()
    summary = build_summary(grades, [], client, max_retries=0, generate_comment=True)

    # 统计字段正确计算
    assert summary.total_questions  == 2
    assert summary.incorrect_count  == 2
    assert summary.score_total      == 4.0
    assert summary.full_score_total == 6.0
    # comment 降级为 fallback
    assert summary.overall_teacher_comment == FALLBACK_COMMENT
    print("T5 PASS: build_summary comment fallback, stats preserved")


# ---------------------------------------------------------------------------
# T6: 最终输出 schema 对齐
# ---------------------------------------------------------------------------

def test_output_schema_completeness() -> None:
    grade = _make_grade("2a", is_correct=False)

    feedback_json = '{"student_feedback": "Check your +C.", "teacher_feedback": "Student omitted constant."}'
    client = _OKClient(feedback_json)

    fb = generate_feedback(grade, client, question_text="Integrate 4x^3", student_answer="x^4")

    # QuestionFeedback 字段完整
    assert fb.question_number
    assert fb.student_feedback
    assert fb.teacher_feedback

    grades  = [grade]
    summary = build_summary(
        grades, [fb], _OKClient("Great work overall."), max_retries=1, generate_comment=True,
    )

    required = [
        "total_questions", "correct_count", "incorrect_count",
        "review_count", "score_total", "full_score_total",
        "common_error_types", "knowledge_tags_summary", "overall_teacher_comment",
    ]
    dump = summary.model_dump()
    for field in required:
        assert field in dump, f"missing field: {field}"
    print("T6 PASS: output schema completeness")


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_compute_stats_counts,
        test_compute_stats_unanswered_separate_bucket,
        test_common_error_types_exclusion,
        test_common_error_types_min_frequency,
        test_knowledge_tags_normalization,
        test_knowledge_tags_empty_protection,
        test_generate_feedback_fallback_on_error,
        test_generate_feedback_correct_no_llm,
        test_build_summary_comment_fallback,
        test_output_schema_completeness,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"结果: {len(tests) - failed}/{len(tests)} 通过")
