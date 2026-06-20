# AGENCY

## Goal

Build an A-Level learning assistant that turns uploaded homework images/PDFs into mark-scheme-grounded or open-AI grading, visible workflow, and actionable study feedback.

## Repository Structure

- `frontend/`: React/Vite/Tailwind frontend, including upload flow, grading UI, history, summary, practice, and profile pages.
- `api/`: FastAPI app, upload/grading routes, streaming endpoints, feedback routes, showcase/demo routes, and debug helpers.
- `pipeline/`: image/PDF loading, segmentation, extraction, grading orchestration, and SSE workflow events.
- `grader/`: question classification, multi-agent grading, voting, confidence adjustment, and verifier integration.
- `verifier/`: deterministic math/statistics/probability/simplification checks used to calibrate model output.
- `formatter/`: student feedback, teacher feedback, solution explanation, topic/formula formatting, and page summaries.
- `router/`: model-client abstraction and model registry for base, vision, OCR, review, and explanation roles.
- `reflection/` and `memory/`: Socratic reflection, student weakness extraction, and student facts.
- `questionbank/`, `scraper/`, `data/`: CIE paper catalog, question database, paper scraping/parsing support, and local data.
- `math_solver/`: standalone multi-agent math solver reference flow.
- `models/`, `utils/`, `parser/`: shared schemas, utilities, image/PDF parsing helpers.
- `test/` and `test_*.py`: fixtures, regression tests, benchmarks, and manual replay scripts.
- `docs/`, `spec/`, `RUN.md`, `DEPLOY.md`: product notes, implementation specs, local run instructions, and deployment notes.
- `agent_workflow/`: long-running development task memory, backlog, progress notes, and durable agent knowledge.
- `scripts/agent_workflow.py`: helper for reading and updating long-running development tasks.
- `codex_shim.py`: local Codex CLI OAuth shim exposing OpenAI/Anthropic-compatible HTTP endpoints for demos/development.

## Implementation Constraints

- Keep all model access behind `router.models.ModelClient`; do not call provider SDKs directly from feature code.
- Preserve the stage separation: segment/extract, grade, vote, verify, format, and render should remain distinct responsibilities.
- Segmenter output must preserve student mistakes; never silently correct the student's work during extraction.
- Do not expose raw chain-of-thought. UI may show concise `agent_step` summaries only.
- Preserve streaming behavior for grading progress and per-question updates.
- Prefer past-paper/mark-scheme matching before open AI grading when paper context is available; never force a cover page as the only path.
- UI work should follow `spec/product-ui-agent-spec.md`: calm learning workspace, light surfaces, upload-first flow, visible but non-dominant AI workflow.
- Acceptance work should follow `spec/acceptance.md`; visual/UI changes require real running screenshots or equivalent real browser evidence, not logs alone.
- Do not commit real API keys, local uploads, generated caches, or unrelated build artifacts.
- Keep changes scoped; avoid broad prompt rewrites, provider migrations, or architecture refactors unless explicitly requested.
- For large multi-step development work, use `spec/long-running-agent-workflow.md` and `agent_workflow/`; keep this development workflow separate from runtime grading agents.
