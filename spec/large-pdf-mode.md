# Large PDF Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let students upload a full A-Level past paper PDF, identify the paper context, select the relevant questions/pages, and process only those pages without removing the existing 16-image upload limit.

**Architecture:** Large PDF Mode is a separate upload route beside the current image/PDF-to-images path. The backend stores a short-lived PDF session, renders thumbnails and lightweight page metadata, resolves paper context, then converts only selected pages into the existing grading pipeline. The frontend treats large PDFs as a guided selection flow instead of immediately converting every page into upload images.

**Tech Stack:** FastAPI routes, existing in-memory upload cache pattern, `pdfjs-dist` for current frontend PDF rendering where useful, backend PDF rendering/OCR utilities added behind feature-specific modules, React components under `frontend/src/components/largePdf`, existing `agent_step` timeline contract.

---

## Current State

- `frontend/src/components/UploadForm.tsx` converts every selected PDF page into images client-side through `frontend/src/utils/pdfToImages.ts`.
- `UploadForm.tsx` enforces `MAX_FILES = 24`.
- `api/routes.py` enforces `MAX_PAGES_PER_REQUEST = 24` for `/analyze-homework` and `/analyze-homework-stream`.
- `/prepare-upload` accepts one image and caches extraction through `api/upload_cache.py`.
- Past paper routing already accepts `upload_intent`, `paper_code`, and `question_numbers` through `api/paper_resolver.py`.

Large PDF Mode should not force students to choose pages before they can proceed. It should auto-select up to the single-run budget and let users remove cover, blank, or irrelevant pages only when needed.

## File Structure

- Create `api/large_pdf_cache.py`: short-lived in-memory session store for PDF metadata, thumbnails, and temporary PDF path.
- Create `api/large_pdf.py`: PDF intake, page thumbnailing, page selection conversion, and paper-context helpers.
- Modify `api/routes.py`: add Large PDF endpoints and call existing `run_pipeline_streaming` only after selected pages are converted.
- Modify `api/paper_resolver.py`: accept Large PDF page/header recognition signals without changing manual paper-code behavior.
- Create `test/test_large_pdf_mode.py`: backend tests for session creation, selected-page enforcement, and fallback routing.
- Create `frontend/src/api/largePdfClient.ts`: typed client for Large PDF endpoints.
- Create `frontend/src/components/largePdf/LargePdfMode.tsx`: guided PDF workflow shell.
- Create `frontend/src/components/largePdf/PdfPagePicker.tsx`: thumbnail grid and page selection controls.
- Create `frontend/src/components/largePdf/PaperContextCard.tsx`: paper match/manual confirmation UI.
- Modify `frontend/src/components/UploadForm.tsx`: branch PDF upload into Large PDF Mode when needed, while preserving current small-PDF/image flow.
- Modify `frontend/src/types/index.ts`: add Large PDF session and selected-page request types.
- Modify `spec/acceptance.md`: add Large PDF acceptance checks once implementation begins.

## Backend Contracts

### `POST /large-pdf/prepare`

Accepts one PDF file.

Returns:

```json
{
  "status": "ready",
  "pdf_id": "uuid",
  "filename": "9709_s22_qp_11.pdf",
  "page_count": 17,
  "preview_pages": [
    {
      "page": 1,
      "thumbnail_b64": "data:image/jpeg;base64,...",
      "width": 360,
      "height": 509,
      "ocr_hint": "Cambridge International AS & A Level Mathematics 9709..."
    }
  ],
  "paper_resolution": {
    "paper_id": "9709_s22_11",
    "paper_label": "CIE 9709/11 May/Jun 2022",
    "match_confidence": "medium",
    "match_source": "cover",
    "grading_route": "open_ai_grading",
    "needs_user_confirmation": true
  }
}
```

Rules:

- PDF file size cap is separate from image cap. Start with `MAX_LARGE_PDF_BYTES = 80 * 1024 * 1024`.
- Page count cap is separate from image cap. Start with `MAX_LARGE_PDF_PAGES = 40`.
- Render thumbnails for all pages at low resolution.
- OCR or vision recognition may inspect only pages 1-2 in MVP 2.
- Store local PDF paths only in the cache entry. Do not return them to the frontend, logs, SSE, or model prompts.

