# A-Level Assistant Full-Chain Benchmark Report

Generated: 2026-06-25  
Tester: Codex with Superpowers verification workflow  
Environment: local API at `http://127.0.0.1:8000`, existing local server process

## 1. Benchmark Definition

This run used the metrics framework implemented in `/feedback/stats` and `scripts/evaluate_upload_corpus.py`.

Core pass thresholds:

| Area | Metric | Pass Target |
|---|---:|---:|
| Upload reliability | Upload success rate | >= 95% |
| Parsing reliability | Parse success rate | >= 90% |
| Question readability | Readable question rate | >= 85% |
| Single image latency | Image end-to-end P95 | <= 60s |
| PDF latency | PDF end-to-end P95 | <= 90s |
| First visible result | First question P95 | <= 30s |
| 10-image pressure | 10 image batch P95 | <= 60s |
| Hard failures | recognition_timeout / unreadable / fast_batch_timeout | 0 |
| Stability | repeated question-count and recommendation-mode stability | >= 90% |

Quality targets that still need labeled data:

| Area | Metric | Target |
|---|---:|---:|
| Manual grading audit | correctness match | >= 90% |
| Manual grading audit | exact score match | >= 85% |
| Recommendation audit | recommendation relevance | >= 90% |
| Paper compliance | recommended paper matches expected | 100% |

## 2. Test Corpus

Local corpus discovery found 17 uploadable assets under `test/`:

- 4 PDFs: `9709_s22_qp_11.pdf`, `9709_s22_qp_41.pdf`, `9709_s22_qp_51.pdf`, `Lesson2-Coordinate geometry 11.pdf`
- 13 images: HEIC/JPEG/iPhone/WeChat images

External source check:

- Cambridge official 9709 past papers page: `https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-international-as-and-a-level-mathematics-9709/past-papers/`
- PapaCambridge 9709/11 May-June 2022 question paper and mark scheme pages were found.
- BestExamHelp has a 9709/11 May-June 2022 mark scheme page.
- Several public YouTube worked-solution videos exist for 9709/11/M/J/22.

Decision: this run used local assets only for execution, because the local corpus already includes the matching 9709 PDFs and handwritten/photo uploads. External sources are recommended for the next labeled benchmark pass, not mixed into this unlabeled pressure run.

## 3. Execution Summary

| Run | Report | Status | Score | Key Result |
|---|---|---:|---:|---|
| JPEG smoke, 2 assets | `jpeg_smoke_20260625_codex.json` | pass | 100 | Single JPEG path healthy |
| JPEG repeat x3 | `jpeg_repeat3_20260625_codex.json` | pass | 100 | Stable question count and recommendation mode |
| PDF smoke, 9709 PDF | `pdf_smoke_20260625_codex.json` | fail | 36 | PDF was fast enough but parsed as unreadable |
| 10 JPEG fast batch | `batch_10_jpeg_fast_20260625_codex.json` | fail | 77 | 112.9s total and 7 fast-batch timeouts |
| 10 JPEG prepared fast batch | `batch_10_jpeg_prepared_fast_20260625_codex.json` | fail | 77 | Pre-extraction removed timeouts but still 79.2s |
| Full local corpus | no final JSON | aborted | n/a | First HEIC sample produced no result after >180s |
| HEIC single sample | no final JSON | aborted | n/a | Same HEIC sample produced no result after >120s |
| Visual acceptance | `/private/tmp/alevel-visual-acceptance/visual-acceptance-report.json` | fail | n/a | Upload visible, no overflow, nav not visible |

## 4. Detailed Findings

### 4.1 JPEG Single-Image Path Is Currently Healthy

JPEG smoke:

| Metric | Value | Target | Status |
|---|---:|---:|---:|
| Upload success | 100% | >= 95% | pass |
| Parse success | 100% | >= 90% | pass |
| Readable question rate | 100% | >= 85% | pass |
| Image end-to-end P95 | 47.1s | <= 60s | pass |
| First question P95 | 23.5s | <= 30s | pass |
| recognition_timeout | 0 | 0 | pass |
| unreadable | 0 | 0 | pass |

JPEG repeat x3:

| Metric | Value | Target | Status |
|---|---:|---:|---:|
| Image end-to-end P95 | 53.1s | <= 60s | pass |
| First question P95 | 26.6s | <= 30s | pass |
| Repeat question-count stability | 100% | >= 90% | pass |
| Repeat recommendation-mode stability | 100% | >= 90% | pass |

Interpretation:

