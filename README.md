# A-Level Assistant

An AI learning assistant for Cambridge A-Level Mathematics homework and past-paper practice.

The product turns uploaded homework images or selected PDF pages into structured grading, mark-scheme-grounded feedback, and next-step study guidance. It is designed as a learning workspace rather than a generic answer bot: the core output is not only whether an answer is right, but where the student's reasoning broke and what to review next.

## What It Does

- Upload homework images and receive per-question grading.
- Stream visible grading progress through `agent_step` events.
- Match CAIE 9709 past-paper context where possible.
- Inject question-level mark scheme context into grading prompts.
- Cross-check math with deterministic verifiers for algebra, statistics, probability, and simplification.
- Generate student-facing and teacher-facing feedback.
- Browse and practice from a local structured question bank.
- Support long-running agent development through durable workflow files in `agent_workflow/`.

## Current Status

The project has a working full-stack MVP:

- FastAPI backend with upload, grading, streaming, feedback, and question-bank APIs.
- React/Vite frontend with upload flow, grading views, progress timeline, practice mode, history, and profile pages.
- Local SQLite question bank with 5536 parsed questions.
- Past-paper catalog metadata for 468 paper records in the checked-in database.
- Large PDF Mode is in progress. The backend prepare route exists in this snapshot; frontend selection work is being developed separately.

## Architecture

```text
frontend/        React/Vite UI: upload, grading, practice, history, profile
api/             FastAPI routes, streaming endpoints, debug/demo helpers
pipeline/        Image/PDF loading, segmentation, extraction, orchestration
grader/          Classification, grading, multi-agent voting, solution generation
verifier/        Deterministic math/statistics/probability checks
formatter/       Student and teacher feedback, summaries, formula/topic helpers
router/          Model registry and provider abstraction
questionbank/    SQLite question-bank access and mark-scheme helpers
scraper/         CAIE catalog and paper collection utilities
parser/          PDF parsing and batch question extraction
reflection/      Socratic follow-up and next-practice suggestions
memory/          Student weakness/fact extraction and storage
agent_workflow/  Durable task plan and progress for long-running AI work
spec/            Product, acceptance, and implementation specs
docs/            Design notes, proposals, and architecture decisions
```

Key design rule: model access should stay behind `router.models.ModelClient`, and the runtime grading pipeline should remain separated into segment, extract, grade, verify, format, and render stages.

## Data Included

This repository includes lightweight structured data:

- `data/questions.db`: local SQLite question bank.
- `data/papers_catalog.csv`: past-paper catalog metadata.

The raw PDF corpus under `data/papers/` is intentionally not committed. It is larger, changes independently from source code, and may have redistribution constraints. See [docs/DATA.md](docs/DATA.md) for the data strategy.

## Quick Start

```bash
cp .env.example .env
pip install -r requirements.txt
python server.py
```

Open:

```text
http://localhost:8000
```

If you modify the frontend:

```bash
cd frontend
npm install
npm run build
cd ..
python server.py
```

For frontend-only development:

```bash
python server.py
cd frontend && npm run dev
```

## Useful Commands

```bash
# Backend focused tests
pytest test/test_paper_resolver.py test/test_pipeline_mark_scheme.py -q

# Large PDF Mode backend tests
pytest test/test_large_pdf_mode.py -q

# Frontend build
cd frontend && npm run build

# Visual acceptance runner
cd frontend && npm run test:visual

# Long-running task status
python scripts/agent_workflow.py status
```

## Environment

Create `.env` from `.env.example`. Real model keys are never committed.

Main variables:

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL`
- `DASHSCOPE_API_KEY`
- `DEEPSEEK_API_KEY`
- `GLM_API_KEY`
- `ALLOWED_ORIGINS`

## Development Notes

- Do not expose raw chain-of-thought. UI progress should show concise learning-oriented step summaries only.
- Keep raw local PDF paths out of user-visible responses, logs, SSE payloads, and model prompts.
- Do not raise the normal 16-page image upload limit to support full PDFs. Large PDF Mode uses a separate prepare/select/process flow.
- Keep generated folders and local assets out of Git: `frontend/node_modules/`, `frontend/dist/`, `data/papers/`, `.env`, caches, and local test media.

## Roadmap

- Complete Large PDF frontend selection UI.
- Add selected-page streaming for Large PDF Mode.
- Improve paper recognition and manual confirmation.
- Expand visual acceptance evidence for mobile and desktop.
- Package the paper corpus through a controlled data channel instead of regular Git history.

## Related Docs

- [Run locally](RUN.md)
- [Deploy](DEPLOY.md)
- [Product UI spec](spec/product-ui-agent-spec.md)
- [Large PDF Mode plan](spec/large-pdf-mode.md)
- [Acceptance criteria](spec/acceptance.md)
- [Question bank proposal](docs/question-bank-proposal.md)
- [Agent workflow](agent_workflow/README.md)