### `POST /large-pdf/{pdf_id}/analyze-stream`

Accepts:

```json
{
  "selected_pages": [3, 4, 7],
  "question_numbers": ["3", "4", "7"],
  "paper_code": "9709/11/M/J/22",
  "upload_intent": "full_past_paper_pdf"
}
```

Streams existing event types:

- `agent_step`
- `segmentation`
- `question_extracted`
- `agent_progress`
- `question`
- `summary`
- `solution`
- `done`
- `error`

Rules:

- `selected_pages.length` must be between 1 and 24. This preserves a bounded processing budget while allowing the original PDF to be larger.
- Convert only selected pages to temporary images.
- Pass `upload_intent="full_past_paper_pdf"`, `paper_code`, and `question_numbers` to `resolve_paper_context`.
- Emit an initial `agent_step` with title `选择 PDF 页面` and summary such as `已从 17 页 PDF 中选择 3 页进入批改。`
- If the PDF session expired, return `404 PDF_SESSION_EXPIRED`.
- If selected pages exceed 24, return `400 TOO_MANY_SELECTED_PAGES`.

## Frontend Flow

1. User selects a PDF.
2. If the PDF has 24 pages or fewer and upload intent is not `Past Paper / 真题卷`, keep the existing client-side conversion path.
3. If the PDF has more than 24 pages or upload intent is `Past Paper / 真题卷`, enter Large PDF Mode.
4. Large PDF Mode calls `/large-pdf/prepare`.
5. UI shows:
   - paper match/manual paper code card;
   - page thumbnails;
   - auto-selected page thumbnails;
   - selected count, max 24 pages for one grading run.
6. User starts grading directly or removes irrelevant pages/questions first.
7. Frontend consumes `/large-pdf/{pdf_id}/analyze-stream` with the same stream parser callbacks used by `analyzeHomeworkStreaming`.

Student-facing copy:

- `已读取整套 PDF。系统已自动选中可处理页面。`
- `完整 PDF 不需要拆成图片；你可以直接开始，也可以取消封面、空白页或无关页面。`
- `一次最多批改 24 页；下一轮可以继续处理更多页面。`

## Milestones

### Milestone 1: Backend PDF Session And Thumbnails

**Files:**

- Create `api/large_pdf_cache.py`
- Create `api/large_pdf.py`
- Modify `api/routes.py`
- Create `test/test_large_pdf_mode.py`

- [ ] Add `LargePdfSession` storage with `store`, `get`, `pop`, and TTL sweep.
- [ ] Add `prepare_large_pdf(file)` that validates PDF size/page count and returns page thumbnails.
- [ ] Add `POST /large-pdf/prepare`.
- [ ] Test with `test/9709_s22_qp_11.pdf`:

```bash
pytest test/test_large_pdf_mode.py::test_prepare_large_pdf_returns_session_and_thumbnails -q
```

Expected: response has `pdf_id`, `page_count > 0`, and at least one thumbnail.

Rollback point:

- If thumbnailing is unstable, keep `/large-pdf/prepare` behind a feature flag and leave existing PDF conversion untouched.

### Milestone 2: Paper Context Recognition Contract

**Files:**

- Modify `api/large_pdf.py`
- Modify `api/paper_resolver.py`
- Extend `test/test_large_pdf_mode.py`

- [ ] Extract first-page text/header signal from the PDF session.
- [ ] Convert recognized code into the existing `paper_code` format before calling `resolve_paper_context`.
- [ ] Return `match_confidence="medium"` when recognition is plausible but needs student confirmation.
- [ ] Test cover/header recognition fallback:

```bash
pytest test/test_large_pdf_mode.py::test_large_pdf_prepare_returns_medium_confidence_when_cover_matches -q
```

Expected: `needs_user_confirmation` is `true` unless manual `paper_code` is supplied.

Rollback point:

- If recognition is noisy, return `match_confidence="low"` and rely on manual paper code without disabling Large PDF upload.

### Milestone 3: Frontend Large PDF Selection UI

**Files:**

- Create `frontend/src/api/largePdfClient.ts`
- Create `frontend/src/components/largePdf/LargePdfMode.tsx`
- Create `frontend/src/components/largePdf/PdfPagePicker.tsx`
- Create `frontend/src/components/largePdf/PaperContextCard.tsx`
- Modify `frontend/src/components/UploadForm.tsx`
- Modify `frontend/src/types/index.ts`

