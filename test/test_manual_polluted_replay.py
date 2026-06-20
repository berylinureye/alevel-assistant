"""Manual POLLUTED_QT replay harness.

Purpose
-------
Independent of the hand-constructed fixtures (``test/fixtures/rescue_bridging/``),
prove rescue works on REAL production data structures by:

  1. Loading a known-clean VL raw dump — today's Lesson2 page-1 output
     (all four sub-parts 1a/1b/1c/1d with qt containing ONLY the
     sub-part's instruction, ps containing progressive bridging).
  2. Manually mutating 1a's question_text to match the 23:18 user-
     screenshot POLLUTED_QT variant (append the trailing bridging
     sentence "The point P(1, 2) lies on the circle."). Everything
     else is kept byte-for-byte identical to the clean baseline.
  3. Running the full ``_attach_parent_stems`` chain (rescue in circuit).
  4. Asserting:
     - 1a.question_text is stripped back to its clean form
     - 1b/1c/1d drift byte-for-byte identically vs the clean baseline
       through the same pipeline (so any change is attributable to
       rescue alone, not to other Step 2 / merge logic)
     - A single ``rescue_decision`` JSON log line with ``action=strip``
       was emitted for 1a

Reusability
-----------
This file is deliberately NOT one-shot. When a real POLLUTED_QT case
surfaces in the ``rescue_decision`` production log, copy the polluted
payload into a new ``test_rescue_polluted_qt_replay_<slug>`` function
and add the appropriate assertions. The helper ``_replay(...)`` takes
an arbitrary item list, so any captured production payload can be
replayed verbatim.

Runs as pytest (``pytest test/test_manual_polluted_replay.py``) or as
a standalone diagnostic script (``python test/test_manual_polluted_replay.py``).
"""
from __future__ import annotations

import copy
import json
import logging
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pipeline.segmenter as seg  # noqa: E402


CLEAN_DUMP = _REPO_ROOT / "test/fixtures/rescue_bridging/_baseline_lesson2_page1_clean.json"

# The trailing bridging sentence from the 23:18 user screenshot.
# Structurally belongs to sub-part (b)'s setup (it defines P for 1b's
# tangent problem), NOT to 1a's "find radius" instruction.
BRIDGING = "The point P(1, 2) lies on the circle."

# 1a's clean instruction (the target rescue must restore)
EXPECTED_CLEAN_1A = "Find the radius of the circle and the coordinates of C."


def _load_clean_items() -> list[dict]:
    if not CLEAN_DUMP.exists():
        pytest.skip(f"missing baseline dump: {CLEAN_DUMP}")
    items = json.loads(CLEAN_DUMP.read_text())
    return [i for i in items if isinstance(i, dict)]


def _qn_key(item: dict) -> str:
    """Normalize qnum to lowercase stripped form, e.g. '1a' / '1(a)' → '1a'."""
    s = str(item.get("question_number") or "").strip().lower()
    return s.replace("(", "").replace(")", "")


def _find(items: list[dict], qn: str) -> dict:
    qn = qn.lower()
    for it in items:
        if _qn_key(it) == qn:
            return it
    raise KeyError(f"no item with qn={qn!r}")


def _inject_pollution(items: list[dict]) -> list[dict]:
    """Append the bridging sentence to 1a.question_text.

    This is the exact minimal transformation of the clean baseline that
    reproduces the 23:18 POLLUTED_QT variant.
    """
    polluted = copy.deepcopy(items)
    one_a = _find(polluted, "1a")
    one_a["question_text"] = f"{EXPECTED_CLEAN_1A} {BRIDGING}"
    return polluted


# ---------------------------------------------------------------------------
# The primary replay test
# ---------------------------------------------------------------------------

