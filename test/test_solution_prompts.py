from __future__ import annotations

from string import Formatter

from grader.solution_prompts import get_active_prompt


def test_active_solution_prompt_formats_with_latex_examples() -> None:
    allowed_fields = {
        "question_text",
        "student_answer",
        "correct_answer",
        "feedback",
        "is_correct_text",
    }
    prompt_template = get_active_prompt()
    unexpected_fields = {
        field
        for _, field, _, _ in Formatter().parse(prompt_template)
        if field is not None and field not in allowed_fields
    }

    assert unexpected_fields == set()
    prompt = prompt_template.format(
        question_text=r"Find $\frac{x}{2}$.",
        student_answer="",
        correct_answer=r"$x = 4$",
        feedback="",
        is_correct_text="否",
    )

    assert r"\frac{1}{2}r^2\theta" in prompt