- [ ] Add typed API calls for `prepareLargePdf` and `analyzeLargePdfStreaming`.
- [ ] Add `LargePdfMode` state to `UploadForm.tsx` without changing image upload behavior.
- [ ] Show page thumbnails with selected count `已选择 N/24 页`.
- [ ] Show manual paper code and question number inputs in the Large PDF panel.
- [ ] Run visual acceptance:

```bash
cd frontend
npm run test:visual -- --url http://127.0.0.1:3001/ --out /private/tmp/alevel-large-pdf-ui
```

Expected: desktop and mobile screenshots exist, and `horizontalOverflow=false`.

Rollback point:

- If the new UI has layout risk, hide the Large PDF branch and keep the existing PDF button path.

### Milestone 4: Selective Page Processing

**Files:**

- Modify `api/large_pdf.py`
- Modify `api/routes.py`
- Extend `test/test_large_pdf_mode.py`
- Modify `frontend/src/api/largePdfClient.ts`
- Modify `frontend/src/components/largePdf/LargePdfMode.tsx`

- [ ] Add selected-page validation: 1-24 pages only.
- [ ] Convert selected pages into temporary images.
- [ ] Call `run_pipeline_streaming` with selected images and existing paper context.
- [ ] Emit `agent_step` events for PDF intake, paper resolution, selected-page processing, and route choice.
- [ ] Test selected-page limit:

```bash
pytest test/test_large_pdf_mode.py::test_large_pdf_analyze_rejects_more_than_24_selected_pages -q
```

Expected: `400 TOO_MANY_SELECTED_PAGES`.

- [ ] Test existing image limit still holds:

```bash
pytest test/test_large_pdf_mode.py::test_existing_image_stream_limit_still_rejects_more_than_24_files -q
```

Expected: current `/analyze-homework-stream` behavior remains unchanged.

Rollback point:

- If selective processing fails, keep `prepare` and page selection UI as preview-only, then route users back to the current 16-page upload path with a clear message.

### Milestone 5: Evidence And Documentation

**Files:**

- Modify `spec/acceptance.md`
- Modify `agent_workflow/prd.json`
- Update `agent_workflow/progress.md` through `scripts/agent_workflow.py`

- [ ] Document Large PDF acceptance evidence:
  - prepare endpoint response sample;
  - page selection screenshot;
  - selected-page stream evidence;
  - existing image limit regression result.
- [ ] Run backend checks:

```bash
pytest test/test_large_pdf_mode.py test/test_paper_resolver.py -q
python -m py_compile api/large_pdf.py api/large_pdf_cache.py api/routes.py
```

Expected: all tests pass and py_compile exits 0.

- [ ] Run frontend checks:

```bash
cd frontend
npm run build
npm run test:visual -- --url http://127.0.0.1:3001/ --out /private/tmp/alevel-large-pdf-final
```

Expected: build exits 0; visual report status is `passed`.

Rollback point:

- If documentation or visual checks fail late, leave the feature disabled and merge only backend/session code that is fully covered by tests.

## Non-Goals For First Implementation

- Do not grade all 40 PDF pages in one request.
- Do not remove the 16-image limit from the normal upload path.
- Do not require cover page upload when manual paper code is available.
- Do not expose local PDF/QP/MS filesystem paths in public responses.
- Do not build full OCR question-text matching in the first Large PDF milestone.

## Acceptance Checklist

- [ ] PDF intake is separate from image upload.
- [ ] Page thumbnailing works before grading starts.
- [ ] Paper recognition/manual paper code feeds the existing Past Paper resolver.
- [ ] Large PDF mode auto-selects processable pages before grading and allows optional page removal.
- [ ] Only selected pages enter `run_pipeline_streaming`.
- [ ] Current `MAX_FILES = 24` and `MAX_PAGES_PER_REQUEST = 24` remain in sync.
- [ ] More than 24 selected PDF pages is rejected with a clear error.
- [ ] Large PDF UI has desktop and mobile screenshot evidence.
- [ ] Feature can be disabled without breaking existing image/PDF upload.