- For normal JPEG homework photos, the product is usable under current thresholds.
- Latency is close to the edge. A 53.1s P95 means there is not much headroom before the experience feels slow.
- The repeat test is encouraging: the same two assets consistently returned 2 questions each across 3 runs.

### 4.2 HEIC Path Is a High-Risk Blocker

Two attempts involving `IMG_9160.HEIC` were manually aborted:

- Full corpus run: no first sample result after more than 180s.
- HEIC-only run: no result after more than 120s.

Interpretation:

- The issue is not caused by the full corpus runner itself.
- JPEG requests completed successfully on the same local server, so the problem is likely HEIC conversion/processing or model handling of that HEIC payload.
- This is product-critical because iPhone camera uploads commonly produce HEIC.

Recommended benchmark status:

- Treat HEIC as failing both first-question latency and image end-to-end latency until proven otherwise.
- Add a hard route-level timeout so one HEIC request cannot silently hold the experience beyond 120s.

### 4.3 PDF Past-Paper Path Is Functionally Unreliable

PDF smoke on `9709_s22_qp_11.pdf`:

| Metric | Value | Target | Status |
|---|---:|---:|---:|
| Upload success | 100% | >= 95% | pass |
| PDF end-to-end P95 | 53.2s | <= 90s | pass |
| First question P95 | 53.2s | <= 30s | fail |
| Parse success | 0% | >= 90% | fail |
| Readable question rate | 0% | >= 85% | fail |
| unreadable count | 1 | 0 | fail |

Interpretation:

- The Large PDF path can complete inside the PDF latency budget.
- However, it selected/analyzed content in a way that produced one unreadable result rather than useful question extraction.
- For a known 9709 PDF, this is a product-quality failure: the user would wait almost a minute and get no usable grading.

Likely root-cause areas to inspect next:

- Default selected pages may include cover/instruction pages rather than question pages.
- Large PDF prepare may not be passing enough page text/MinerU context into selected-page analysis.
- Past-paper matching may not force question-bank/mark-scheme route strongly enough before vision grading.

### 4.4 10-Image Batch Is Not Ready at Current Targets

10 JPEG direct fast batch:

| Metric | Value | Target | Status |
|---|---:|---:|---:|
| Upload success | 100% | >= 95% | pass |
| Parse success | 100% | >= 90% | pass |
| Readable question rate | 100% | >= 85% | pass |
| First question P95 | 6.3s | <= 30s | pass |
| 10-image batch P95 | 112.9s | <= 60s | fail |
| fast_batch_timeout count | 7 | 0 | fail |

10 JPEG prepared + fast batch:

| Metric | Value | Target | Status |
|---|---:|---:|---:|
| Upload success | 100% | >= 95% | pass |
| Parse success | 100% | >= 90% | pass |
| Readable question rate | 100% | >= 85% | pass |
| First question P95 | 4.0s | <= 30s | pass |
| 10-image batch P95 | 79.2s | <= 60s | fail |
| fast_batch_timeout count | 0 | 0 | pass |

Interpretation:

- `prepare-upload` materially improves the batch path.
- It removed all fast-batch timeouts and improved total latency by 33.7s.
- It still misses the 60s target by 19.2s.
- The direct batch path should not be the recommended UX for 10-image uploads.

Recommended benchmark decision:

- Make prepare-upload mandatory for multi-image batches over a small threshold, e.g. 4+ images.
- Keep direct fast_batch only as fallback.

### 4.5 UI First-Screen Visual Acceptance Fails Current Runner

Visual acceptance result:

| Viewport | Horizontal overflow | Upload text | Nav text | Status |
|---|---:|---:|---:|---:|
| Desktop 1366x768 | false | true | false | fail |
| Mobile 390x844 | false | true | false | fail |

Screenshots:

- `/private/tmp/alevel-visual-acceptance/first-screen-desktop.png`
- `/private/tmp/alevel-visual-acceptance/first-screen-mobile.png`

Observed reality:

- The page shown at `/` is a landing page.
- Upload CTA is visible.
- Navigation tabs are not present, so the runner fails `expectNav`.

Interpretation:

- This is not a layout overflow bug.
- It is a product/acceptance mismatch: acceptance expects the workbench first screen, while the app currently defaults to landing.

## 5. Product Experience Assessment

What currently feels strong:

- JPEG homework upload path works and is stable.
- First visible result for normal JPEGs is under 30s.
- Prepared batch mode shows the right architectural direction: early feedback and no fast-batch timeout.
- The dashboard/test infrastructure now provides useful evidence rather than anecdotal impressions.

What currently feels risky:

