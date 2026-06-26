# Progress

Use this file as short-term memory for long-running agent work. Each entry should say what changed, what was learned, and what evidence exists.

- 2026-06-20T00:00:00+08:00 Initialized the hybrid long-running workflow for this repo. The first backlog focuses on making past-paper matching truly mark-scheme-grounded, adding replayable agent events, improving visual acceptance, and designing Large PDF Mode.

- 2026-06-19T17:19:27+00:00 orchestrator: Implemented hybrid long-running workflow docs, task memory, helper script, and tests.

- 2026-06-19T17:21:59+00:00 orchestrator: start AW-001 - Starting question-level mark scheme context integration.

- 2026-06-19T17:41:43+00:00 orchestrator: complete AW-001 - Implemented question-level mark scheme context for matched Past Papers. Evidence: 15 focused tests passed, py_compile passed, spec reviewer PASS, code-quality reviewer APPROVED.

- 2026-06-19T17:42:16+00:00 orchestrator: Completed AW-001: Past Paper route now extracts question-level mark scheme context, injects it into grading prompts, exposes safe route metadata, and avoids leaking local QP/MS paths. Verification: 15 focused tests passed, py_compile passed, spec reviewer PASS, code-quality reviewer APPROVED.

- 2026-06-19T17:47:43+00:00 orchestrator: start AW-002 - Starting fixture-backed agent_step replay for loading-state UI.

- 2026-06-20T02:10:17+00:00 orchestrator: complete AW-002 - Implemented fixture-backed agent_step replay for loading UI. Evidence: npm run test:agent-steps passed, npx tsc -b passed, touched-file eslint passed, Chrome screenshot /private/tmp/alevel-agent-step-replay.png, DOM proof /private/tmp/alevel-agent-step-replay-dom.html.

- 2026-06-20T02:10:33+00:00 orchestrator: start AW-003 - Starting repeatable visual acceptance runner for desktop and mobile screenshots.

- 2026-06-20T02:17:44+00:00 orchestrator: complete AW-003 - Added repeatable visual acceptance runner and documented it. Evidence: npm run test:visual produced desktop/mobile screenshots and report in /private/tmp/alevel-visual-acceptance-aw003-final with horizontalOverflow=false; node --check passed; npm run build passed.

- 2026-06-20T02:18:18+00:00 orchestrator: start AW-004 - Starting Large PDF Mode implementation plan: separate PDF intake, thumbnails, paper recognition, question selection, selective processing, milestones, and rollback points.

- 2026-06-20T02:20:57+00:00 orchestrator: complete AW-004 - Designed Large PDF Mode plan in spec/large-pdf-mode.md and linked it from product, acceptance, and workflow specs. Plan separates PDF intake, thumbnails, paper recognition, question selection, selective processing, preserves 16-page normal path limit, and includes milestones plus rollback points. Evidence: placeholder scan clean for new plan, workflow status readable, py_compile agent_workflow helper passed, visual runner node --check passed.

- 2026-06-20T03:11:02+00:00 orchestrator: start AW-002 - Continuing AW-002 polish: make agent trace labels less technical and align loading UI language with upload-page style.

- 2026-06-20T03:14:21+00:00 orchestrator: Refined grading UI: student-visible model names now use role labels only, internal model ids are hidden from progress/skeleton UI, and QuestionCard expanded scoring area is now a learning diagnosis panel. Evidence: npm run test:question-card, touched-file eslint, tsc, build, and question-card visual runner passed.

- 2026-06-20T03:14:58+00:00 orchestrator: complete AW-002 - Continued AW-002 polish: translated agent/tool/badge/fallback labels into student-facing learning language and aligned replay copy with the upload-page visual style. Evidence: npm run test:agent-steps passed, npx tsc -b passed, touched-file eslint passed, npm run test:visual for /__agent-step-replay passed with horizontalOverflow=false, npm run build passed.

- 2026-06-20T03:16:30+00:00 orchestrator: start AW-003 - Continuing AW-003: make visual runner enforce first-screen content checks for the grading home page while keeping custom replay paths usable.

- 2026-06-20T03:18:26+00:00 orchestrator: complete AW-003 - Continued AW-003: visual runner now enforces homepage content checks by default for upload and navigation visibility, reports checks/failures per viewport, and keeps custom replay paths usable. Evidence: node --check passed; npm run test:visual homepage passed with expectUpload=true expectNav=true and horizontalOverflow=false; npm run test:visual /__agent-step-replay passed with custom checks disabled.

- 2026-06-20T03:23:55+00:00 orchestrator: start AW-005 - Starting Large PDF Mode Milestone 1 backend prepare session with TDD.

- 2026-06-20T03:28:05+00:00 orchestrator: complete AW-005 - Implemented Large PDF prepare session backend: /large-pdf/prepare accepts PDF uploads, renders page thumbnails, returns public paper-resolution metadata, stores internal pdf_path in session cache, and preserves existing image page limits. Verified with pytest test/test_large_pdf_mode.py -q, pytest test/test_paper_resolver.py -q, and py_compile on changed backend modules.

- 2026-06-20T03:30:49+00:00 orchestrator: start AW-006 - Starting Large PDF frontend selection UI with typed client, guided page picker, and visual verification.

- 2026-06-20T03:48:15+00:00 orchestrator: complete AW-006 - Implemented Large PDF frontend selection UI and adjusted UX after user feedback: single-run budget increased to 24 pages, Large PDF pages are auto-selected by default, and a top start button lets users begin without manual page selection. Added typed prepare client, LargePdfMode/PaperContextCard/PdfPagePicker, Vite /large-pdf proxy, selected-page conversion through existing grading flow, replay route, and synced specs. Evidence: npm run build passed; focused eslint on touched frontend files passed; pytest test/test_large_pdf_mode.py test/test_paper_resolver.py -q passed; real /large-pdf/prepare and Vite proxy prepare returned ready for 20-page fixture; visual acceptance passed with screenshots in /private/tmp/alevel-large-pdf-ui-topstart.
