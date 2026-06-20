# Product UI And Agent Specification

## Goal

Create a polished A-Level learning workspace where students upload real homework, watch an AI grading workflow progress, and receive specific feedback that improves their next study action.

## Scope

This spec governs the next UI/agent-facing iteration of the project. It is not a full system design document; it defines the product direction, visual rules, agent cooperation mechanism, delivery phases, and links to acceptance criteria.

Related documents:

- [Acceptance Criteria](./acceptance.md)
- [Long-Running Agent Workflow](./long-running-agent-workflow.md)
- [Large PDF Mode Implementation Plan](./large-pdf-mode.md)
- [Agency Guide](../AGENCY.md)

## Product Positioning

The product is a learning assistant, not a generic admin dashboard and not a marketing landing page.

Primary users:

- A-Level students who upload work and need specific correction.
- Teachers/tutors who need fast diagnosis of errors and weak topics.

Primary user questions:

- What did I get wrong?
- Where did my reasoning break?
- What concept should I review?
- Which questions should I practice next?
- How confident is the AI, and why?

## Product Principles

- Make students feel corrected, not judged.
- Every grading result should lead to a concrete next study action.
- AI transparency should build trust, not expose internal reasoning.
- Teachers should see where to intervene; the product should not pretend AI is always certain.
- Prefer mark-scheme-grounded grading when the upload can be matched to a known past paper; fall back to open AI grading when it cannot.

## Core Grading Strategy

The product should support two grading routes.

### Route A: Past Paper Matching Grading

Use this route when the upload can be matched to a known A-Level past paper question.

Flow:

```text
upload -> resolve paper context -> match question bank -> fetch mark scheme -> grade against mark scheme -> explain deductions -> study summary
```

Advantages:

- Faster and more accurate than open-ended grading.
- Lower hallucination risk.
- More credible for teachers because grading is grounded in official mark schemes.
- Easier to connect mistakes to topics and recommended practice.

### Route B: Open AI Grading

Use this route when the upload cannot be reliably matched.

Examples:

- teacher-created homework
- workbook questions
- cropped questions without enough context
- unknown paper code
- low-confidence question-bank match

Flow:

```text
segment -> extract -> multi-agent grade -> vote -> verify -> feedback
```

Default system behavior:

```text
try Past Paper matching first -> ask for confirmation when uncertain -> fallback to open grading when matching is low-confidence or unavailable
```

Do not force students to upload a full paper or cover page. The system should infer what it can, then ask lightweight follow-up questions only when needed.

## Visual Style

The visual direction is a premium learning workspace with visible AI workflow.

Use:

- Light surfaces by default.
- Calm slate/white base palette.
- Blue for primary actions and workflow accents.
- Green/red/amber only for semantic correctness states.
- Small-radius cards and controls, generally `rounded-md` or `rounded-lg`.
- Subtle borders over heavy shadows.
- Information-dense but breathable layouts.
- Clear typography hierarchy with compact headings inside panels.
- Warm learning-product microcopy: prefer "next step", "review", "practice", and "needs review" over "error report" language.

Avoid:

- Large dark panels unless the whole page is intentionally dark mode.
- Generic SaaS hero sections.
- Decorative gradient blobs, orbs, and excessive glass effects.
- Purple/indigo AI-default palette dominance.
- Card-in-card nesting except for repeated items, modals, or framed tools.
- Visible explanatory UI text that sounds like a feature tour instead of product content.
- Overusing red for wrong answers; wrong work should feel actionable, not punitive.

## Layout Rules

### First Screen

The grading first screen should prioritize upload.

Required hierarchy:

1. Lightweight app header.
2. Navigation tabs.
3. Page title/one-line purpose.
4. Upload surface as the dominant action.
5. Optional AI workflow/support panel that is lighter than the upload surface.
6. A short "after upload you will get" section.

The page must not feel like several unrelated white boxes stacked together.

The first screen should answer what the student gets after upload:

- per-question score
- mistake cause
- key-step feedback
- weak topics
- next recommended practice

### Upload Surface

The upload area should:

- Make image/PDF upload obvious.
- Support drag/drop, camera upload, file selection, and PDF selection.
- Show selected files as a clean grid.
- Show pre-extraction readiness without alarming the user.
- Keep mobile upload ergonomics high.
- Offer a lightweight upload intent choice:
  - `Past Paper / 真题卷`
  - `老师布置的作业`
  - `不确定，帮我识别`
- Default intent should be `不确定，帮我识别`.
- Recommend, but never require, uploading a cover page for past paper work.
- Explain briefly: `如果你上传的是 Past Paper，包含封面页或 paper code 会让批改更快更准。`

### Past Paper Matching Mode

Before open-ended grading, the system should attempt to identify whether the upload belongs to a known A-Level past paper.

Supported upload situations:

- full past paper PDF
- partial past paper pages
- cover page plus answer pages
- screenshots of a few questions
- answer pages only
- custom homework
- unknown intent

Upload intent model:

