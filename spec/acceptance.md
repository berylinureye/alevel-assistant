# Acceptance Criteria

## Principle

Acceptance must be concrete, comparable, and evidence-backed. A change is not accepted just because build logs pass.

For UI changes, there must be a real running screenshot or equivalent real browser evidence. Logs alone are not enough.

## Required Evidence

Every completed task should include:

- Files changed.
- Commands run.
- Whether each command passed or failed.
- Real runtime evidence:
  - preferred: browser screenshots;
  - acceptable fallback: browser DOM/accessibility evidence plus HTTP status/assets evidence;
  - not acceptable alone: TypeScript build output, lint output, or server logs.

## General Build Acceptance

Frontend:

- `cd frontend && npm run build` must pass for frontend code changes.
- If lint is run and fails due to existing issues, identify whether touched files introduced new issues.
- Production asset warnings are acceptable only if they existed before or are unrelated to the change.

Backend:

- Python syntax check must pass for touched backend files, using the smallest relevant command.
- For core grading changes, run at least one focused fixture/regression test when available.

Environment:

- The app should not require real API keys for purely visual validation.
- Model-backed behavior may be validated with fixture/prepared data if provider keys are unavailable.

## UI Acceptance

### Repeatable Visual Runner

Use the local visual runner for first-screen UI checks:

```bash
cd frontend
npm run test:visual
```

Behavior:

- If a local Vite app is already reachable on `127.0.0.1:3000`, `3001`, or `3002`, the runner uses it.
- If no app is reachable, the runner starts Vite on `127.0.0.1:3010` for the duration of the check.
- To target a specific app URL, run `node ../scripts/visual_acceptance.mjs --url http://127.0.0.1:3001/`.
- The default `/` check requires upload-related text and main navigation text to be visible.
- For fixture or replay pages, pass `--path /__agent-step-replay` or another route; custom paths keep screenshots and overflow checks but do not require upload/navigation content unless `--expect-upload` or `--expect-nav` is provided.
- To disable the default homepage content checks, pass `--skip-content-checks`.
- Screenshots and the JSON report are written to `/private/tmp/alevel-visual-acceptance` by default.

Required report fields:

- `viewport.width` and `viewport.height` for desktop and mobile captures.
- `metrics.scrollWidth`, `metrics.clientWidth`, and `metrics.horizontalOverflow`.
- `metrics.uploadTextVisible` and `metrics.navTextVisible`.
- `checks.expectUpload`, `checks.expectNav`, and per-viewport `failures`.
- `screenshotPath` for each viewport.

Pass criteria:

- The command exits `0`.
- Both desktop and mobile screenshots exist under `/private/tmp/alevel-visual-acceptance`.
- `horizontalOverflow` is `false` for both desktop and mobile.
- When `expectUpload=true`, `uploadTextVisible` is `true`.
- When `expectNav=true`, `navTextVisible` is `true`.

### Desktop First Screen

Viewport target: approximately `1366x768` or wider.

Pass criteria:

- App header is visible without overlap.
- Navigation tabs are visible and usable.
- Upload area is the most visually prominent action on the grading tab.
- Any support/workflow panel is secondary to upload.
- Page states what the user gets after upload: score, mistake cause, key-step feedback, weak topics, and next practice.
- Upload area offers or preserves a lightweight intent signal: `Past Paper / 真题卷`, `老师布置的作业`, or `不确定，帮我识别`.
- No text overlaps or spills outside buttons/cards.
- No default large dark panel appears in the light UI unless explicitly requested.

Evidence:

- Screenshot required, or documented real browser evidence if screenshot tooling is unavailable.

### Mobile First Screen

Viewport target: approximately `390x844` or similar phone size.

Pass criteria:

- Header and tabs fit without horizontal page overflow.
- Upload action is reachable without needing desktop-only drag/drop.
- Buttons have readable labels and do not wrap awkwardly.
- Secondary panels stack below primary upload content.

Evidence:

- Screenshot required, or documented real browser evidence if screenshot tooling is unavailable.

### Upload Selected-State

Pass criteria:

