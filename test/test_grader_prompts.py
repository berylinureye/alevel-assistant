from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from grader.prompts import _STATISTICS


def test_statistics_prompt_uses_caie_9709_micro_tags():
    prompt = _STATISTICS.lower()

    assert "cambridge international as & a level mathematics 9709" in prompt
    assert "paper 5" in prompt
    assert "paper 6" in prompt
    assert "mean" in prompt
    assert "variance" in prompt
    assert "standard_deviation" in prompt
    assert "do not output generic tags such as statistics" in prompt
