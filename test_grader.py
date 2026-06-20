"""
批改模块 + 路由层独立测试：直接用 mock QuestionData，不依赖图片。

运行：
    python3 test_grader.py
"""
from __future__ import annotations

import json
import os
from dotenv import load_dotenv

from models.schemas import QuestionData
from router.models import ModelRole, build_registry
from router.models import TaskType
from router.context import RouteContext
from router.router import route
from grader.grader import grade_question

load_dotenv(override=True)

registry      = build_registry()
base_client   = registry[ModelRole.base]
review_client = registry[ModelRole.review]

# ---------------------------------------------------------------------------
# 测试样例
# ---------------------------------------------------------------------------
TEST_CASES: list[QuestionData] = [

    # Case 1: 正确的求导
    QuestionData(
        question_number="1a",
        bbox=[0, 0, 100, 100],
        question_text="Differentiate y = 3x^4 - 2x^2 + 5x - 1 with respect to x.",
        student_answer="dy/dx = 12x^3 - 4x + 5",
        working_steps=[
            "Differentiate each term separately",
            "d/dx(3x^4) = 12x^3",
            "d/dx(-2x^2) = -4x",
            "d/dx(5x) = 5",
            "d/dx(-1) = 0",
        ],
        image_quality="good",
        confidence=0.95,
    ),

    # Case 2: 符号错误的求导（chain rule）
    QuestionData(
        question_number="1b",
        bbox=[0, 0, 100, 100],
        question_text="Differentiate y = sin(3x) with respect to x.",
        student_answer="dy/dx = -3cos(3x)",
        working_steps=[
            "Use chain rule",
            "dy/dx = cos(3x) * 3",
            "dy/dx = -3cos(3x)",
        ],
        image_quality="good",
        confidence=0.90,
    ),

    # Case 3: 积分漏写 +C
    QuestionData(
        question_number="2a",
        bbox=[0, 0, 100, 100],
        question_text="Find the integral of 4x^3 - 6x + 2 with respect to x.",
        student_answer="x^4 - 3x^2 + 2x",
        working_steps=[
            "Integrate each term",
            "∫4x^3 dx = x^4",
            "∫-6x dx = -3x^2",
            "∫2 dx = 2x",
        ],
        image_quality="good",
        confidence=0.95,
    ),

    # Case 4: 正确找驻点（步骤完整）
    QuestionData(
        question_number="3a",
        bbox=[0, 0, 100, 100],
        question_text="Find the stationary points of y = x^3 - 6x^2 + 9x + 1 and determine their nature.",
        student_answer="Stationary points at x=1 (local max) and x=3 (local min)",
        working_steps=[
            "dy/dx = 3x^2 - 12x + 9",
            "Set dy/dx = 0: 3x^2 - 12x + 9 = 0",
            "x^2 - 4x + 3 = 0",
            "(x-1)(x-3) = 0",
            "x = 1 or x = 3",
            "d²y/dx² = 6x - 12",
            "At x=1: d²y/dx² = -6 < 0, so local maximum",
            "At x=3: d²y/dx² = 6 > 0, so local minimum",
            "y(1) = 1 - 6 + 9 + 1 = 5",
            "y(3) = 27 - 54 + 27 + 1 = 1",
        ],
        image_quality="good",
        confidence=0.95,
    ),

]

# ---------------------------------------------------------------------------
# 运行：base 批改 → 路由判断 → 按需升级
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    all_results = []

    for i, q in enumerate(TEST_CASES, 1):
        print(f"\n{'='*55}")
        print(f"[test {i}] Q{q.question_number}: {q.question_text[:60]}...")

        # Step 1: base 批改
        base_grade = grade_question(q, base_client, task=TaskType.grade)

        # Step 2: 路由判断
        ctx = RouteContext(
            image_quality         = q.image_quality,
            extraction_confidence = q.confidence,
            working_steps_count   = len(q.working_steps),
            student_answer        = q.student_answer,
            question_type         = base_grade.question_type,
            grading_confidence    = base_grade.grading_confidence,
            needs_review          = base_grade.needs_review,
        )
        decision = route(ctx)
        print(f"  → route: {decision.role.value}  escalated={decision.escalated}  reasons={decision.reasons}")

        # Step 3: 按需升级
        if decision.escalated:
            final_grade = grade_question(q, review_client, task=TaskType.review)
            final_grade.escalation_reasons = decision.reasons
            used_model = review_client.model_id
        else:
            final_grade = base_grade
            used_model = base_client.model_id

        output = final_grade.model_dump()
        output["used_model"] = used_model
        print(json.dumps(output, ensure_ascii=False, indent=2))
        all_results.append(output)

    print(f"\n{'='*55}")
    print(f"[done] {len(all_results)} 道题完成")
    escalated = sum(1 for r in all_results if r.get("escalation_reasons"))
    print(f"[done] 升级到 review_model: {escalated} 道，留在 base_model: {len(all_results) - escalated} 道")
