# A-Level Assistant Latest Full Retest Report

Generated: 2026-06-25 22:35 Asia/Shanghai  
API under test: `http://127.0.0.1:8013`  
Tester: Codex, current workspace state

## 1. Executive Verdict

Latest full-chain status: **not release-ready on all paths**.

Strong path:

- Official 9709 digital PDF path is currently healthy.

Regressed or risky paths:

- JPEG handwritten seed failed quality and latency targets on this run.
- HEIC no longer hangs, but first result narrowly missed the 30s target and still needs parent context.
- 10-image prepared batch failed the 60s pressure target and returned only 4 final questions despite 10 pages being prepared.
- Visual acceptance still fails because the runner expects nav tabs on `/`, while the product currently serves a landing page.

## 2. Local Verification

| Check | Result |
|---|---:|
| Python compile | pass |
| Backend focused tests | `60 passed, 1 skipped` |
| Frontend build | pass |
| Visual acceptance | fail |

Commands:

```bash
python -m py_compile api/effectiveness.py scripts/evaluate_upload_corpus.py pipeline/pipeline.py api/routes.py grader/solution_prompts.py
PYTHONPATH=. pytest -q test/test_effectiveness.py test/test_pipeline_streaming.py test/test_solution_prompts.py test/test_large_pdf_mode.py test/test_feedback_metrics_dashboard.py test/test_practice_orchestrator.py test/test_rescue_bridging.py
cd frontend && npm run build
cd frontend && npm run test:visual
```

## 3. End-to-End Benchmark Results

### 3.1 JPEG Quality Seed

Report:

- `reports/effectiveness/jpeg_full_retest_20260625_latest.json`

Result:

- `overall_status = fail`
- `overall_score = 65`

| Metric | Latest | Target | Status |
|---|---:|---:|---:|
| Upload success | 1.0 | >= 0.95 | pass |
| Parse success | 1.0 | >= 0.90 | pass |
| Readable question rate | 1.0 | >= 0.85 | pass |
| Image end-to-end P95 | 103.3s | <= 60s | fail |
| First question P95 | 51.7s | <= 30s | fail |
| Expected question recall | 1.0 | >= 0.95 | pass |
| Expected question order | 1.0 | >= 0.95 | pass |
| Correctness match | 0.75 | >= 0.90 | fail |
| Exact score match | 0.75 | >= 0.85 | fail |
| Recommendation relevance | 0.0 | >= 0.90 | fail |

Failure detail:

- `02-phone.jpeg`
  - Q11(i): correct, `2/2`.
  - Q11(ii): expected correct `4/4`, latest result `arithmetic_error`, `1/4`.
  - End-to-end: `103.3s`.
  - Recommendation topic: `statistics`, expected seed topic: `combined_mean`.

- `01-small.jpg`
  - Q11(a): correct, `5/5`.
  - Q11(b): correct, `2/2`.
  - End-to-end: `62.2s`.
  - Recommendation topic: `inverse_functions`, expected seed topic: `transformations`.

Interpretation:

- Recognition and question order are stable.
- The grading ensemble/verifier result is not stable enough on `02-phone.jpeg` Q11(ii).
- Latency regressed substantially versus the previous seed run.
- Recommendation topic relevance is too brittle for broad topic expectations.

### 3.2 Official PDF Quality Seed

Report:

- `reports/effectiveness/pdf_full_retest_20260625_latest.json`

Result:

- `overall_status = pass`
- `overall_score = 100`

| Metric | Latest | Target | Status |
|---|---:|---:|---:|
| Upload success | 1.0 | >= 0.95 | pass |
| Parse success | 1.0 | >= 0.90 | pass |
| Readable question rate | 1.0 | >= 0.85 | pass |
| PDF end-to-end P95 | 22.5s | <= 90s | pass |
| First question P95 | 1.0s | <= 30s | pass |
| Expected question recall | 1.0 | >= 0.95 | pass |
| Expected question order | 1.0 | >= 0.95 | pass |
| Correctness match | 1.0 | >= 0.90 | pass |
| Exact score match | 1.0 | >= 0.85 | pass |

Interpretation:

- The digital past-paper fallback is still working.
- 22 official questions were returned in correct order.
- All were correctly treated as unanswered with score `0`.
- No unreadable, recognition timeout, or fast-batch timeout occurred.

