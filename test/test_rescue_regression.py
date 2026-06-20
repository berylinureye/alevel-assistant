"""Regression test: rescue must only strip (never add, never touch
other fields) when run on historical VL outputs.

Strategy
--------
For every bench_out_*.json in the repo root, we:
  1. Load its questions list (schema varies — older dumps are raw lists,
     newer ones wrap in a 'result.questions' envelope — we handle both).
  2. Deep-copy the items twice.
  3. Run _attach_parent_stems on copy A with ``_rescue_trailing_bridging_to_next_stem``
     monkey-patched to a no-op. This reproduces the pipeline BEFORE
     Step 3 landed.
  4. Run _attach_parent_stems on copy B normally (rescue active, current
     production path).
  5. Diff B against A item-by-item on (question_text, parent_stem,
     student_answer, working_steps, marks, page).

Assertion contract
------------------
For every (file, item) pair, the diff must be one of:
  * ``unchanged`` — rescue had no effect
  * ``expected_strip`` — rescue removed whole sentence(s) from the END
      of question_text; nothing else changed; the stripped content does
      NOT start with an instruction verb (would indicate false positive)
  * Anything else → FAIL. These are side-effect regressions — rescue
    contract said it only touches qt tails.

Monkey-patch rationale (vs git stash)
-------------------------------------
The user's original specification suggested ``git stash`` to isolate
the pre-Step-3 state. Monkey-patching the ``_rescue_trailing_...``
symbol on ``pipeline.segmenter`` at module level achieves the same
effect without touching the working tree — safer in CI, reproducible,
and avoids the "untracked file + ``git stash -u``" edge cases that
``pipeline/segmenter.py`` (entirely untracked in this repo) would hit.
Both approaches change exactly the same observable: whether rescue
runs or not.
"""
from __future__ import annotations

import copy
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pipeline.segmenter as seg  # noqa: E402


_BENCH_FILES = sorted(_REPO_ROOT.glob("bench_out_*.json"))


def _extract_questions(raw: Any) -> list[dict]:
    """bench_out files come in two schemas: newer ones wrap in
    ``{"elapsed_seconds": ..., "result": {"questions": [...]}}``,
    older ones are already a list. Unwrap both."""
    if isinstance(raw, dict):
        res = raw.get("result", raw)
        qs = res.get("questions", []) if isinstance(res, dict) else []
    else:
        qs = raw
    if not isinstance(qs, list):
        return []
    return [q for q in qs if isinstance(q, dict)]


def _run_pipeline(items: list[dict], with_rescue: bool) -> list[dict]:
    """Run _attach_parent_stems with rescue either active or disabled
    (via monkey-patch). Items mutated in place — caller must have
    deep-copied beforehand."""
    if with_rescue:
        seg._attach_parent_stems(items)
        return items
    original = seg._rescue_trailing_bridging_to_next_stem
    seg._rescue_trailing_bridging_to_next_stem = (
        lambda results, group_stems: None
    )
    try:
        seg._attach_parent_stems(items)
    finally:
        seg._rescue_trailing_bridging_to_next_stem = original
    return items


_INSTRUCTION_OPENERS = seg._INSTRUCTION_OPENERS  # re-export for classifier


def _classify_diff(baseline: dict, rescued: dict) -> tuple[str, str]:
    """Return (category, detail). Category is one of:
       ``unchanged``, ``expected_strip``, ``UNEXPECTED_*``."""
    bq = str(baseline.get("question_text", "") or "")
    rq = str(rescued.get("question_text", "") or "")
    bp = str(baseline.get("parent_stem", "") or "")
    rp = str(rescued.get("parent_stem", "") or "")

    # Rescue is NOT supposed to touch parent_stem. Flag any ps diff.
    if bp != rp:
        return ("UNEXPECTED_parent_stem_changed",
                f"ps baseline={bp[:120]!r} rescued={rp[:120]!r}")

    # Other fields should be untouched too.
    for k in ("student_answer", "working_steps", "marks", "page",
              "question_number"):
        if baseline.get(k) != rescued.get(k):
            return (f"UNEXPECTED_{k}_changed",
                    f"{k} baseline={baseline.get(k)!r} rescued={rescued.get(k)!r}")

    if bq == rq:
        return ("unchanged", "")

    # qt differs. Rescue strips from the end, so rescued must be a
    # prefix-substring of baseline (modulo trailing whitespace).
    bq_stripped = bq.rstrip()
    rq_stripped = rq.rstrip()
    if not bq_stripped.startswith(rq_stripped):
        return ("UNEXPECTED_qt_non_prefix_change",
                f"baseline_qt={bq[:120]!r} rescued_qt={rq[:120]!r}")

    removed = bq_stripped[len(rq_stripped):].lstrip()
    if not removed:
        return ("UNEXPECTED_only_whitespace_changed",
                f"baseline_qt={bq!r} rescued_qt={rq!r}")

    # The stripped content should be bridging, not an instruction.
    first_token = (
        removed.strip().split(None, 1)[0].lower().rstrip(",.;:)")
        if removed.strip() else ""
    )
    if first_token in _INSTRUCTION_OPENERS:
        return ("UNEXPECTED_stripped_content_is_instruction",
                f"removed={removed[:120]!r} (starts with instruction "
                f"verb {first_token!r})")

    return ("expected_strip",
            f"removed={removed[:120]!r}")


@pytest.mark.parametrize(
    "bench_path", _BENCH_FILES, ids=lambda p: p.name,
)
def test_rescue_no_side_effects(bench_path: Path, caplog) -> None:
    try:
        raw = json.loads(bench_path.read_text())
    except Exception as e:
        pytest.skip(f"unreadable: {e}")
    items_src = _extract_questions(raw)
    if not items_src:
        pytest.skip("no questions in file")

    baseline_items = copy.deepcopy(items_src)
    rescued_items = copy.deepcopy(items_src)

    caplog.set_level(logging.INFO, logger="pipeline.segmenter")
    _run_pipeline(baseline_items, with_rescue=False)
    _run_pipeline(rescued_items, with_rescue=True)

    assert len(baseline_items) == len(rescued_items), (
        f"item count changed by rescue: baseline={len(baseline_items)}, "
        f"rescued={len(rescued_items)}"
    )

    categories: dict[str, int] = {}
    unexpected: list[str] = []
    for i, (b, r) in enumerate(zip(baseline_items, rescued_items)):
        cat, detail = _classify_diff(b, r)
        categories[cat] = categories.get(cat, 0) + 1
        if cat.startswith("UNEXPECTED_"):
            unexpected.append(
                f"  item[{i}] qn={r.get('question_number')!r}: {cat} :: {detail}"
            )

    if unexpected:
        pytest.fail(
            f"{bench_path.name}: {len(unexpected)} side-effect regression(s):\n"
            + "\n".join(unexpected)
        )
