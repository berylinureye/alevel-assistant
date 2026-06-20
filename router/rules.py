"""
升级规则列表。

每条规则签名：(RouteContext) -> tuple[bool, str]
  - bool : 是否触发升级
  - str  : 触发原因描述（用于日志和 escalation_reasons 字段）

规则之间相互独立，全部检查，任一触发即升级。
新增规则只需往 ESCALATION_RULES 列表追加，不改其他代码。
"""
from __future__ import annotations

import re
from typing import Callable

from models.schemas import QuestionType
from router.context import RouteContext

Rule = Callable[[RouteContext], tuple[bool, str]]


# ---------------------------------------------------------------------------
# 各条规则
# ---------------------------------------------------------------------------

def rule_low_extraction_confidence(ctx: RouteContext) -> tuple[bool, str]:
    if ctx.extraction_confidence < 0.5:
        return True, f"low_extraction_confidence({ctx.extraction_confidence:.2f})"
    return False, ""


def rule_poor_image_quality(ctx: RouteContext) -> tuple[bool, str]:
    if ctx.image_quality == "poor":
        return True, "poor_image_quality"
    return False, ""


def rule_grader_flagged_review(ctx: RouteContext) -> tuple[bool, str]:
    if ctx.needs_review:
        return True, "grader_flagged_review"
    return False, ""


def rule_low_grading_confidence(ctx: RouteContext) -> tuple[bool, str]:
    if ctx.grading_confidence < 0.35:
        return True, f"low_grading_confidence({ctx.grading_confidence:.2f})"
    return False, ""


def rule_complex_working(ctx: RouteContext) -> tuple[bool, str]:
    if ctx.working_steps_count > 12:
        return True, f"complex_working({ctx.working_steps_count}_steps)"
    return False, ""


def rule_unknown_question_type(ctx: RouteContext) -> tuple[bool, str]:
    if ctx.question_type == QuestionType.unknown:
        return True, "unknown_question_type"
    return False, ""


# 匹配"含变量的分式"或"复合函数调用"
# 需同时满足：① grading_confidence < 0.8  ② 答案含复杂结构且长度 > 15
_COMPLEX_EXPR = re.compile(
    r"(?:[a-zA-Z]\s*/\s*[a-zA-Z]"   # 变量分式：x/y、(x+1)/y 等
    r"|sqrt\s*\("                    # sqrt(
    r"|ln\s*\("                      # ln(
    r"|e\s*\^\s*[({])"               # e^( 或 e^{
)


def rule_ambiguous_equivalence(ctx: RouteContext) -> tuple[bool, str]:
    """
    触发条件（两者同时满足，缺一不可）：
    1. grading_confidence < 0.8：base model 已经不太确定对错
    2. student_answer 含复杂表达式（变量分式 / 复合函数）且长度 > 15

    避免仅因答案含 ln/sqrt 就升级；只在 base model 本身不确定时才触发。
    """
    if ctx.grading_confidence >= 0.6:
        return False, ""
    answer = ctx.student_answer
    if len(answer) > 20 and _COMPLEX_EXPR.search(answer):
        return True, "ambiguous_equivalence"
    return False, ""


# ---------------------------------------------------------------------------
# 规则列表（顺序无关，全量评估）
# ---------------------------------------------------------------------------

ESCALATION_RULES: list[Rule] = [
    rule_low_extraction_confidence,
    rule_poor_image_quality,
    rule_grader_flagged_review,
    rule_low_grading_confidence,
    rule_complex_working,
    # rule_unknown_question_type removed: statistics and other non-calculus questions
    # were being needlessly escalated, doubling grading time with no quality benefit.
    rule_ambiguous_equivalence,
]
