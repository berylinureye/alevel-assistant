from __future__ import annotations

from router.models import ModelRole
from verifier.statistics_verifier import verify_statistics


class FailingClient:
    role = ModelRole.base
    model_id = "failing"
    provider = "test"

    def supports_images(self) -> bool:
        return False

    def call(self, request):
        raise RuntimeError("没有可用token")


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
