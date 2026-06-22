# Practice Orchestrator MVP Design

Date: 2026-06-22

## Goal

Turn grading from a one-time correction report into a learning loop: grade the student's work, diagnose the weakest next topic, recommend practice, grade the new answer, then adapt the next recommendation.

## Product Principle

The product should make students feel guided, not judged. Every grading result should lead to one concrete next study action. AI transparency should explain why a recommendation was chosen, not expose internal model logs.

## MVP Entry Point

The first version starts from the grading result page.

After a homework or Past Paper submission finishes, the results page shows a `下一步练习` section below the learning diagnosis. The student can start recommended practice immediately from the weak topics detected in the current grading session.

This is preferred over building a separate learning-plan page because it keeps the loop attached to the moment of correction, when the student most needs the next action.

## Existing Building Blocks

The repository already has useful foundations:

- Grading output contains `knowledge_tags`, `syllabus_topics`, `error_type`, `score`, `full_score`, and `needs_review` on each question.
- Page summary contains `priority_topics` and `knowledge_tags_summary`.
- Question bank models already support `topic`, `subtopic`, `difficulty`, `tags`, `marking_points`, and `common_errors`.
- Practice APIs already exist under `/questions/random` and `/questions/submit-answer`.
- Frontend has a Practice mode, answer input, result display, and summary components.

The MVP should reuse these pieces instead of building a new practice system.

## User Flow

1. Student uploads work and receives grading results.
2. The system identifies the top weak topic from `summary.priority_topics` first, falling back to wrong-question `knowledge_tags` if needed.
3. The result page shows `下一步练习` with up to three recommended items:
   - `基础修复`: lower difficulty, same topic.
   - `巩固练习`: medium difficulty, same topic.
   - `真题风格`: higher difficulty or exam-style source when available.
4. Student clicks `开始练习`.
5. The question opens in an inline practice panel, visually aligned with the grading page.
6. Student submits an answer.
7. The existing `/questions/submit-answer` endpoint grades the answer.
8. The panel shows correctness, score, short feedback, and the next action:
   - If correct with high score: suggest a harder same-topic question.
   - If partially correct: suggest another same-topic medium question.
   - If wrong: suggest an easier foundation question or a brief review.
9. The current session remembers recommended and completed question IDs to avoid immediate repeats.

## Recommendation Strategy

### Inputs

- `PageSummary.priority_topics`
- Wrong or partially correct `QuestionResult` items
- `knowledge_tags`
- `error_type`
- `score / full_score`
- `needs_review`
- Existing question-bank metadata

### Topic Selection

Use this priority order:

1. `summary.priority_topics[0]` when present.
2. Most frequent `knowledge_tags` among incorrect questions.
3. Most frequent `error_type` mapped to a broad fallback topic.
4. If no topic is available, show a clear fallback state instead of pretending to know.

### Question Selection

For each weak topic, request question-bank items through `/questions/random` with:

- `topics`: selected topic or mapped topic key.
- `exclude_ids`: IDs already recommended or completed in the current session.
- difficulty bands:
  - foundation: `1-2`
  - consolidation: `3`
  - exam-style: `4-5`
- `count`: enough candidates to fill three cards.

If the exact topic has no available questions, broaden to parent topic or related tags. If no match exists, show a disabled fallback card that says real practice is unavailable until more tagged questions are added.

## Data Contracts

### Frontend View Model

```ts
interface PracticeRecommendation {
  id: string
  question_id: number | null
  topic: string
  subtopic?: string | null
  difficulty: "foundation" | "consolidation" | "exam-style"
  title: string
  reason: string
  source_label?: string
  unavailable?: boolean
}
```

### Session State

```ts
interface PracticeLoopState {
  weak_topics: string[]
  recommended_ids: number[]
  completed_ids: number[]
  current_question_id?: number
  last_result?: {
    question_id: number
    is_correct: boolean
    score: number
    full_score: number
    error_type: string | null
  }
}
```

The first version can keep this state in React state. Persistent mastery tracking is a later phase.

## UI Design

The UI should stay close to the current grading style: white panels, slate text, blue accents, compact cards, and no decorative dashboard look.

`下一步练习` appears after the main diagnosis. Each card should show:

- recommendation type
- topic and subtopic
- difficulty label
- one-sentence reason
- source metadata when available
- `开始练习` button

After a student starts practice, use an inline panel rather than navigating away. The student should feel the grading result naturally continued into practice.

## Agentic Loop Presentation

Do not show raw `think / act / observe` labels to students. Use learning language:

- `定位弱点`
- `选择练习`
- `提交作答`
- `批改反馈`
- `调整下一题`
- `总结进步`

Internally, this corresponds to:

- observe: read grading and practice result
- think: choose weak topic and difficulty
- act: fetch or generate next practice item
- observe: grade submitted answer
- decide: raise, repeat, or simplify
- final: summarize next study action

## Tagging Strategy

A fully hand-tagged question bank is not required before launching this loop.

MVP tagging should be progressive:

1. Use existing `topic`, `subtopic`, `difficulty`, and `tags`.
2. Map grading `knowledge_tags` to question-bank topics with a small alias table.
3. When recommendations fail because of missing tags, log the missing topic key.
4. Later, run an AI-assisted batch tagging job over high-traffic or untagged questions.
5. Human-review only the questions that are frequently recommended or low-confidence.

This avoids blocking the product on a complete taxonomy project.

## Error And Fallback States

- No weak topic found: show `本次表现较均衡` and suggest general mixed practice.
- Topic found but no question-bank match: show the weak topic and say the real question bank needs more tagged questions.
- Practice grading fails: preserve the student's answer and show retry.
- AI confidence low or `needs_review` is true: recommend teacher review before adaptive practice.
- Duplicate recommendation risk: exclude already completed and already shown IDs.

## Non-Goals For MVP

- Long-term mastery profile across days.
- Full spaced-repetition scheduling.
- Full automatic question-bank retagging.
- AI-generated new questions as the default path.
- Separate learning-plan page.
- Complex multi-agent debug trace in the student UI.

## Implementation Phases

### Phase 1: Recommendation Cards

Show `下一步练习` after grading using current session results and existing `/questions/random`.

### Phase 2: Inline Practice Attempt

Let students answer one recommended question inline and grade it using `/questions/submit-answer`.

### Phase 3: Adaptive Next Step

After the practice answer is graded, choose one next recommendation based on correctness and score.

### Phase 4: Lightweight Mastery Memory

Persist topic attempts locally or in the existing feedback/history storage so future sessions can avoid repeats and show progress.

## Acceptance Criteria

- After a grading run with at least one wrong or partial question, the result page shows at least one practice recommendation when matching question-bank items exist.
- Each recommendation shows topic, difficulty, and a reason tied to the grading result.
- Starting a recommendation opens an inline practice panel without losing the grading result.
- Submitting an answer calls `/questions/submit-answer` and displays the grading result.
- After practice grading, the UI shows a next action: harder, repeat, easier, or review.
- The loop excludes already completed question IDs within the current session.
- If no real question is available, the UI shows a clear fallback rather than a fake recommendation.
- Evidence must include a real browser screenshot or DOM proof, not only logs.

## Test Plan

- Unit-test recommendation derivation from `PageSummary` and `QuestionResult` fixtures.
- Component-test or replay-test the `下一步练习` panel with fixture grading results.
- API integration test that `/questions/random` can return candidates for a selected topic.
- Browser visual acceptance for desktop and mobile with recommendations visible.
- Regression check that grading results still render without recommendations when no weak topic exists.