def test_rescue_polluted_qt_replay(caplog) -> None:
    """Mutate 1a.qt to the 23:18 POLLUTED_QT pattern; pipeline should
    clean it up via rescue without touching any other field."""
    clean = _load_clean_items()
    polluted = _inject_pollution(clean)

    # Sanity: mutation actually injected the pollution.
    assert BRIDGING in _find(polluted, "1a")["question_text"]

    caplog.set_level(logging.INFO, logger="pipeline.segmenter")

    # Run the full chain on a separate copy of the CLEAN baseline too,
    # so we can compare post-pipeline state apples-to-apples (any Step 2
    # / merge drift is then cancelled out and only rescue's effect
    # shows up as a diff).
    clean_baseline = copy.deepcopy(clean)
    seg._attach_parent_stems(clean_baseline)
    seg._attach_parent_stems(polluted)

    # ----- Assertion 1: 1a.qt cleaned back to instruction-only --------
    post_1a = _find(polluted, "1a")
    assert post_1a["question_text"].rstrip() == EXPECTED_CLEAN_1A, (
        f"1a.qt NOT cleaned by rescue:\n  got: {post_1a['question_text']!r}\n"
        f"  expected: {EXPECTED_CLEAN_1A!r}"
    )

    # ----- Assertion 2: every other field on 1a untouched vs baseline -
    # Except question_text (that's the whole point).
    base_1a = _find(clean_baseline, "1a")
    for f in ("parent_stem", "student_answer", "working_steps",
              "marks", "page", "question_number"):
        assert post_1a.get(f) == base_1a.get(f), (
            f"1a.{f} drifted vs baseline: "
            f"got {post_1a.get(f)!r}, expected {base_1a.get(f)!r}"
        )

    # ----- Assertion 3: 1b/1c/1d byte-identical to baseline -----------
    for qn in ("1b", "1c", "1d"):
        post = _find(polluted, qn)
        base = _find(clean_baseline, qn)
        for f in ("question_text", "parent_stem", "student_answer",
                  "working_steps", "marks", "page", "question_number"):
            assert post.get(f) == base.get(f), (
                f"{qn}.{f} drifted between polluted and clean baseline: "
                f"got {post.get(f)!r}, expected {base.get(f)!r}"
            )

    # ----- Assertion 4: exactly 1 rescue_decision action=strip event for 1a
    strip_events: list[dict] = []
    for record in caplog.records:
        if record.name != "pipeline.segmenter":
            continue
        msg = record.getMessage()
        if not msg.startswith("rescue_decision "):
            continue
        try:
            payload = json.loads(msg[len("rescue_decision "):])
        except json.JSONDecodeError:
            continue
        if payload.get("action") == "strip":
            strip_events.append(payload)

    assert len(strip_events) == 1, (
        f"expected 1 rescue_decision strip event, got {len(strip_events)}: "
        f"{strip_events}"
    )
    evt = strip_events[0]
    assert _qn_key({"question_number": evt.get("qnum", "")}) == "1a", evt
    assert evt.get("n") == 1, evt
    assert BRIDGING.rstrip(".") in evt.get("sentences", ""), evt
    assert "1b.parent_stem" == evt.get("matched_in") or \
           "1(b).parent_stem" == evt.get("matched_in"), evt


# ---------------------------------------------------------------------------
# Standalone diagnostic entry point
# ---------------------------------------------------------------------------

def _main() -> int:
    """Ad-hoc replay mode: print the full before/after state and the
    rescue_decision log line, useful for debugging a captured production
    POLLUTED_QT payload."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("pipeline.segmenter").setLevel(logging.INFO)

    clean = _load_clean_items()
    polluted = _inject_pollution(clean)

    print("== before pipeline ==")
    for it in polluted:
        print(f"  {it['question_number']}.qt: {it['question_text']!r}")

    print("\n== running _attach_parent_stems ==")
    seg._attach_parent_stems(polluted)

    print("\n== after pipeline ==")
    for it in polluted:
        print(f"  {it['question_number']}.qt: {it['question_text']!r}")

    post_1a = _find(polluted, "1a")
    if post_1a["question_text"].rstrip() == EXPECTED_CLEAN_1A:
        print(f"\n✓ rescue cleaned 1a.qt: {post_1a['question_text']!r}")
        return 0
    print(
        f"\n✗ rescue FAILED to clean 1a.qt: "
        f"{post_1a['question_text']!r}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(_main())