### 3.3 HEIC / iPhone Format

Report:

- `reports/effectiveness/heic_full_retest_20260625_latest.json`

Result:

- `overall_status = pass`
- `overall_score = 91`

| Metric | Latest | Target | Status |
|---|---:|---:|---:|
| Upload success | 1.0 | >= 0.95 | pass |
| Parse success | 1.0 | >= 0.90 | pass |
| Readable question rate | 1.0 | >= 0.85 | pass |
| Image end-to-end P95 | 30.2s | <= 60s | pass |
| First question P95 | 30.2s | <= 30s | fail |
| Hard timeout/unreadable count | 0 | 0 | pass |

Failure detail:

- Returned one question: `b`.
- Result: `missing_parent_context`, `needs_review=true`.
- This is a safe outcome for a bare sub-question, but it is still not a complete grading experience.

Interpretation:

- HEIC no longer hangs.
- It narrowly missed the first-question threshold by about `155ms`.
- The fixture still needs either parent-page upload or better cross-page context detection.

### 3.4 10-Image Prepared Fast Batch

Report:

- `reports/effectiveness/batch10_full_retest_20260625_latest.json`

Result:

- `overall_status = fail`
- `overall_score = 77`

| Metric | Latest | Target | Status |
|---|---:|---:|---:|
| Upload success | 1.0 | >= 0.95 | pass |
| Parse success | 1.0 | >= 0.90 | pass |
| Readable question rate | 1.0 | >= 0.85 | pass |
| First question P95 | 22.4s | <= 30s | pass |
| 10-image batch P95 | 89.5s | <= 60s | fail |
| Recognition timeout count | 0 | 0 | pass |
| Fast-batch timeout count | 0 | 0 | pass |

Timing split:

| Stage | Latest |
|---|---:|
| Prepare-upload total | 65.9s |
| Analyze after prepare | 23.6s |
| End-to-end total | 89.5s |

Prepared extraction detail:

- All 10 files returned `upload_id`.
- Prepared question counts per page: `1,1,1,1,1,1,2,1,2,1`.
- Final streamed questions: only 4.

Interpretation:

- Timeout protection works.
- The pressure target fails because prepare is slow.
- More importantly, the final merge/analyze stage only emitted 4 questions from 10 prepared pages. That suggests a prepared-result merge/grouping issue, not a model timeout.

### 3.5 Visual Acceptance

Command:

```bash
cd frontend && npm run test:visual
```

Result:

- `status = failed`
- Desktop and mobile both:
  - no horizontal overflow
  - upload text visible
  - nav text not visible

Interpretation:

- This is still the known landing/workbench acceptance mismatch.
- The visual runner expects nav tabs on `/`.
- The current product shows a landing/upload-first experience on `/`.

## 4. Latest Risk Register

| Priority | Issue | Evidence | Suggested Next Action |
|---|---|---|---|
| P0 | JPEG grading instability | `02-phone.jpeg` Q11(ii) changed to `arithmetic_error`, `1/4`; expected `4/4` | Debug statistics verifier / multi-agent consensus for combined standard deviation |
| P0 | 10-image prepared merge loses results | 10 pages prepared, final stream only 4 questions | Trace `_resolve_prepared` / `_merge_prepared_with_cross_context` and add regression test |
| P1 | JPEG latency regression | JPEG P95 `103.3s`, first question `51.7s` | Split recognition, grading, summary, recommendation timings in evaluator |
| P1 | HEIC parent context incomplete | `missing_parent_context` safe fallback | Add HEIC labeled parent-context fixtures |
| P1 | Recommendation topic brittleness | seed relevance `0.0` this run | Normalize topic hierarchy, allow parent/child topic equivalence |
| P2 | Visual runner route mismatch | `navTextVisible=false` | Split landing and workbench visual acceptance |

## 5. Bottom Line

The latest full retest shows the product is not uniformly green.

What is currently strong:

- Official digital PDF route.
- Timeout protection.
- HEIC no-hang behavior.
- Test/build baseline.

What needs immediate follow-up:

- Debug JPEG Q11(ii) grading regression.
- Debug 10-image prepared merge/result-loss.
- Add stage-level timing to separate model latency from evaluator/request overhead.

The next engineering iteration should not add new product surface area. It should focus on these two concrete regressions: **statistics grading correctness** and **prepared batch merge completeness**.
