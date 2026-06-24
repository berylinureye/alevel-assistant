from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.pipeline import _process_one_question
from router.models import ModelRole


class FailingClient:
    role = ModelRole.base
    model_id = "should-not-call"
    provider = "test"

    def supports_images(self) -> bool:
        return False

    def call(self, request):
        raise AssertionError("orphan subpart should not be sent to an LLM")


def test_orphan_subpart_without_parent_stem_asks_for_full_question() -> None:
    result = _process_one_question(
        {
            "question_number": "c",
            "bbox": [0, 0, 1536, 2048],
            "question_text": (
                "Find the probability that at least 2 of the marbles chosen are blue, "
                "given that at least 1 red marble and at least 1 blue marble are chosen."
            ),
            "student_answer": "",
            "working_steps": ["P(X \\ge 2 | Y \\ge 1 \\cap X \\ge 1)", "="],
            "marks": 3,
            "image_quality": "good",
            "confidence": 0.7,
        },
        FailingClient(),
        FailingClient(),
        "auto",
        True,
        agent_clients=None,
        solution_client=None,
        generate_solution_inline=False,
    )

    record = result["record"]
    grading = record["grading"]

    assert grading["error_type"] == "missing_parent_context"
    assert grading["needs_review"] is True
    assert grading["correct_answer"] is None
    assert "补充上一页" in grading["short_feedback"]
    assert "完整题目" in record["feedback"]["student_feedback"]