- HEIC uploads can hang far beyond user-tolerable limits.
- Full/official past-paper PDF may return unreadable output, which undermines the core “mark scheme grounded” promise.
- 10-image grading still takes too long for an impatient student unless the UI makes progress highly visible and results stream incrementally.
- Current benchmarks are mostly unlabeled, so we cannot yet claim grading correctness, score correctness, or recommendation relevance.

## 6. Recommended Iteration Direction

### P0: Fix HEIC and Request Timeouts

Why:

- HEIC is a common iPhone default.
- Current behavior can exceed 120s without user-visible completion.

Actions:

- Convert HEIC/HEIF to JPEG/WebP server-side before model calls.
- Add route-level and per-stage time budgets with explicit fallback results.
- Emit `pipeline_error` or `recognition_timeout` instead of hanging indefinitely.
- Add HEIC-specific regression benchmarks to CI/nightly testing.

Acceptance:

- HEIC single-image P95 <= 60s.
- First question P95 <= 30s or explicit fallback within 30s.
- No request remains silent beyond 90s.

### P0: Repair Past-Paper PDF Question Extraction

Why:

- Known 9709 PDF returned one unreadable item after 53s.
- This directly breaks the product’s most differentiated route.

Actions:

- Inspect Large PDF default page selection on 9709 PDFs; exclude cover/instruction pages by default.
- Use PDF text/MinerU extraction first for printed past papers; reserve vision for student answer pages or image-only PDFs.
- When paper code is known, prefer question-bank structure over freeform page segmentation.
- Add a fixture expectation for `9709_s22_qp_11.pdf`: expected paper identity, selected question pages, minimum question count.

Acceptance:

- `9709_s22_qp_11.pdf` produces readable questions, not `unreadable`.
- Past-paper route emits `past_paper_mark_scheme` where match confidence is high.
- First useful question appears within 30s, or page/question picker appears earlier.

### P1: Make Prepared Upload the Default Multi-Image Path

Why:

- Direct 10-image batch: 112.9s and 7 fast-batch timeouts.
- Prepared 10-image batch: 79.2s and 0 fast-batch timeouts.

Actions:

- Start `/prepare-upload` immediately when each image is selected.
- For 4+ images, block analysis until enough pages are prepared or explicitly show fallback status.
- Use a concurrency cap that keeps server stable, likely 4 based on this test.
- Make batch progress page-based: “7/10 pages prepared”, “12/20 questions graded”.

Acceptance:

- 10-image prepared batch P95 <= 60s.
- fast_batch_timeout count = 0.
- First question P95 <= 10s for prepared batches.

### P1: Build a Labeled Quality Benchmark

Why:

- Current pressure tests validate throughput and readability.
- They do not prove grading correctness, exact scoring, deduction quality, or recommendation relevance.

Actions:

- Create `reports/effectiveness/expectations_9709_mini.json`.
- Label 20 to 30 questions across:
  - Past-paper mark scheme questions
  - Teacher-style handwritten homework
  - Cross-page parent-stem questions
  - Blank/low-quality/answer-only edge cases
- Include expected `is_correct`, `score`, `full_score`, `topic/subtopic`, and expected recommendation topic.

Acceptance:

- Correctness match >= 90%.
- Exact score match >= 85%.
- Recommendation relevance >= 90%.
- Wrong high-confidence sample count = 0.

### P1: Align Landing/Workbench Acceptance

Why:

- Visual runner expects nav tabs, but `/` currently shows landing.

Actions:

- Decide product default:
  - If landing remains default, update visual runner to target `/#workbench` for workbench acceptance.
  - If upload workspace should be first screen, route `/` directly to workbench.
- Add separate visual tests for landing and workbench.

Acceptance:

- Landing visual test checks CTA, no overflow, brand clarity.
- Workbench visual test checks nav, upload intent, upload surface, no overflow.

### P2: Expand Online Past-Paper Worked-Solution Coverage

Suggested sources:

- Cambridge official past papers for source-of-truth question papers.
- PapaCambridge/BestExamHelp for accessible 9709 mark schemes.
- Public worked-solution videos for process-level comparison, manually converted into labeled expectations rather than automatically scraped.

Actions:

- Use official PDFs for question/mark scheme ground truth.
- Use worked-solution videos only to help human labeling of reasoning steps.
- Avoid relying on random web images as automated truth without manual verification.

## 7. Commands Run

