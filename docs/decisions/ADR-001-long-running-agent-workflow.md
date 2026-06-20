# ADR-001: Use Hybrid File Memory And Multi-Agent Orchestration For Long Development Tasks

## Status

Accepted

## Date

2026-06-20

## Context

This repository has several kinds of complex work:

- frontend UI polish and browser acceptance;
- backend grading and model-routing changes;
- past-paper matching and mark-scheme grounding;
- streaming `agent_step` observability;
- future Large PDF Mode.

Long tasks can exceed one agent conversation's useful context. A pure Ralph-style loop gives each round fresh context, but coordination is passive and rigid. A pure multi-agent approach is more flexible, but without durable files it can lose progress across sessions.

## Decision

Use a hybrid approach:

- Ralph-style file memory in `agent_workflow/`.
- A small stdlib helper at `scripts/agent_workflow.py`.
- Multi-agent orchestration for large work: orchestrator, planner, developer, tester, reviewer.

This workflow is for repository development only. It is separate from runtime grading agents in `pipeline/`, `grader/`, `verifier/`, and `formatter/`.

## Alternatives Considered

### Shell Loop Ralph Clone

Pros:

- Easy to run for many rounds.
- Simple mental model.

Cons:

- Too rigid for tasks needing UI screenshots, backend tests, and product judgment.
- Harder to preserve "who wrote the bug fixes it" because each loop can create a new context.
- Encourages autonomous churn unless task acceptance is very tight.

Rejected as the primary workflow.

### Runtime Multi-Agent Refactor First

Pros:

- Could make product grading more agentic.
- Existing `grader/multi_agent.py` already has multiple model agents and `agent_step`.

Cons:

- Higher risk to the user-facing grading path.
- Does not solve repository development context management by itself.

Deferred. Product runtime orchestration should evolve separately and conservatively.

### Hybrid File Memory + Orchestrator

Pros:

- Durable progress across sessions.
- Clear task ownership and acceptance evidence.
- Works without API keys for local workflow checks.
- Supports sub-agent resume and tester/developer loops.

Cons:

- Requires agents to maintain the files honestly.
- Adds a small amount of process overhead.

Accepted.

## Consequences

- Long tasks should begin by checking `python scripts/agent_workflow.py status`.
- Durable lessons belong in `agent_workflow/knowledge.md`.
- Short-term work notes belong in `agent_workflow/progress.md`.
- Completed tasks must cite tests or runtime evidence.
- Product grading code should not read from `agent_workflow/`; this is development infrastructure.
