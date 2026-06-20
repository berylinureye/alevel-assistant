# Long-Term Agent Knowledge

## Product Direction

- The product is an A-Level learning assistant, not a generic AI dashboard.
- The core value is: grading should explain what the student should study next.
- Past Paper matching is a primary route, not a decoration. Prefer mark-scheme-grounded grading when enough paper context exists.
- Do not force users to upload a cover page. Recommend cover/page code, then fall back gracefully.

## Architecture Boundaries

- Product grading agents live in `pipeline/`, `grader/`, `verifier/`, and `formatter/`.
- Development orchestration lives in `agent_workflow/` and `scripts/agent_workflow.py`.
- Do not mix development-task orchestration with runtime grading logic.
- Keep model access behind `router.models.ModelClient`.
- Keep `segment -> extract -> grade -> vote -> verify -> feedback -> summary` responsibilities separate.

## UI Rules

- UI should feel like a learning workspace: calm, light, scan-first, actionable.
- Student-facing workflow labels should use learning language, not raw technical labels.
- Never show raw chain-of-thought.
- Wrong answers should lead to next action, not only a red error state.
- UI acceptance requires real browser evidence, not build logs only.

## Long-Running Work Rules

- The orchestrator picks the next task from `agent_workflow/prd.json`.
- Workers get narrow file ownership and must not revert unrelated edits.
- Testers validate acceptance criteria and report concrete evidence.
- Whoever wrote the bug fixes it; whoever found the bug verifies the fix.
- Resume prior sub-agents when the fix depends on their context.
- Update `progress.md` after each meaningful round.
- Promote durable lessons into this file instead of bloating future prompts.

## Known Gotchas

- The project directory currently is not a git repository in this environment, so rely on file lists and tests instead of `git diff`.
- Frontend dev port `3000` may already be occupied; Vite may fall back to `3001`.
- Real grading requires model keys in `.env`; visual validation should not require model keys.
- Mobile validation should check both screenshots and `document.documentElement.scrollWidth`.
- Paper resolver output sent to users, logs, SSE, or model prompts must not expose local `qp_path` / `ms_path`; keep file paths inside `pipeline_context()` only.
- Large PDF Mode should be a separate session/selection route; do not raise the normal `MAX_FILES` / `MAX_PAGES_PER_REQUEST` limits to support full past-paper PDFs.
