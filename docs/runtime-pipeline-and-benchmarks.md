# Runtime Pipeline And Benchmarks

这份文档是当前后端实现路径的主说明。它把上传链路、fast-first 批改策略、OCR/切题、Mark Scheme、verifier、推荐练习、反馈埋点和 benchmark 结果放在一处，方便后续开发、复测和上线前审查。

## 一句话总览

A-Level Assistant 不是“上传图片后等一个大模型回答”的系统。当前实现是一条可观测的学习闭环：

```text
Upload
  -> optional prepare/cache
  -> streaming analyze
  -> OCR + vision segmentation
  -> paper/mark-scheme context
  -> fast-first grading
  -> deterministic verification
  -> SSE question/summary events
  -> explanation/practice recommendation
  -> feedback + effectiveness metrics
```

设计取舍是：**先返回可信首轮结果，但不把不确定题伪装成确定结论。** 慢题、低置信题、识别超时题和空白/答案页-only 样本应显示为 `needs_review` 或 timeout placeholder。

## 最新主流程图

```mermaid
flowchart TD
  U["Student uploads image / PDF"] --> F["React UploadForm"]
  F --> P{"PDF or image?"}

  P -->|"image / multi-image"| C["/prepare-upload<br/>content hash cache<br/>in-flight dedupe"]
  C -->|"upload_ids"| S["/analyze-homework-stream"]
  P -->|"large PDF"| L["/large-pdf/prepare<br/>thumbnail + selected pages"]
  L --> S

  S --> R{"fast-first?"}
  R -->|"image default"| I["page-level recognition<br/>parallel where possible"]
  R -->|"non-fast / review path"| G["quality-first recognition"]

  I --> O["Mathpix OCR evidence<br/>local tesseract fallback"]
  G --> O
  O --> Q{"OCR guard"}
  Q -->|"question/task language"| H["OCR hint to segmenter"]
  Q -->|"handwriting-only / weak OCR"| A["audit evidence only"]

  H --> X["structured question JSON"]
  A --> X
  X --> M["paper resolver<br/>mark scheme context"]
  M --> B["first-pass grading"]
  B --> V["deterministic verifiers<br/>SymPy / statistics / probability / simplification"]
  V --> D{"risk remains?"}
  D -->|"yes"| W["review / multi-agent path<br/>or needs_review"]
  D -->|"no"| E["SSE question event"]
  W --> E

  E --> T{"pending slow questions?"}
  T -->|"short window passes"| N["timeout placeholder<br/>needs_review=true"]
  T -->|"all ready"| Z["summary event"]
  N --> Z
  Z --> K["practice recommendation"]
  K --> J["feedback/track + effectiveness dashboard"]
```

## Frontend Entry Points

| UI surface | Main code | Runtime behavior |
|---|---|---|
| Upload shell | `frontend/src/components/UploadForm.tsx` | Select images/PDF, prepare uploads, submit to streaming analyze |
| Large PDF | `frontend/src/api/largePdfClient.ts` | Prepare PDF, show thumbnails, submit selected pages |
| Result page | `frontend/src/components/QuestionCard.tsx`, `PageSummary.tsx` | Render streamed question results, confidence, feedback, explanations |
| Practice loop | `frontend/src/components/practice/PracticeRecommendations.tsx` | Ask-first or auto recommendations from questionbank |
| Feedback events | `frontend/src/api/client.ts`, `api/feedback.py` | Track UI funnel and benchmark metadata |

Development server:

```bash
python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

Vite proxies upload and practice routes to `localhost:8000`.

## Backend Runtime Paths

### 1. Image Upload

Primary files:

- `api/routes.py`
- `api/upload_cache.py`
- `pipeline/pipeline.py`
- `pipeline/segmenter.py`
- `utils/image_utils.py`

Path:

```text
UploadForm
  -> /prepare-upload
  -> upload_cache stores extracted questions by upload_id/content hash
  -> /analyze-homework-stream with fast_batch=true
  -> run_pipeline_streaming(..., fast_batch=True)