- Selected files appear in a stable grid/list.
- Remove/edit controls are visible or discoverable.
- Count indicator shows selected count and max count.
- PDF conversion/progress message does not cover primary controls permanently.
- Past paper guidance recommends cover page or paper code without making it mandatory.

Evidence:

- Screenshot or browser evidence with at least one selected file.

### Past Paper Matching

Pass criteria:

- System supports two explicit routes:
  - `past_paper_mark_scheme`
  - `open_ai_grading`
- Past paper matching is attempted before open-ended grading when upload intent or detected content suggests a past paper.
- Match confidence is represented as `high`, `medium`, or `low`.
- High-confidence match may proceed to mark-scheme grading.
- Medium-confidence match requires user confirmation.
- Low-confidence match asks for more context or falls back to open AI grading.
- If only answer pages are uploaded and no paper context is detected, UI asks for question page, cover page, or manual paper selection.
- Manual paper selection exists for MVP 1, even if automatic recognition is not complete.
- Matching UI shows paper ID/code, question number, match source, and route when known.

Evidence:

- Screenshot or browser evidence showing one of:
  - manual paper selection;
  - a paper match confirmation card;
  - fallback to open grading with a clear reason.

### Large PDF Mode

Detailed implementation plan: [Large PDF Mode Implementation Plan](./large-pdf-mode.md).

Pass criteria:

- Full PDF intake uses a dedicated Large PDF route/session instead of sending every page through `/analyze-homework-stream`.
- Current non-Large-PDF upload limits remain unchanged: frontend `MAX_FILES = 16`, backend `MAX_PAGES_PER_REQUEST = 16`.
- Page thumbnails are visible before grading starts.
- User can select pages/questions before processing.
- One Large PDF grading run processes at most 16 selected pages.
- Paper recognition/manual paper code feeds the existing Past Paper resolver.
- If paper matching is uncertain, the UI asks for confirmation or uses open AI grading with a visible reason.
- Local PDF paths are never returned to the frontend or included in user-visible events.

Evidence:

- Backend test or response sample for `/large-pdf/prepare`.
- Screenshot showing page thumbnails and selected count.
- Streaming evidence showing selected pages enter grading.
- Regression evidence showing the normal image upload limit still rejects more than 16 files.

### Loading / Agent Trace State

Pass criteria:

- Progress panel shows current status.
- If `agent_step` data exists, timeline shows distinct step labels and statuses.
- Normal student UI uses learning labels such as `识别上传类型`, `匹配真题`, `确认题目`, `识别题型`, `提取答案`, `初步判分`, `交叉检查`, `生成反馈`.
- Normal student UI does not show raw technical labels like `think`, `act`, `observe`, `decide`, or `final`.
- If only legacy logs exist, UI still displays useful progress.
- Raw chain-of-thought is not displayed.
- User can cancel when loading.

Evidence:

- Screenshot or recorded browser evidence from a real or fixture-backed run.

### Results State

Pass criteria:

- Filter bar is visible when questions exist.
- Each question card shows question number, correctness state, score, extraction confidence, and grading confidence.
- Collapsed question cards show a one-sentence mistake cause when available.
- Collapsed question cards show qualitative AI confidence: high / medium / low, or the Chinese equivalent.
- Expanded card shows prompt, student answer, feedback, and solution area when available.
- Page summary shows score rate, total/correct/wrong/unanswered counts, and priority topics when available.
- Result page top is framed as learning diagnosis: `本次表现`, `主要问题`, and `下一步`.
- `建议老师复核` appears as its own state when backend confidence/review flags require it.

Evidence:

- Screenshot or real browser evidence with at least one rendered question.

### Practice Recommendation MVP

Pass criteria:

- When weak topics are available, UI can show at least 3 recommended practice items.
- Each recommendation has topic, difficulty (`easy`, `medium`, or `exam-style`), and why it is recommended.
- If real question-bank recommendations are unavailable, fixture-backed placeholders are clearly marked and still follow the same structure.
- User can return from recommendation/practice context to upload/grading.

Evidence:

- Screenshot or real browser evidence with recommendations visible.

## Agent Workflow Acceptance

Backend event criteria:

