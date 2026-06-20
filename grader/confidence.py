"""
Confidence 校准：调整 LLM 自报的 grading_confidence。

基于启发式规则检测自相矛盾和可疑模式，结合 SymPy 验证结果。
"""
from __future__ import annotations

from models.schemas import GradeResult


def calibrate_confidence(
    grade: GradeResult,
    sympy_agrees: bool | None = None,
) -> float:
    """
    返回校准后的 grading_confidence（0.0 ~ 1.0）。

    调整规则：
    - correct_answer 为空/模糊 → -0.2
    - is_correct=True 但 error_type != "correct" → -0.3（自相矛盾）
    - is_correct=False 但 error_type == "correct" → -0.3
    - SymPy 验证一致 → +0.15
    - SymPy 验证不一致 → -0.25
    """
    conf = grade.grading_confidence

    # 正确答案缺失或过于模糊
    if not grade.correct_answer or len(grade.correct_answer.strip()) < 2:
        conf -= 0.2

    # is_correct 与 error_type 自相矛盾
    if grade.is_correct and grade.error_type not in ("correct", None):
        conf -= 0.3
    if not grade.is_correct and grade.error_type == "correct":
        conf -= 0.3

    # SymPy 验证结果
    if sympy_agrees is True:
        conf += 0.15
    elif sympy_agrees is False:
        conf -= 0.25

    return max(0.0, min(1.0, conf))
