from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_workflow import choose_next, summarize, update_task


def _sample_prd() -> dict:
    return {
        "project": "demo",
        "workflow": "hybrid_orchestrator",
        "tasks": [
            {"id": "AW-002", "status": "pending", "priority": "P1", "events": []},
            {"id": "AW-001", "status": "pending", "priority": "P0", "events": []},
            {"id": "AW-003", "status": "completed", "priority": "P0", "events": []},
        ],
    }


def test_choose_next_prefers_highest_priority_pending() -> None:
    data = _sample_prd()

    task = choose_next(data)

    assert task is not None
    assert task["id"] == "AW-001"


def test_summarize_counts_statuses_and_next_task() -> None:
    data = _sample_prd()

    result = summarize(data)

    assert result["counts"] == {"pending": 2, "completed": 1}
    assert result["next"]["id"] == "AW-001"


def test_update_task_sets_owner_status_and_event() -> None:
    data = _sample_prd()

    task = update_task(
        data,
        "AW-002",
        status="in_progress",
        agent="tester",
        note="checking workflow",
    )

    assert task["status"] == "in_progress"
    assert task["owner"] == "tester"
    assert task["events"][-1]["note"] == "checking workflow"
