# UI Composite Notes

This note records the design direction behind the current grading UI refresh.
It is intentionally kept out of the product interface so students see actions,
not implementation concepts.

## Current Direction

- Use a calm student-facing shell: upload first, report second, correction third.
- Keep visible copy short. Prefer action labels over process labels.
- Keep design terms such as "intake", "dashboard", "coach", and "tutor" out of the user interface.
- Let the UI guide inexperienced users through layout and button priority instead of long helper text.
- Allow uncertain uploads. If the student only has answer pages or misses paper metadata, the system should explain that later in the report.
- Keep the main grading product visually minimal: white surfaces, black line icons, gray hierarchy, and no blue primary styling unless the user explicitly approves it.

## Reflection Rule

- Before changing UI, first list the details the user has already said they like or want to keep.
- Do not remove liked product details while applying a new visual style. Preserve the upload guidance, report dashboard, and correction workspace unless the user explicitly asks to replace them.
- If a decision is uncertain, make a side-by-side demo or describe the trade-off and ask the user to choose.
- Avoid turning internal design concepts into visible product labels. Put rationale here in docs instead.

## Upload Screen Rules

- Show four upload intent choices, but only the names are visible.
- Keep explanations available to assistive technology through accessible labels.
- Show one short reassurance: answer-only pages can be uploaded first.
- Make upload actions the main guidance: camera, image, and PDF should feel like a compact icon tray, not a large drag-and-drop billboard.
- A process panel can stay only if it is concise and secondary. If it competes with the upload task, move the content into a compact top note or a demo for review.

## Report And Corrections

- The report should summarize performance with score, correct/wrong counts, and next action.
- The question card should behave like a correction workspace: score first, reason second, details after expansion.
- Detailed design rationale belongs in docs, not in the student-facing page.
