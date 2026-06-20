"""pytest tests for `_rescue_trailing_bridging_to_next_stem`.

Loads every fixture under test/fixtures/rescue_bridging/*.json and asserts:
    1. After rescue runs on fixture.pre_items + fixture.group_stems, each
       item's (question_number, question_text, parent_stem) matches the
       fixture's expected_post_rescue entry at the same index.
    2. The number of rescue-strip log events emitted (captured via
       pytest's caplog) equals len(fixture.expected_strip_log).

Phase-2 fixtures (adv_3_shift_by_one_prepend) are skipped here and will
be enabled when Phase 2 (qt head prepend rescue) lands.

Run:
    pytest test/test_rescue_bridging.py -v
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.segmenter import _rescue_trailing_bridging_to_next_stem

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rescue_bridging"
# Fixture files use the ``case_*`` or ``adv_*`` prefix; leading-underscore
# files (like ``_baseline_*.json``) are shared helper data, not fixtures.
_FIXTURES = sorted(
    p for p in _FIXTURE_DIR.glob("*.json")
    if not p.name.startswith("_")
)

# Fixtures deferred to Phase 2 (qt head prepend). Skipped for now.
_PHASE_2_NAMES = frozenset({"adv_3_shift_by_one_prepend"})


@pytest.mark.parametrize(
    "fixture_path", _FIXTURES, ids=lambda p: p.stem
)
def test_rescue_bridging_fixture(fixture_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    fix = json.loads(fixture_path.read_text())
    name = fix["name"]

    if name in _PHASE_2_NAMES:
        pytest.skip(
            "Phase 2: qt head prepend rescue not yet implemented. "
            "Fixture preserved for future enablement."
        )

    # Deep copy so the fixture file is never mutated in place (rescue
    # modifies items in place).
    items = json.loads(json.dumps(fix["pre_items"]))
    group_stems = dict(fix["group_stems"])

    caplog.set_level(logging.INFO, logger="pipeline.segmenter")
    _rescue_trailing_bridging_to_next_stem(items, group_stems)

    # ----- Assert per-item field equivalence ------------------------------
    expected_post = fix["expected_post_rescue"]
    assert len(items) == len(expected_post), (
        f"{name}: item count mismatch ({len(items)} actual vs "
        f"{len(expected_post)} expected)"
    )
    for idx, (got, want) in enumerate(zip(items, expected_post)):
        ctx = f"{name}[{idx}] qnum={want.get('question_number')!r}"
        assert got.get("question_number") == want["question_number"], (
            f"{ctx}: question_number mismatch"
        )
        assert got.get("question_text") == want["question_text"], (
            f"{ctx}: question_text mismatch\n"
            f"  expected: {want['question_text']!r}\n"
            f"  actual:   {got.get('question_text')!r}"
        )
        assert got.get("parent_stem") == want["parent_stem"], (
            f"{ctx}: parent_stem mismatch\n"
            f"  expected: {want['parent_stem']!r}\n"
            f"  actual:   {got.get('parent_stem')!r}"
        )

    # ----- Assert rescue-strip log event count ---------------------------
    # The code logs one 'rescue_decision' line per decision point, as a
    # JSON payload. We count those where action=="strip". Skip-decision
    # lines are informational; they're not counted.
    strip_records = []
    for r in caplog.records:
        if r.name != "pipeline.segmenter":
            continue
        msg = r.getMessage()
        if not msg.startswith("rescue_decision "):
            continue
        try:
            payload = json.loads(msg[len("rescue_decision "):])
        except json.JSONDecodeError:
            continue
        if payload.get("action") == "strip":
            strip_records.append(payload)

    expected_n = len(fix["expected_strip_log"])
    assert len(strip_records) == expected_n, (
        f"{name}: expected {expected_n} strip event(s), got "
        f"{len(strip_records)}: {strip_records}"
    )
