# Mark Scheme Fusion Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a student explicitly uploads or labels work as a past paper, use the matched paper code to fuse three sources before grading: the extracted student answer, the local question-bank record, and the official mark-scheme block. This makes automated scoring follow Cambridge M/A/B points when available and keeps the practice recommendation loop grounded in the same knowledge base.

**Architecture:** Keep `api.paper_resolver` as the paper-code authority. Keep `questionbank.mark_scheme` as the PDF mark-scheme block extractor. Add a small question-bank matcher that resolves `(paper, question_number)` to stored question records and formats their structured answers, marking points, tags, and common errors as grading context. `pipeline._attach_mark_scheme_contexts` becomes the fusion point.

**Tech Stack:** Python, SQLite, existing FastAPI/pipeline modules, pytest, local CIE 9709 paper assets.

---

### Task 1: Question-Bank Past-Paper Matcher

**Files:**
- Create: `questionbank/pastpaper_matcher.py`
- Test: `test/test_pastpaper_matcher.py`

- [ ] **Step 1: Write failing tests**

Build a temporary SQLite DB with one paper and subpart questions. Assert that:
- Exact subpart lookup, e.g. `1(a)`, returns the matching question with high confidence.
- Top-level lookup, e.g. `1`, can still return the same question group with medium confidence.
- The formatted context contains question id, stored question text, topic/subtopic/tags, correct answer, marking points, and common errors.

- [ ] **Step 2: Implement matcher**

Expose:
```python
build_questionbank_mark_scheme_context(conn, catalog_match, question_number) -> QuestionBankMarkSchemeContext | None
```

The function should only match inside the exact subject/year/session/paper/variant from the catalog row.

- [ ] **Step 3: Verify focused tests**

Run:
```bash
python -m pytest test/test_pastpaper_matcher.py -q
```

Expected: PASS.

### Task 2: Pipeline Fusion

**Files:**
- Modify: `pipeline/pipeline.py`
- Test: `test/test_pipeline_mark_scheme.py`

- [ ] **Step 1: Write failing test**

Patch `build_mark_scheme_context_map` and `build_questionbank_mark_scheme_context`, then assert `_attach_mark_scheme_contexts` stores a single `mark_scheme_context` containing both the structured question-bank context and the official PDF mark-scheme block.

- [ ] **Step 2: Implement fusion**

For `past_paper_mark_scheme` route:
- Attach the official MS block when high/medium confidence.
- Attach question-bank context when a DB record matches.
- Keep fallback metadata (`open_ai_grading`, error reason) when official MS block cannot be found.
- Add non-sensitive match metadata (`questionbank_question_id`, `questionbank_match_confidence`) to the record for observability.

- [ ] **Step 3: Verify focused tests**

Run:
```bash
python -m pytest test/test_pipeline_mark_scheme.py test/test_mark_scheme_context.py test/test_pastpaper_matcher.py -q
```

Expected: PASS.

### Task 3: Real Smoke Tests

**Files:**
- No additional code files expected.

- [ ] **Step 1: Real DB match**

Use local `data/questions.db` and `9709_s22_qp_41/ms_41` to verify `1(a)` resolves to the stored question and marking points.

- [ ] **Step 2: Real MS PDF extraction**

Extract official context for `9709_s22_ms_41.pdf` question `1` and confirm it contains recognizable M/A/B marks.

- [ ] **Step 3: Real image/PDF smoke**

Run focused non-network tests plus the available test image/PDF smoke paths to ensure the pipeline can still extract and grade-prep homework without breaking.