```ts
type UploadIntent =
  | "full_past_paper_pdf"
  | "partial_past_paper_pages"
  | "answer_pages_only"
  | "custom_homework"
  | "unknown"
```

Paper matching should use layered fallback:

1. Cover recognition: syllabus code, paper number, session, year, variant.
2. Page header recognition: paper code, page number, question number.
3. Question text matching: OCR/vision text matched against question bank.
4. Manual selection: exam board, subject, year, session, paper, variant.
5. Open grading fallback.

Match confidence:

- `high`: automatically use mark-scheme grading.
- `medium`: ask the user to confirm the paper/question.
- `low`: ask for more context or fall back to open grading.

If only answer pages are uploaded and no paper context is detected, the UI should ask the user to upload the question page, upload the cover page, or manually select the paper.

The frontend should handle multiple possible matches with a confirmation card:

- `正确`
- `不是这套`
- `我不知道`

Large PDF direction:

- Full past paper PDFs may have 16-20 pages and should not be constrained by the image-page limit.
- The long-term path is Large PDF Mode: inspect first pages, identify paper, show page/question thumbnails, and process only selected/relevant pages.
- MVP may keep current upload limits, but the UI should recommend PDF upload instead of asking students to split full papers into many screenshots.
- Implementation details and rollback points live in [Large PDF Mode Implementation Plan](./large-pdf-mode.md).

### Result Surface

The result view should:

- Preserve streaming updates.
- Show progress/agent trace while grading.
- Use filter tabs for all/correct/wrong/unanswered.
- Make question cards scannable before expansion.
- Keep summary, feedback, formulas, and solution text visually distinct.
- Frame the page as a learning diagnosis, not only grading results.

The top of the result page should follow this structure:

1. `本次表现`: score rate, correct count, wrong count, unanswered count.
2. `主要问题`: top weak topics or recurring error types.
3. `下一步`: what to review, which practice to attempt, and estimated time.

The result page should help the student decide what to do tonight, not only see what went wrong.

### Agent Workflow Panel

The agent workflow should be visible but not dominant.

Backend events may use technical step types, but user-facing labels should use learning language.

Preferred user-facing labels:

- `识别上传类型`
- `匹配真题`
- `确认题目`
- `识别题型`
- `提取答案`
- `初步判分`
- `交叉检查`
- `生成反馈`

Avoid showing raw labels like `think`, `act`, `observe`, `decide`, or `final` in student-facing UI.

It must not show raw chain-of-thought or private reasoning.

### Question Card Priority

Collapsed cards should be scan-first.

Default collapsed state should show only:

- question number
- score, e.g. `3/5`
- status: correct / partial / wrong / unanswered / needs review
- one-sentence mistake cause, e.g. `方法对，但漏了条件限制`
- AI confidence: high / medium / low

Expanded state may show:

- original image or question crop
- question text
- student answer
- standard solution
- deduction points
- student feedback
- teacher feedback
- recommended practice

### AI Confidence

Do not rely on raw percentages alone.

Preferred format:

- `AI 置信度：高`  
  `原因：答案、关键步骤、公式使用均一致`
- `AI 置信度：中`  
  `原因：解题步骤较完整，但手写识别有一处不确定`
- `AI 置信度：低`  
  `原因：模型投票不一致，建议老师复核`

The UI may still retain numeric confidence for debug or compact badges, but student-facing interpretation should be qualitative and explainable.

### Needs Review State

The product must support a clear `建议老师复核` state.

Triggers may include:

- messy handwriting
- incomplete image or cropped prompt
- proof/show-that questions
- severe skipped steps
- model vote disagreement
- OCR/vision conflict
- low extraction or grading confidence

This state is a trust feature, not a failure state.

## Agent Cooperation Mechanism

The backend currently acts as a staged multi-agent workflow:

```text
segment -> extract -> multi-agent grade -> vote -> verify -> feedback -> summary
```

The target observable shape is:

```text
think -> act -> observe -> decide -> final
```

The first implementation step is observability, not behavioral rewrite.

Use structured events:

- `agent_progress`: legacy status events for per-agent started/completed/failed states.
- `agent_step`: structured workflow event for the frontend timeline.

Recommended event contract:

```ts
type AgentStepType = "think" | "act" | "observe" | "decide" | "final"
type AgentStepStatus = "running" | "completed" | "failed"

interface AgentStepData {
  question_number: string
  step_type: AgentStepType
  title: string
  summary: string
  status: AgentStepStatus
  agent_name?: string | null
  tool?: string | null
  detail?: Record<string, unknown>
  confidence?: "high" | "medium" | "low"
  user_visible?: boolean
  severity?: "info" | "success" | "warning" | "error"
  paper_id?: string | null
  question_id?: string | null
  match_confidence?: "high" | "medium" | "low" | null
  match_source?: "cover" | "page_header" | "question_text" | "manual" | "none"
  grading_route?: "past_paper_mark_scheme" | "open_ai_grading"
  needs_user_confirmation?: boolean
}
```

Rules:

