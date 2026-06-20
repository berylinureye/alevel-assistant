# Long-Running Agent Workflow

## Goal

Enable AI agents to work on this repository for long, complex tasks without losing project context, while preserving quality through explicit planning, ownership, testing, and evidence.

## Recommendation

Use a hybrid of Ralph-style file memory and multi-agent orchestration.

Do not use an unconditional shell loop as the primary workflow. A blind loop is easy to start but too rigid for this project because UI, backend grading, model routing, and acceptance evidence often need different specialists.

## Architecture

### Orchestrator

The main agent is the orchestrator.

Responsibilities:

- Read `AGENCY.md`, relevant specs, and `agent_workflow/knowledge.md`.
- Choose the next task from `agent_workflow/prd.json`.
- Pack focused context for each sub-agent.
- Assign file ownership.
- Integrate results.
- Decide whether work is complete, blocked, or needs another iteration.
- Update `agent_workflow/progress.md`.

The orchestrator should keep its context light. It should not do every implementation detail when the task is large enough to delegate.

### Sub-Agents

Use sub-agents for bounded work:

- Planning agent: expands one task into concrete implementation steps.
- Development agent: edits a narrow set of files.
- Testing agent: validates acceptance criteria and reports evidence.
- Review agent: checks risks, regressions, and whether evidence is sufficient.

Each sub-agent should have independent context and a narrow brief. It should know that other agents may also be editing the repo and must not revert unrelated work.

### File Memory

Ralph-style memory is still useful, but as coordination state rather than a replacement for orchestration.

Files:

- `agent_workflow/prd.json`: tasks, status, owner, acceptance, event history.
- `agent_workflow/progress.md`: short-term progress log.
- `agent_workflow/knowledge.md`: durable project lessons and coordination rules.
- `scripts/agent_workflow.py`: small helper for status and task updates.

## Status Model

Task status values:

- `pending`: ready to pick up.
- `in_progress`: owned by an active agent.
- `blocked`: cannot progress without input or external state.
- `completed`: acceptance criteria passed with evidence.

Priority values:

- `P0`: core route or correctness blocker.
- `P1`: important UX, test, or workflow improvement.
- `P2`: planned follow-up.
- `P3`: optional cleanup.

## Resume Rule

Use the same sub-agent for bug fixes when possible.

Pattern:

```text
developer agent implements task -> tester agent finds bug -> orchestrator resumes the same developer agent with tester evidence -> tester verifies the fix
```

This preserves local context and follows the rule: whoever wrote the bug fixes it; whoever found the bug verifies it.

## When To Use This Workflow

Use it when a task:

- touches frontend and backend together;
- requires multiple verification modes;
- has more than one independent research question;
- risks exceeding a single conversation's useful context;
- needs repeated implementation/test/fix cycles;
- changes product or agent architecture.

Do not use it for small single-file fixes.

Large PDF Mode should be executed through this workflow as multiple child tasks rather than one oversized change. Use [Large PDF Mode Implementation Plan](./large-pdf-mode.md) as the task source, and keep backend session work, frontend selection UI, selective processing, and visual acceptance in separate worker scopes.

## Integration With Product Runtime

This workflow is for development orchestration. It must not be confused with the product's runtime grading agents.

Runtime grading agents:

- live in `grader/`, `pipeline/`, `verifier/`, and `formatter/`;
- grade student work;
- emit user-safe `agent_step` summaries;
- never expose raw chain-of-thought.

Development orchestration:

- lives in `agent_workflow/` and `scripts/agent_workflow.py`;
- coordinates code changes and testing;
- may spawn planning/development/testing sub-agents;
- records durable lessons for future sessions.

## Minimal Operating Loop

1. Orchestrator runs `python scripts/agent_workflow.py status`.
2. Orchestrator chooses or confirms the next task.
3. Orchestrator starts the task:

   ```bash
   python scripts/agent_workflow.py start AW-001 --agent orchestrator --note "Packed context and assigned worker"
   ```

4. Worker implements within assigned files.
5. Tester validates against task acceptance criteria.
6. If failed, orchestrator resumes the same worker with tester evidence.
7. If passed, task is completed with evidence:

   ```bash
   python scripts/agent_workflow.py complete AW-001 --agent tester --note "pytest + build + screenshot passed"
   ```

8. Orchestrator promotes durable lessons into `knowledge.md`.

## Acceptance

A long-running workflow change is accepted only when:

- `agent_workflow/prd.json` can be read by `scripts/agent_workflow.py`.
- The helper can show status and next task.
- At least one unit test covers task selection or status update logic.
- The mechanism is documented in this spec and referenced from `AGENCY.md`.
- The workflow does not require model/API keys for local status checks.
