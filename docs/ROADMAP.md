# Roadmap

## Completed

- Core upload and grading pipeline.
- Streaming progress events for the grading flow.
- Multi-agent grading and voting path.
- Deterministic verifier modules for common math categories.
- Student and teacher feedback formatting.
- Local question-bank APIs and practice-mode frontend.
- Past-paper resolver with question-level mark scheme context.
- Visual acceptance runner for desktop and mobile checks.
- Long-running agent workflow files under `agent_workflow/`.

## In Progress

- Large PDF Mode.
  - Backend prepare session exists in the current source snapshot.
  - Frontend page selection UI is the next active milestone.
  - Later milestones should process only selected pages and preserve the normal 16-page upload limit.

## Next

- Add a typed Large PDF frontend client.
- Build PDF page picker and paper confirmation UI.
- Connect selected pages to streaming grading.
- Add regression tests for selected-page limits.
- Document data restore flow for the raw PDF corpus.

## Later

- Improve paper/code recognition from uploaded PDFs.
- Add richer analytics for repeated student mistakes.
- Harden production settings by hiding debug endpoints unless `DEBUG=1`.
- Package demo data separately from raw corpus data.
