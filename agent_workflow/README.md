# Long-Running Agent Workflow

This folder is the shared workbench for long-running AI development on this repo.

It combines two ideas:

- Ralph-style file memory: tasks, progress, and durable project knowledge live in files.
- Multi-agent orchestration: a main orchestrator coordinates planning, development, testing, and review agents with separate context.

Use it for large multi-step changes that would otherwise overload one conversation.

## Files

- `prd.json`: task backlog, status, owners, acceptance criteria, and event history.
- `progress.md`: short-term memory for each work round.
- `knowledge.md`: long-term rules, decisions, gotchas, and coordination habits.

## Commands

```bash
python scripts/agent_workflow.py status
python scripts/agent_workflow.py next
python scripts/agent_workflow.py start AW-001 --agent orchestrator --note "Starting implementation"
python scripts/agent_workflow.py complete AW-001 --agent tester --note "Build and browser evidence passed"
python scripts/agent_workflow.py block AW-001 --agent tester --note "Backend key unavailable"
python scripts/agent_workflow.py note --agent orchestrator --text "Learned: keep paper matching separate from grading pipeline."
```

## Coordination Rules

- The orchestrator owns task selection, context packing, and final integration.
- Workers own bounded file sets and must not revert unrelated edits.
- Testers validate the exact task acceptance criteria and report evidence.
- Whoever introduced a bug should fix it; whoever found the bug should verify the fix.
- A task is not done without tests or runtime evidence when the UI/API surface changes.