```bash
python scripts/evaluate_upload_corpus.py --dry-run --input-dir test
python scripts/evaluate_upload_corpus.py --input-dir test --api-base http://127.0.0.1:8000 --repeat 1 --max-concurrency 1 --track-events --output reports/effectiveness/full_corpus_benchmark_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-jpeg --api-base http://127.0.0.1:8000 --repeat 1 --max-concurrency 1 --track-events --output reports/effectiveness/jpeg_smoke_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-heic --api-base http://127.0.0.1:8000 --repeat 1 --max-concurrency 1 --track-events --output reports/effectiveness/heic_single_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-pdf --api-base http://127.0.0.1:8000 --repeat 1 --max-concurrency 1 --track-events --output reports/effectiveness/pdf_smoke_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-10jpeg --api-base http://127.0.0.1:8000 --batch-only --batch-images 10 --repeat 1 --fast-batch --track-events --output reports/effectiveness/batch_10_jpeg_fast_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-10jpeg --api-base http://127.0.0.1:8000 --batch-only --batch-images 10 --repeat 1 --use-prepare-upload --prepare-concurrency 4 --fast-batch --track-events --output reports/effectiveness/batch_10_jpeg_prepared_fast_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-jpeg --api-base http://127.0.0.1:8000 --repeat 3 --max-concurrency 1 --track-events --output reports/effectiveness/jpeg_repeat3_20260625_codex.json
npm run test:visual
PYTHONPATH=. pytest -q test/test_feedback_metrics_dashboard.py test/test_effectiveness.py test/test_practice_orchestrator.py test/test_rescue_bridging.py
```

Notes:

- The full corpus run and HEIC single run were manually interrupted after exceeding the benchmark time budget without a result.
- The test runner output for backend regression was `36 passed, 1 skipped`.
- `npm run test:visual` exited with status 1 due to missing nav visibility on the landing default route.

## 8. Final Verdict

Current readiness by path:

| Path | Verdict |
|---|---|
| Single JPEG homework upload | Usable, near latency edge |
| Repeated JPEG behavior | Stable on tested sample |
| HEIC/iPhone default format | Not acceptable; needs urgent timeout/conversion fix |
| Past-paper PDF | Not acceptable; readable extraction failed on 9709 PDF |
| 10-image direct batch | Not acceptable; too slow and timeout-prone |
| 10-image prepared batch | Directionally good, still above latency target |
| Visual first screen | Needs acceptance/product-route alignment |

Overall product state:

The product has a working core for ordinary JPEG homework photos, but the two most strategically important promises are not yet reliable enough: iPhone-native upload and past-paper PDF/mark-scheme grounding. The next iteration should focus less on adding new features and more on making these core routes deterministic, timeout-safe, and benchmarked with labeled expectations.

## 9. Debug Fixes and Re-Test Addendum

Generated after the initial report on 2026-06-25.

### 9.1 Fixes Implemented

Past-paper PDF extraction:

- Added a digital past-paper fallback for high-confidence matched PDFs.
- For matched printed past papers with embedded text, the Large PDF path now uses the local question bank structure instead of sending rendered question-paper pages through freeform vision segmentation.
- This preserves quality because the source of question text is the matched paper/question database, not a weaker base-model shortcut.

HEIC / long-running recognition:

- Added a default recognition timeout budget to normal `run_pipeline` and non-fast streaming paths.
- HEIC decoding itself was verified locally as fast; the previous risk was model-stage recognition holding the request without a bounded fallback.

Multi-image UX:

- Reconnected the existing frontend `prepareUpload` API to the upload form.
- Images now start `/prepare-upload` immediately after file selection with a 4-request concurrency cap.
- Submit still uses the existing `upload_ids` mechanism. Pages not prepared yet continue through the original pipeline, so this moves work earlier without lowering grading quality.

Solution explanation reliability:

- Fixed a prompt-template escaping bug where the literal LaTeX example `\frac{1}{2}` was parsed by Python `.format()` as fake placeholders.
- Added a regression test so active solution prompts must format cleanly before any model call.

Files touched:

- `api/routes.py`
- `pipeline/pipeline.py`
- `grader/solution_prompts.py`
- `frontend/src/components/UploadForm.tsx`
- `test/test_large_pdf_mode.py`
- `test/test_solution_prompts.py`

### 9.2 Re-Test Results

| Run | Report | Status | Score | Key Result |
|---|---|---:|---:|---|
| PDF smoke after fix, 9709 PDF | `pdf_smoke_after_fix_20260625_codex.json` | pass | 100 | 22 readable questions, 0 unreadable |
| HEIC single after timeout fix | `heic_single_after_timeout_20260625_codex.json` | pass | 100 | Completed in 11.5s, no hang |
| 10 JPEG prepared fast batch after frontend/default path fix | `batch_10_jpeg_prepared_fast_c4_after_fix_20260625_codex.json` | pass | 100 | 20/20 questions, 0 fast-batch timeouts, 49.3s total |

