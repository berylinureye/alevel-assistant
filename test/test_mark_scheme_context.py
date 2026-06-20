from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.schemas import QuestionData, QuestionType
from questionbank.mark_scheme import extract_question_mark_scheme_context
from router.models import ModelRequest, ModelRole, TaskType
from grader.grader import grade_question


class CaptureClient:
    role = ModelRole.base
    model_id = "capture"
    provider = "test"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def supports_images(self) -> bool:
        return False

    def call(self, request: ModelRequest) -> str:
        self.prompts.append(request.prompt)
        return json.dumps(
            {
                "is_correct": True,
                "correct_answer": "$x=2$",
                "score": 4,
                "full_score": 4,
                "error_type": "correct",
                "knowledge_tags": ["functions"],
                "needs_review": False,
                "short_feedback": "做对了。",
                "grading_confidence": 0.95,
                "student_feedback": "做对了。",
                "teacher_feedback": "掌握良好，无需额外关注。",
                "syllabus_topics": [],
                "relevant_formulas": [],
            }
        )


def test_extract_question_mark_scheme_context_from_text(monkeypatch, tmp_path) -> None:
    fake_pdf = tmp_path / "9709_s16_ms_12.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake")
    fake_text = """
Page 4
1
Correct method for inverse function
B1
Uses x = 2 correctly
M1 A1
[3]

2
Differentiate correctly
B1
[1]
"""

    monkeypatch.setattr("questionbank.mark_scheme.extract_pdf_text", lambda path: fake_text)

    context = extract_question_mark_scheme_context(
        fake_pdf,
        "1",
        paper_label="CIE 9709/12 May/Jun 2016",
    )

    assert context.confidence == "high"
    assert context.question_number == "1"
    assert "Official mark scheme" in context.text
    assert "Correct method for inverse function" in context.text
    assert "Differentiate correctly" not in context.text


def test_extract_question_mark_scheme_context_handles_real_pdf_numeric_formula_lines() -> None:
    context = extract_question_mark_scheme_context(
        ROOT / "data/papers/9709/2016/9709_s16_ms_12.pdf",
        "10",
        paper_label="CIE 9709/12 May/Jun 2016",
    )

    assert context.confidence == "high"
    assert "question 10" in context.text
    assert "Vol = π" in context.text
    assert "ff(x)" not in context.text


def test_grade_question_includes_mark_scheme_context_in_prompt() -> None:
    client = CaptureClient()
    question = QuestionData(
        question_number="1",
        bbox=[],
        question_text="Solve f(x)=2.",
        student_answer="x=2",
        working_steps=["f(2)=2"],
        marks=4,
        image_quality="good",
        confidence=0.99,
        mark_scheme_context="Official mark scheme context for Q1: B1 for inverse, M1 for substitution.",
    )

    grade_question(
        question,
        client,
        task=TaskType.grade,
        skip_verification=True,
        q_type=QuestionType.algebra,
    )

    assert client.prompts
    assert "Official mark scheme context for Q1" in client.prompts[0]
    assert "Use this official mark scheme as the primary scoring guide" in client.prompts[0]