- Step summaries must be short and user-safe.
- Detail fields may include scores, confidence, elapsed time, method, and agreement.
- Detail fields must not include hidden model reasoning.
- `user_visible=false` events are for developer/debug surfaces and should not appear in normal student UI.
- `severity` should drive visual treatment; it should not be inferred only from color.
- Past paper fields should be present when the step relates to paper matching or route selection.
- `grading_route` should be explicit before grading starts when the route is known.
- Frontend should gracefully fall back to legacy logs if `agent_step` is absent.

## Delivery Plan

### Phase 1: UI Foundation

Deliver:

- Lightweight app header and navigation.
- Grading first-screen layout with upload-first hierarchy.
- Upload surface visual refresh.
- Consistent card, border, radius, status, and typography treatment.
- Build passes with `npm run build`.

Acceptance:

- Empty grading page is visually coherent at desktop and mobile widths.
- Upload area is clearly the primary action.
- No large dark block appears in the default light UI.

### Phase 2: Agent Trace Experience

Deliver:

- `agent_step` timeline rendered in the grading progress panel.
- Legacy `agent_progress` still supports per-question skeleton cards.
- Timeline shows classify/action/observe/decision/final states.
- Timeline uses user-facing learning labels, not raw technical step names.
- Timeline remains compact and does not obscure question results.

Acceptance:

- A real or fixture-backed grading run shows at least 4 distinct workflow steps.
- Timeline works without exposing chain-of-thought.
- If backend is unavailable, error state remains understandable.

### Phase 3: Past Paper Matching MVP 1

Deliver:

- Manual past paper selection for known papers/questions.
- Student can upload answer/question pages and select paper code + question number.
- System can retrieve matching question/mark scheme data when available.
- Grading route is explicit: `past_paper_mark_scheme` or `open_ai_grading`.
- If no match is selected or available, system falls back to open AI grading.

Acceptance:

- User can choose at least subject/paper/year/session/question from available data or fixture data.
- UI clearly shows when grading is mark-scheme-grounded.
- UI clearly shows fallback when no match is available.

### Phase 4: Past Paper Matching MVP 2

Deliver:

- Cover/page-header recognition for paper context.
- Medium-confidence paper matches require user confirmation.
- High-confidence matches can proceed automatically.
- Low-confidence matches ask for more context or use open grading.

Acceptance:

- Upload with cover or page header can produce a paper candidate.
- Confirmation card appears when multiple matches are plausible.
- User can choose `正确`, `不是这套`, or `我不知道`.

### Phase 5: Result And Study Diagnosis

Deliver:

- Question cards redesigned for scanning and expansion.
- Page summary redesigned as a study diagnosis, not just score totals.
- Weak topics and formulas are visually connected to next actions.
- Teacher/student feedback remains distinct.
- `建议老师复核` state is visible and visually distinct from simple wrong answers.
- AI confidence is qualitative and includes a short reason when available.

Acceptance:

- Results page supports at least all/correct/wrong/unanswered filters.
- Expanded question card clearly shows prompt, student answer, score, feedback, and solution.
- Summary gives score rate, counts, common errors, and priority topics when available.
- Collapsed cards can be scanned without reading long feedback text.

### Phase 6: Practice Loop

Deliver:

- Lightweight practice recommendation MVP, even before the full question bank is complete.
- Recommend 3 practice items by topic when weak topics are available.
- Mark each item as `easy`, `medium`, or `exam-style`.
- Explain why each item is recommended.
- Let the student return to upload/grading after practice.
- Keep practice UI visually aligned with grading UI.

Acceptance:

- A wrong-topic summary can lead the user to at least three relevant practice recommendations or a clear fixture-backed placeholder.
- Practice UI does not feel like a separate product.

### Later: Past Paper Matching MVP 3

Deliver:

- Question-text/OCR matching without cover page.
- Partial screenshot matching against the question bank.
- Large PDF Mode with thumbnail/page selection.
- Process only relevant pages after paper/question selection.

Acceptance:

- A partial past paper page can produce ranked question candidates.
- Large PDF upload does not require the student to manually split pages into images.

## Response And Collaboration Mechanism

When an agent works on this project:

1. Read `AGENCY.md` first.
2. For UI/agent workflow work, read this spec.
3. For acceptance, read `spec/acceptance.md`.
4. Make small, reviewable changes.
5. Verify with commands and, for UI changes, real browser evidence.
6. Report what changed, what was verified, and what remains uncertain.

When making design changes:

- Prefer proposing one clear direction, then implementing one screen or state.
- Treat user visual feedback as binding.
- If the user dislikes a visual element, remove or simplify it before adding more decoration.

## Visual Validation Notes

Every major UI change should capture evidence for:

- Desktop first screen.
- Mobile first screen.
- Upload selected-file state if touched.
- Loading/agent trace state if touched.
- Result card state if touched.

Screenshots are preferred. If screenshots are unavailable, provide real browser DOM evidence plus a clear note that visual screenshot verification was not possible.