```

Important behavior:

- Single image benchmark now matches the real product path by sending `fast_batch=true`.
- `api/upload_cache.py` adds content hash cache and in-flight dedupe.
- Prepared upload results are reused when healthy; recognition timeout cache entries force full fallback instead of silently dropping pages.
- Fast-first mode returns question events as soon as they are ready.
- After the first question has been emitted, pending slow questions get only a short extra window before returning `needs_review` timeout placeholders.

Key knobs:

| Setting | Default | Purpose |
|---|---:|---|
| `FAST_BATCH_PREPARE_TIMEOUT_SECONDS` | `120` | Page recognition budget |
| `FAST_BATCH_QUESTION_TIMEOUT_SECONDS` | `120` | Hard total grading budget before any result |
| `FAST_BATCH_AFTER_FIRST_QUESTION_TIMEOUT_SECONDS` | `25` | Extra wait after first usable question |
| `FAST_BATCH_PREPARE_MAX_WORKERS` | `10` | Prepare/upload recognition concurrency |
| `FAST_BATCH_MAX_WORKERS` | `16` | Fast-first question grading concurrency |

### 2. Large PDF

Primary files:

- `api/routes.py`
- `frontend/src/api/largePdfClient.ts`
- `frontend/src/components/UploadForm.tsx`

Path:

```text
PDF upload
  -> /large-pdf/prepare
  -> thumbnail + default page selection
  -> /large-pdf/{pdf_id}/analyze-stream
  -> run_pipeline_streaming on selected rendered pages
```

The frontend keeps PDF selection explicit, because a large past paper often contains covers, blank pages, mark schemes or answer-only pages.

### 3. OCR And Segmentation

Primary files:

- `pipeline/segmenter.py`
- `router/models.py`
- `utils/image_utils.py`

Current OCR strategy:

- Mathpix is an evidence layer, not the structure authority.
- OCR text enters the segmenter prompt only when the OCR guard sees task language.
- Handwriting-only/formula-only OCR is retained as audit evidence.
- Local tesseract remains a weak fallback and page-header probe.

This prevents handwritten work from overwriting the actual question structure. See [Model Routing And OCR Chain](model-routing-and-ocr-chain.md).

### 4. Paper And Mark Scheme Context

Primary files:

- `api/paper_resolver.py`
- `questionbank/pastpaper_matcher.py`
- `questionbank/mark_scheme.py`
- `pipeline/pipeline.py`

Path:

```text
upload intent + file/header/page clues
  -> paper resolver
  -> questionbank / mark scheme lookup
  -> attach mark_scheme_context per question
  -> grader uses context when confidence is sufficient
