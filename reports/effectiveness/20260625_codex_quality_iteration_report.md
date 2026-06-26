# A-Level Assistant Quality Iteration Report

Generated: 2026-06-25  
Scope: second-pass quality benchmark and fixes after the full-chain reliability benchmark.

## 1. Objective

Continue from the previous benchmark without weakening the existing grading path:

- Do not replace the current grading route with a lower-quality base-model shortcut.
- Add quality instrumentation and tests on top of the current product logic.
- Use benchmark failures to drive fixes.
- Produce a repeatable report, not a one-off manual impression.

## 2. What Was Added

### 2.1 Labeled Quality Seed

Added:

- `reports/effectiveness/expectations_quality_seed_20260625.json`

This seed currently covers:

| Fixture | Coverage |
|---|---:|
| `01-small.jpg` | 2 handwritten questions: expected order, correctness, score, recommendation topic |
| `02-phone.jpeg` | 2 handwritten/iPhone-style questions: expected order, correctness, score, recommendation topic |
| `01-9709.pdf` | 22 official 9709 PDF subquestions: expected order, unanswered score state |

Total labeled seed:

- 26 expected questions.
- 3 ordered assets.
- 2 recommendation-topic checks.

This is intentionally small but strict. It avoids pretending that unlabeled model output is human-verified quality.

### 2.2 Effectiveness Metric Fixes

The benchmark layer now catches failures that were previously invisible:

| Metric | Why It Matters |
|---|---|
| `expected_question_recall_rate` | If expected Q2 is missing, it now counts as a failure instead of being silently skipped. |
| `expected_question_order_rate` | Official PDFs and multi-part questions must appear in student-readable order. |
| normalized question-number matching | `11a` and `11(a)` can match without hiding genuinely missing questions. |
| `ask_first.detected_topic` recommendation relevance | If the product correctly identifies the topic but waits for user confirmation before serving real questions, relevance can still be measured honestly. |

Regression tests were added in `test/test_effectiveness.py`.

### 2.3 Evaluator Summary Fix

Root cause:

- `scripts/evaluate_upload_corpus.py` parsed SSE events in reverse order.
- It accepted both `summary` and `done` as summary-like events.
- Since `done {}` is emitted after `summary`, valid page summaries were overwritten as `{}`.
- This made recommendation evaluation look worse and removed topic context.

Fix:

- `_summary_from_events` now only reads the `summary` event.
- Added regression coverage so `done {}` can no longer shadow the real summary.

### 2.4 Streaming Order Fix

Root cause:

- Non-fast streaming grading used worker concurrency and yielded `question` events in completion order.
- The official PDF fallback produced the correct extracted order, but output events could arrive as `1(a), 2, 1(b)`.
- This is confusing on the result page and makes official question papers feel broken.

Fix:

- Non-fast streaming now buffers completed question results and emits them in original extracted index order.
- Fast batch still emits completion-order results to preserve the large-batch speed path.

Regression:

- `test_non_fast_streaming_preserves_question_order` simulates Q2 finishing before Q1 and verifies output order remains Q1, Q2.

## 3. Re-Test Results

### 3.1 JPEG Quality Seed

Report:

- `reports/effectiveness/jpeg_quality_seed_after_summary_fix_20260625_codex.json`

Recomputed with current metrics and seed expectations:

| Metric | Value | Status |
|---|---:|---:|
| Upload success rate | 1.0 | pass |
| Parse success rate | 1.0 | pass |
| Readable question rate | 1.0 | pass |
| Image P95 | 44.2s | pass |
| First question P95 | 22.1s | pass |
| Expected question recall | 1.0 | pass |
| Expected question order | 1.0 | pass |
| Correctness match | 1.0 | pass |
| Exact score match | 1.0 | pass |
| Recommendation relevance | 1.0 | pass |

Final seed verdict:

- `overall_status = pass`
- `overall_score = 100`

### 3.2 PDF Quality Seed

Report:

- `reports/effectiveness/pdf_quality_order_after_fix_20260625_codex.json`

Results:

| Metric | Value | Status |
|---|---:|---:|
| Upload success rate | 1.0 | pass |
| Parse success rate | 1.0 | pass |
| Readable question rate | 1.0 | pass |
| PDF P95 | 24.3s | pass |
| First question P95 | 1.1s | pass |
| Expected question recall | 1.0 | pass |
| Expected question order | 1.0 | pass |
| Correctness match | 1.0 | pass |
| Exact score match | 1.0 | pass |
| Hard failures | 0 | pass |

Final seed verdict:

- `overall_status = pass`
- `overall_score = 100`

## 4. Important Interpretation

This iteration does not prove broad grading accuracy yet.

It does prove that the benchmark now refuses several previously dangerous false positives:

- Missing expected questions no longer disappear from quality scoring.
- PDF question order is measurable and fixed for the tested 9709 fixture.
- SSE summary extraction no longer drops topic context.
- Recommendation relevance can distinguish topic detection from real question serving.

This is a stronger foundation for the 100-question human audit because future failures will show up as measurable red cells instead of being hidden by evaluator gaps.

## 5. Files Changed In This Iteration

- `api/effectiveness.py`
- `scripts/evaluate_upload_corpus.py`
- `pipeline/pipeline.py`
- `test/test_effectiveness.py`
- `test/test_pipeline_streaming.py`
- `reports/effectiveness/expectations_quality_seed_20260625.json`

## 6. Commands Run

```bash
PYTHONPATH=. pytest -q test/test_effectiveness.py
PYTHONPATH=. pytest -q test/test_pipeline_streaming.py test/test_effectiveness.py
PORT=8012 python server.py
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-pdf --api-base http://127.0.0.1:8012 --repeat 1 --max-concurrency 1 --expectations reports/effectiveness/expectations_quality_seed_20260625.json --track-events --output reports/effectiveness/pdf_quality_order_after_fix_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-jpeg --api-base http://127.0.0.1:8012 --repeat 1 --max-concurrency 1 --expectations reports/effectiveness/expectations_quality_seed_20260625.json --track-events --output reports/effectiveness/jpeg_quality_seed_after_summary_fix_20260625_codex.json
```

## 7. Next Iteration Recommendations

P0: Expand from seed quality to a 100-question labeled benchmark.

- 30 Past Paper questions with official mark scheme expected score.
- 30 teacher/custom homework questions.
- 20 cross-page/parent-stem questions.
- 20 blank, low-clarity, answer-only, and partial-working edge cases.

P0: Add explanation-quality checks.

- Current seed validates extraction, order, score, and recommendation topic.
- It should next validate `solution_text` presence, structure, specificity, and whether uncertain cases set `needs_review=true`.

P1: Split recommendation metrics.

- Topic-detection relevance: `ask_first.detected_topic`.
- Real-question serving: non-empty `recommendations[]` with valid `question_id`.
- Practice-start conversion: frontend event level.

P1: Add HEIC quality fixtures.

- The previous reliability fix showed one HEIC sample completing.
- Quality should now label at least 5 iPhone HEIC uploads for recall, parent context, and needs-review behavior.

P1: Keep fast batch and non-fast quality paths distinct.

- Non-fast path should favor ordered, interpretable output.
- Fast batch should keep speed and timeout protection, but its result ordering should be separately tested at the UI layer.
