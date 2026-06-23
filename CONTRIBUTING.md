# Contributing

Thanks for your interest in A-Level Assistant.

This repository is primarily a portfolio and research-oriented AI learning assistant project. Contributions are welcome when they keep the project focused on A-Level mathematics diagnosis, reliable grading, and student-safe learning feedback.

## Project Principles

- Keep the product focused on A-Level mathematics learning diagnosis.
- Prefer Mark Scheme grounded grading when reliable paper context exists.
- Treat LLM output as untrusted until checked by rules, verifiers, tests, or reviewer evidence.
- Do not expose raw hidden reasoning or chain-of-thought in student-facing UI.
- Keep runtime grading agents separate from development orchestration files under `agent_workflow/`.
- For UI changes, include real browser evidence when practical.

## Local Setup

```bash
cp .env.example .env
pip install -r requirements.txt
python server.py
```

Frontend development:

```bash
cd frontend
npm install
npm run dev
```

## Useful Checks

Run focused checks based on what you changed:

```bash
pytest test/test_practice_orchestrator.py -q
pytest test/test_paper_resolver.py -q
pytest test/test_large_pdf_mode.py -q
```

Frontend:

```bash
cd frontend
npm run test:practice-context
npm run test:practice-orchestrator
npm run build
```

Visual acceptance:

```bash
cd frontend
npm run test:visual
```

## Before Opening A Pull Request

- Keep the change scoped and reviewable.
- Avoid committing real API keys, raw paper PDFs, local uploads, screenshots, or generated caches.
- Update docs or specs if behavior changes.
- Include the commands you ran and whether they passed.
- For UI work, include browser screenshot or DOM evidence when possible.

## Data And External Assets

The repository includes lightweight demo data. Raw third-party exam PDFs are intentionally excluded from normal Git history. If you restore local paper corpora for private development, keep them under ignored paths such as `data/papers/`.