```

The resolver should never invent certainty. Medium/low confidence flows should ask for confirmation or fall back to open grading.

### 5. Grading And Verification

Primary files:

- `grader/grader.py`
- `pipeline/pipeline.py`
- `verifier/statistics_verifier.py`
- `verifier/math_verifier.py`
- `verifier/probability_verifier.py`
- `verifier/simplification_verifier.py`

Current strategy:

- First-pass grading is fast and streamed.
- Risky cases use review/multi-agent paths when enabled.
- Deterministic verifiers can correct or flag LLM grading for closed-form math.
- `needs_review=true` is preferred over a confident wrong answer.

Fast-first mode deliberately disables inline solution generation and heavy summary LLM calls; deeper explanation remains available through follow-up actions.

### 6. Practice Recommendation

Primary files:

- `api/practice_orchestrator.py`
- `questionbank/database.py`
- `frontend/src/components/practice/PracticeRecommendations.tsx`

Inputs:

- `priority_topics`
- `knowledge_tags_summary`
- wrong/unanswered questions
- upload intent and paper context

Outputs:

- `auto`: enough topic/paper confidence, return real questionbank items.
- `ask_first`: topic is plausible but needs student confirmation.
- `none`: insufficient signal.

The evaluator accepts narrow topic aliases such as `sigma_notation` within the statistics group to avoid false negative recommendation scores.

## Telemetry And Effectiveness Metrics

Primary files:

- `api/feedback.py`
- `api/effectiveness.py`
- `scripts/evaluate_upload_corpus.py`
- `scripts/build_jpeg_benchmark_corpus.py`

Important events/metrics:

| Metric | Meaning |
|---|---|
| `upload_success_rate` | Request completed successfully |
| `parse_success_rate` | At least one readable question extracted |
| `readable_question_rate` | Question-level readable/non-timeout rate |
| `first_question_p95_ms` | User-facing first result latency |
| `image_end_to_end_p95_ms` | Full image session latency |
| `sse_first_event_p95_ms` | Transport/proxy responsiveness |
| `segmentation_done_p95_ms` | Recognition/cutting latency |
| `first_grading_after_segmentation_p95_ms` | First grading latency after segmentation |
| `summary_after_first_question_p95_ms` | How long slow remaining questions delay the page |
| `recognition_timeout_count` | Recognition hard failures |
| `fast_batch_timeout_count` | Question grading hard fallbacks |
| `marked_correctness_match_rate` | Labeled quality benchmark correctness |
| `recommendation_relevance_rate` | Labeled recommendation topic relevance |

## Current Benchmark Status

Latest focused reports:

- `reports/effectiveness/20260626_fast_first_single_image_report.md`
- `reports/effectiveness/20260626_jpeg30_phase_benchmark_report.md`
- `reports/effectiveness/20260626_quality_speed_iteration_report.md`

Stable wins:

| Area | Latest evidence |
|---|---|
| 10-image prepared batch | Overall pass 100, 20/20 correct, first question 4.244s |
| Product-path single JPEG | Overall pass 100 on seed corpus, first question 24.618s |
| Fixed 30-image corpus | Upload success 100%, parse success 100%, readable question rate 100% |
| Backend focused regression | 72 passed, 1 skipped |
| Frontend build | Passes; Vite chunk-size warning remains |

Known failures from JPEG30:

| Metric | Result | Target |
|---|---:|---:|
| `image_end_to_end_p95_ms` | 131.071s | 60s |
| `first_question_p95_ms` | 88.901s | 30s |
| `segmentation_done_p95_ms` | 77.197s | 20s |
| `first_grading_after_segmentation_p95_ms` | 34.809s | 15s |
| `summary_after_first_question_p95_ms` | 113.997s before the short-window fix | 15s |
| `fast_batch_timeout_count` | 2 | 0 |

Interpretation:

- SSE/proxy is fast; the bottleneck is not transport.
- Tilted/shadow and cross-page photos are recognition long-tail cases.
- Blank/answer-only images should be rule-detected earlier instead of sent through full grading.
- Before the latest short-window fix, later slow questions could delay the page even when the first question was already available.

## Current Optimization Direction

Priority order:

1. Keep fast-first short-window behavior: after the first question, do not let slow pending questions block the whole page for 120s.
2. Add blank/answer-only lightweight detection before grading.
3. Add image quality scoring for tilt, shadow, crop risk and show retake guidance.
4. Add repeat benchmark for the 30-image corpus after each performance change.
5. Label the 30-image corpus with expected question count/order/score so it becomes both a speed and quality benchmark.
6. Split frontend bundles, especially PDF worker and non-first-screen demo/practice code.

## Verification Commands

Focused backend:

```bash
PYTHONPATH=. pytest -q \
  test/test_pipeline_streaming.py \
  test/test_fast_upload_flow.py \
  test/test_effectiveness.py \
  test/test_large_pdf_mode.py
```

Broader backend set used in recent iterations:

```bash
PYTHONPATH=. pytest -q \
  test/test_statistics_verifier.py \
  test/test_fast_upload_flow.py \
  test/test_pipeline_streaming.py \
  test/test_effectiveness.py \
  test/test_large_pdf_mode.py \
  test/test_practice_orchestrator.py \
  test/test_rescue_bridging.py \
  test/test_feedback_metrics_dashboard.py
```

Frontend:

```bash
cd frontend
npm run build
```

Benchmark corpus:

```bash
python scripts/build_jpeg_benchmark_corpus.py \
  --output-dir test/fixtures/jpeg_benchmark_corpus \
  --count 30

python scripts/evaluate_upload_corpus.py \
  --input-dir test/fixtures/jpeg_benchmark_corpus \
  --api-base http://127.0.0.1:8000 \
  --repeat 1 \
  --max-concurrency 1 \
  --track-events \
  --output reports/effectiveness/jpeg30_fast_first_phase_metrics_YYYYMMDD.json
```

## What Not To Change Casually

- Do not let OCR unconditionally rewrite segmenter output.
- Do not hide uncertainty by dropping timeout/unreadable placeholder questions.
- Do not make fast-first generate inline solutions before first result.
- Do not widen topic aliases without a matching benchmark sample or human review note.
- Do not optimize speed by lowering `needs_review` visibility.
