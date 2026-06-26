# MinerU Questionbank Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure MinerU locally and expose a stable project entry point that can turn PDF papers into structured text assets for question tagging and later practice recommendation.

**Architecture:** Keep MinerU isolated in `.venv-mineru` because the main project currently runs on Python 3.9 while MinerU requires Python 3.10-3.13. Add a thin Python adapter that shells out to the MinerU CLI, discovers its generated Markdown/JSON files, and lets existing question extraction choose MinerU text before falling back to the current image/VL path.

**Tech Stack:** Python 3.10 virtual environment, MinerU 3.4.0 CLI, SQLite questionbank, pytest.

---

### Task 1: Local MinerU Runtime

**Files:**
- Create: `requirements-mineru.txt`
- Modify: `.gitignore`
- Modify: `.env.example`

- [x] **Step 1: Install MinerU in an isolated runtime**

Run:
```bash
uv venv --python /Library/Frameworks/Python.framework/Versions/3.10/bin/python3.10 .venv-mineru
uv pip install --python .venv-mineru/bin/python -U "mineru[all]"
```

Expected: `.venv-mineru/bin/mineru` exists and `mineru[all]` installs successfully.

- [ ] **Step 2: Document repeatable install inputs**

Create `requirements-mineru.txt`:
```text
mineru[all]==3.4.0
```

Add `.venv-mineru/` and `data/mineru_output/` to `.gitignore`.

Add these optional environment variables to `.env.example`:
```dotenv
MINERU_BIN=.venv-mineru/bin/mineru
MINERU_OUTPUT_DIR=data/mineru_output
MINERU_BACKEND=pipeline
MINERU_METHOD=auto
MINERU_LANG=ch
MINERU_TIMEOUT_SECONDS=1200
```

### Task 2: MinerU Adapter

**Files:**
- Create: `questionbank/mineru_adapter.py`
- Test: `test/test_mineru_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Test command:
```bash
python -m pytest test/test_mineru_adapter.py -q
```

Expected before implementation: import failure for `questionbank.mineru_adapter`.

- [ ] **Step 2: Implement adapter**

Expose:
```python
run_mineru_parse(pdf_path, output_dir=None, backend=None, method=None, lang=None, timeout_seconds=None)
read_mineru_text(result)
mineru_available()
```

The adapter must:
- Use `MINERU_BIN` first, then `.venv-mineru/bin/mineru`, then `mineru` on PATH.
- Run `mineru -p <pdf> -o <output> -b <backend> -m <method> -l <lang>`.
- Find Markdown, `*_content_list.json`, `*_content_list_v2.json`, `*_middle.json`, and `*_model.json` under the output directory.
- Raise a clear `MinerUNotAvailableError` when the CLI cannot be found.

- [ ] **Step 3: Verify adapter tests pass**

Run:
```bash
python -m pytest test/test_mineru_adapter.py -q
```

Expected: all tests pass without invoking real MinerU.

### Task 3: Parser Integration

**Files:**
- Modify: `parser/pdf_parser.py`
- Test: `test/test_pdf_parser_mineru.py`

- [ ] **Step 1: Write parser integration test**

Test command:
```bash
python -m pytest test/test_pdf_parser_mineru.py -q
```

Expected before implementation: no MinerU extraction path exists.

- [ ] **Step 2: Add optional MinerU text path**

Add `use_mineru: bool | None = None` to `parse_question_paper`. When enabled by argument or `QUESTIONBANK_USE_MINERU=1`, run MinerU first, read its text, and pass that extracted text into the existing question extraction prompt as a text-first context. If MinerU fails or is unavailable, log the reason and fall back to the current image path unless `QUESTIONBANK_REQUIRE_MINERU=1`.

- [ ] **Step 3: Verify parser integration test passes**

Run:
```bash
python -m pytest test/test_pdf_parser_mineru.py -q
```

Expected: parser uses MinerU text when available and falls back safely when unavailable.

### Task 4: Smoke Verification

**Files:**
- No code files expected.

- [ ] **Step 1: Verify installed CLI**

Run:
```bash
.venv-mineru/bin/mineru --help
```

Expected: command exits with usage information.

- [ ] **Step 2: Run a bounded PDF parse**

Run:
```bash
.venv-mineru/bin/mineru -p test/9709_s22_qp_11.pdf -o data/mineru_output -b pipeline -m auto -s 0 -e 1
```

Expected: MinerU writes Markdown and structured JSON files under `data/mineru_output`.

- [ ] **Step 3: Run focused test suite**

Run:
```bash
python -m pytest test/test_mineru_adapter.py test/test_pdf_parser_mineru.py -q
```

Expected: tests pass.
