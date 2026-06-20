# Rescue-bridging test fixtures

These fixtures cover the `_rescue_trailing_bridging` post-processing pass
planned for Step 3. Each fixture is self-contained — no VL calls, no real
PDF, just hand-constructed inputs reflecting patterns observed across the
8 determinism runs, the 23:18 user screenshot, and the 5 boundary cases
listed in Step 3 planning.

## Fixture structure

```jsonc
{
  "name":        "<short slug>",
  "category":    "normal | adversarial",
  "description": "<what this exercises>",
  "pre_items":   [ /* items as they appear AFTER _attach_parent_stems Step 1
                     (group_stems populated) but BEFORE Step 1.5 rescue and
                     Step 2 overwrites */ ],
  "group_stems": { "<numeric_prefix>": "<canonical stem>", ... },
  "expected_post_rescue": [ /* items after rescue, before Step 2 */ ],
  "expected_strip_log":   [ /* human-readable log lines rescue should emit */ ]
}
```

## Test contract

When Step 3 rescue code is written, a unit test file loads each fixture,
runs rescue on `pre_items` + `group_stems`, asserts:

1. `question_text` / `parent_stem` of each item matches `expected_post_rescue`
2. The set of log lines matches `expected_strip_log` (order-insensitive)

## Normal cases (5)

| File | Boundary case |
|---|---|
| `case_1_last_subpart.json` | Last sub-part in group has no "next item" — rescue must skip. |
| `case_2_single_bridging_sentence.json` | Classic 23:18 pattern — qt ends with 1 bridging sentence that appears in next item's ps. Strip. |
| `case_3_next_ps_no_match.json` | qt looks polluted but next ps doesn't contain the candidate. Rescue conservatively leaves qt alone. |
| `case_4_multiple_bridging_sentences.json` | qt swallowed 2 bridging sentences. Rescue strips them both, greedy-longest-first. |
| `case_5_cross_page_empty_next_ps.json` | Next item is on a later page, its VL-original ps is empty (not yet inherited). Fallback to `group_stems` for matching. |

## Adversarial cases (3)

| File | Guardrail tested | Phase |
|---|---|---|
| `adv_1_setup_opener_is_instruction.json` | Last sentence starts with "Given that..." (setup word) but IS the instruction (only sentence in qt). Rescue MUST NOT strip. | 1 (enabled) |
| `adv_2_hence_is_instruction.json` | Last sentence starts with connective "Hence" → it's an instruction. Rescue MUST NOT strip even if it superficially matches next ps. | 1 (enabled) |
| `adv_3_shift_by_one_prepend.json` | **TODO: Phase 2, not yet implemented.** Bridging is prepended to NEXT sub-part's qt (shift-by-one pattern from qwen-vl-max era). Symmetric rule: if first sentence of qt matches END of previous item's ps, strip from qt start. Decision 2026-04-19: defer to Phase 2, independent PR — current qwen3-vl-plus 8-run stress test observed 0× shift-by-one, the pattern is historical; Phase 1 keeps code path minimal. | 2 (skipped) |

## Running

```
pytest test/test_rescue_bridging.py -v
```

Phase 2 fixtures are skipped via `@pytest.mark.skip`. Enable them when Phase 2
PR lands.