- `agent_step` events use `question_number`, `step_type`, `title`, `summary`, and `status`.
- `step_type` must be one of `think`, `act`, `observe`, `decide`, `final`.
- `status` must be one of `running`, `completed`, `failed`.
- Optional `confidence` must be one of `high`, `medium`, `low`.
- Optional `severity` must be one of `info`, `success`, `warning`, `error`.
- Optional `match_confidence` must be one of `high`, `medium`, `low`.
- Optional `match_source` must be one of `cover`, `page_header`, `question_text`, `manual`, `none`.
- Optional `grading_route` must be one of `past_paper_mark_scheme`, `open_ai_grading`.
- `needs_user_confirmation=true` requires a user-facing confirmation or selection state before mark-scheme grading proceeds.
- Events with `user_visible=false` must not appear in normal student UI.
- Events must not include raw hidden reasoning.
- Legacy `agent_progress` must remain compatible unless explicitly migrated.

Frontend event criteria:

- Unknown event fields do not crash rendering.
- Missing `agent_step` does not break progress UI.
- Multi-page question relabeling still maps step events to the visible question label.

Evidence:

- Captured SSE sample, browser evidence, or fixture-backed event replay.

## Long-Running Development Workflow Acceptance

Use this section when a task is large enough to require multiple rounds, sub-agents, or cross-session continuation.

Pass criteria:

- Work begins from `agent_workflow/prd.json` or a clearly named task added there.
- `python scripts/agent_workflow.py status` can read the task file.
- Active work records an owner and status with `scripts/agent_workflow.py start`.
- Completed work records verification evidence with `scripts/agent_workflow.py complete`.
- Blocked work records the blocker with `scripts/agent_workflow.py block`.
- Short-term lessons are added to `agent_workflow/progress.md`.
- Durable lessons are promoted to `agent_workflow/knowledge.md`.
- Worker agents declare bounded file ownership and do not revert unrelated edits.
- Tester/reviewer agents validate the acceptance criteria, not just code style.
- Product runtime grading agents are not coupled to `agent_workflow/` files.

Evidence:

- Task id and status from `agent_workflow/prd.json`.
- Commands run and pass/fail status.
- Screenshots or browser evidence for UI changes.
- Focused tests or syntax checks for backend/script changes.

Reject if:

- A task is marked `completed` without verification notes.
- Two active tasks claim the same file ownership without an explicit coordination note.
- `agent_workflow/knowledge.md` contains raw hidden chain-of-thought instead of durable summaries.
- The workflow scripts require model/API keys to run local status checks.

## Bug Acceptance

A task is not accepted if any of these occur:

- App fails to load.
- Upload button becomes unreachable.
- Existing successful upload flow is broken by UI-only changes.
- Streaming parser crashes on unknown events.
- Backend startup fails due to code changes unrelated to missing API keys.
- UI overlaps, horizontal scrolls unexpectedly, or hides primary actions at target desktop/mobile viewports.
- Normal student UI displays raw agent step labels like `think`, `act`, `observe`, `decide`, or `final`.
- Wrong answers are presented only as punitive red error states without next-step guidance.
- System silently uses a low-confidence past paper match without asking for confirmation or falling back.
- Past paper mode requires a cover page with no manual or fallback alternative.

## Quantitative Targets

For UI pages:

- No horizontal body overflow at `390px`, `768px`, and `1366px` widths.
- Primary upload action visible within first viewport on desktop.
- Primary upload action visible within first two mobile screens.
- Button text must remain readable at `390px` width.
- Timeline item summaries should generally be under 120 Chinese characters or 180 English characters.
- Collapsed question-card mistake cause should generally fit within 1-2 lines at desktop width.
- Result diagnosis top should show `本次表现`, `主要问题`, and `下一步` within the first result viewport on desktop.
- Past paper confirmation card should show at most 3 primary candidate choices before manual selection.

For runtime behavior:

- Frontend production build must complete successfully.
- Backend syntax check for touched files must complete successfully.
- If a task touches streaming, at least one event parsing path must be exercised.

## Reporting Template

Use this summary format for completed implementation work:

```text
Changed:
- ...

Verified:
- command: result
- browser/runtime evidence: screenshot path or fallback evidence

Not verified:
- ...

Known risks:
- ...
```
