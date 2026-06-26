# Questionbank Tagging Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every local CIE 9709 past-paper PDF is represented in the SQLite question bank with usable topic/subtopic/tag metadata, and make those tags drive the random practice and recommendation loop.

**Architecture:** Keep `data/questions.db` as the knowledge base. Add an audit utility that compares `data/papers/**/*.pdf` with the `papers`, `questions`, and `question_tags` tables, then tighten query semantics so topic selectors and post-grading recommendations can match either chapter-level topics or fine-grained subtopic/tag keys.

**Tech Stack:** Python, SQLite, FastAPI question-bank routes, existing Pydantic models, pytest, MinerU CLI already configured in `.venv-mineru`.

---

### Task 1: Knowledge Base Coverage Audit

**Files:**
- Create: `questionbank/audit.py`
- Test: `test/test_questionbank_audit.py`

- [ ] **Step 1: Write failing tests**

Create tests that build a temporary SQLite DB and paper directory, then assert:
- A parsed paper with at least one question and tag is counted as complete.
- A local QP PDF with no DB paper row is reported as missing.
- A paper with questions but no `question_tags` row is reported as untagged.

Run:
```bash
python -m pytest test/test_questionbank_audit.py -q
```

Expected: FAIL because `questionbank.audit` does not exist.

- [ ] **Step 2: Implement audit utility**

Expose:
```python
audit_questionbank(pdf_root: Path | str = "data/papers", db_path: Path | str = "data/questions.db") -> QuestionBankAudit
```

The returned object must include `local_qp_count`, `db_paper_count`, `db_question_count`, `db_tag_count`, `missing_in_db`, `papers_without_questions`, `questions_without_tags`, and `questions_without_topic`.

- [ ] **Step 3: Verify tests**

Run:
```bash
python -m pytest test/test_questionbank_audit.py -q
```

Expected: PASS.

### Task 2: Tag-Aware Question Retrieval

**Files:**
- Modify: `questionbank/database.py`
- Test: `test/test_questionbank_tag_filtering.py`

- [ ] **Step 1: Write failing tests**

Tests should insert a question whose `topic` is `coordinate_geometry`, `subtopic` is `equation_of_circle`, and tag is `tangent_to_circle`, then assert `get_random_questions(..., topics=["coordinate_geometry"])`, `topics=["equation_of_circle"]`, and `topics=["tangent_to_circle"]` can all retrieve it.

Run:
```bash
python -m pytest test/test_questionbank_tag_filtering.py -q
```

Expected: FAIL for subtopic/tag lookups before implementation.

- [ ] **Step 2: Implement topic-or-tag filtering**

Update `get_random_questions` so `topics` means:
```sql
q.topic IN selected OR q.subtopic IN selected OR EXISTS (
  SELECT 1 FROM question_tags qt
  WHERE qt.question_id = q.id AND qt.tag IN selected
)
```

Keep all existing difficulty, paper, year, verified, and exclude filters.

- [ ] **Step 3: Verify focused tests**

Run:
```bash
python -m pytest test/test_questionbank_tag_filtering.py -q
```

Expected: PASS.

### Task 3: Recommendation Loop Uses Taxonomy Tags

**Files:**
- Modify: `api/practice_orchestrator.py`
- Test: `test/test_practice_orchestrator.py`

- [ ] **Step 1: Add failing orchestrator tests**

Add tests that assert:
- `derive_candidate_topics` maps known subtopic `equation_of_circle` to parent `coordinate_geometry`.
- When the weak signal is a fine-grained tag, `_query_recommendations` passes that tag to `get_random_questions` while preserving the displayed parent topic.

Run:
```bash
python -m pytest test/test_practice_orchestrator.py -q
```

Expected: FAIL until taxonomy lookup and query target handling are implemented.

- [ ] **Step 2: Implement taxonomy lookup**

Build a subtopic-to-topic map from `scraper.taxonomy.PAPER_TOPICS`. Normalize candidate weak signals as parent topics when known, and pass both parent topic plus raw subtopic/tag keys into DB retrieval.

- [ ] **Step 3: Verify orchestrator tests**

Run:
```bash
python -m pytest test/test_practice_orchestrator.py -q
```

Expected: PASS.

### Task 4: Real Smoke Tests

**Files:**
- No code files expected.

- [ ] **Step 1: Audit local corpus**

Run:
```bash
python -m questionbank.audit --pdf-root data/papers --db data/questions.db
```

Expected: local QP count equals DB paper count, and missing/untagged counts are zero.

- [ ] **Step 2: Exercise random practice by topic and subtopic**

Run:
```bash
python - <<'PY'
from questionbank.database import ensure_db, get_random_questions
conn = ensure_db()
for key in ["coordinate_geometry", "equation_of_circle", "tangent_to_circle"]:
    qs, total = get_random_questions(conn, topics=[key], count=1)
    print(key, total, qs[0].question_number if qs else None)
conn.close()
PY
```

Expected: each key returns at least one real tagged question.

- [ ] **Step 3: Exercise recommendation API function**

Run a direct `recommend_practice` call with `knowledge_tags=["equation_of_circle"]` and confirmed past-paper context. Expected: response mode `auto` with at least one real recommendation.

- [ ] **Step 4: Exercise test image/PDF material**

Run an existing image/PDF extraction smoke test against files under `test/`, preferring focused tests that do not require full production deployment.