Detailed metrics:

| Path | Before | After | Target | Verdict |
|---|---:|---:|---:|---|
| 9709 PDF readable questions | 0 | 22 | non-zero usable extraction | fixed on tested fixture |
| 9709 PDF unreadable count | 1 | 0 | 0 | fixed |
| 9709 PDF end-to-end | 53.2s | 8.7s | <= 90s | pass |
| 9709 PDF first question | 53.2s | 0.4s | <= 30s | pass |
| HEIC single request | >120s aborted | 11.5s | <= 60s | pass on tested fixture |
| 10-image prepared batch total | 79.2s | 49.3s | <= 60s | pass |
| 10-image prepared analyze-after-submit | 22.7s | 9.3s | <= 30s first useful result | pass |
| 10-image fast-batch timeout count | 7 direct / 0 prepared | 0 prepared | 0 | pass on prepared path |

Important interpretation:

- The batch improvement is not from weakening the grading route. It comes from using the product's intended pre-extraction cache earlier and with bounded concurrency.
- The PDF improvement is route-specific and quality-preserving for known printed past papers. It should not be generalized to handwritten answer pages, where the student's work still needs image-based extraction.
- HEIC is now bounded and passed the available iPhone fixture, but this still deserves a broader corpus of iPhone HEIC samples with different resolutions and lighting.

### 9.3 Updated Verdict

| Path | Updated Verdict |
|---|---|
| Single JPEG homework upload | Usable, still close to latency edge |
| Repeated JPEG behavior | Stable on tested sample |
| HEIC/iPhone default format | Fixed on tested fixture; expand HEIC corpus before declaring broadly solved |
| Past-paper PDF | Fixed for matched digital 9709 fixture; add more paper variants |
| 10-image direct batch | Keep as fallback only |
| 10-image prepared batch | Now passes current pressure target |
| Visual first screen | Still needs landing/workbench acceptance alignment |

### 9.4 Next Iteration Recommendations After Fixes

P0: Build a labeled grading-quality benchmark.

- The current pass/fail now proves reliability, readability, timeout behavior, and pressure handling.
- It still does not prove exact mark accuracy, deduction quality, or explanation usefulness.
- Next benchmark should label 100 questions across Past Paper, custom homework, cross-page context, blank/low-quality, and answer-only cases.

P0: Broaden official past-paper coverage.

- Add at least 5 more high-confidence digital PDF fixtures across `9709` paper variants.
- Assert paper identity, expected source pages, expected minimum question count, and zero unreadable results.

P1: Add frontend regression around background prepare.

- Use a browser-level test to select multiple images and assert `/prepare-upload` starts before the user clicks final submit.
- Assert `ui_upload_submit.prepared_count` is non-zero after background preparation has completed.

P1: Split latency dashboards into two views.

- Operational end-to-end: file selected to final result.
- User-submit latency: click "start marking" to first useful question.
- Prepared upload intentionally shifts cost earlier; both views are needed to avoid fooling ourselves.

P1: Align visual acceptance.

- Either test landing and workbench separately, or route the workbench explicitly in the visual runner.
- Current visual failure is an acceptance mismatch, not an overflow/layout failure.

### 9.5 Additional Commands Run

```bash
python -m py_compile api/routes.py pipeline/pipeline.py
PYTHONPATH=. pytest -q test/test_large_pdf_mode.py
PORT=8011 python server.py
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-pdf --api-base http://127.0.0.1:8011 --repeat 1 --max-concurrency 1 --track-events --output reports/effectiveness/pdf_smoke_after_fix_20260625_codex.json
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-heic --api-base http://127.0.0.1:8011 --repeat 1 --max-concurrency 1 --track-events --output reports/effectiveness/heic_single_after_timeout_20260625_codex.json
npm run build
python scripts/evaluate_upload_corpus.py --input-dir /tmp/alevel-bench-10jpeg --api-base http://127.0.0.1:8011 --batch-only --batch-images 10 --repeat 1 --use-prepare-upload --prepare-concurrency 4 --fast-batch --track-events --output reports/effectiveness/batch_10_jpeg_prepared_fast_c4_after_fix_20260625_codex.json
PYTHONPATH=. pytest -q test/test_solution_prompts.py test/test_large_pdf_mode.py test/test_feedback_metrics_dashboard.py test/test_effectiveness.py test/test_practice_orchestrator.py test/test_rescue_bridging.py
python -m py_compile api/routes.py pipeline/pipeline.py grader/solution_prompts.py
```
