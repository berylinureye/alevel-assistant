from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "agent_workflow"
PRD_PATH = WORKFLOW_DIR / "prd.json"
PROGRESS_PATH = WORKFLOW_DIR / "progress.md"

STATUS_ORDER = {"in_progress": 0, "pending": 1, "blocked": 2, "completed": 3}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_prd(path: Path = PRD_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("tasks"), list):
        raise ValueError("prd.json must contain a tasks array")
    return data


def save_prd(data: dict[str, Any], path: Path = PRD_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def append_progress(line: str, path: Path = PROGRESS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n- {utc_now()} {line}\n")


def task_sort_key(task: dict[str, Any]) -> tuple[int, int, str]:
    status = str(task.get("status", "pending"))
    priority = str(task.get("priority", "P2"))
    return (
        STATUS_ORDER.get(status, 99),
        PRIORITY_ORDER.get(priority, 99),
        str(task.get("id", "")),
    )


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for task in data["tasks"]:
        status = str(task.get("status", "pending"))
        counts[status] = counts.get(status, 0) + 1
    next_task = choose_next(data)
    return {
        "project": data.get("project"),
        "workflow": data.get("workflow"),
        "counts": counts,
        "next": next_task,
    }


def choose_next(data: dict[str, Any]) -> dict[str, Any] | None:
    candidates = [
        task for task in data["tasks"]
        if task.get("status", "pending") in {"in_progress", "pending", "blocked"}
    ]
    if not candidates:
        return None
    return sorted(candidates, key=task_sort_key)[0]


def find_task(data: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in data["tasks"]:
        if task.get("id") == task_id:
            return task
    raise KeyError(f"Unknown task id: {task_id}")


def update_task(
    data: dict[str, Any],
    task_id: str,
    *,
    status: str,
    agent: str,
    note: str,
) -> dict[str, Any]:
    task = find_task(data, task_id)
    task["status"] = status
    task["owner"] = agent
    task["updated_at"] = utc_now()
    task.setdefault("events", []).append({
        "at": task["updated_at"],
        "agent": agent,
        "status": status,
        "note": note,
    })
    return task


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="A-Level Assistant long-running agent workflow helper")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show task counts and next task")
    sub.add_parser("next", help="Show the next task only")

    for command in ("start", "complete", "block"):
        p = sub.add_parser(command)
        p.add_argument("task_id")
        p.add_argument("--agent", required=True)
        p.add_argument("--note", default="")

    note_p = sub.add_parser("note")
    note_p.add_argument("--agent", required=True)
    note_p.add_argument("--text", required=True)

    args = parser.parse_args()

    if args.command == "note":
        append_progress(f"{args.agent}: {args.text}")
        print_json({"status": "ok"})
        return

    data = load_prd()

    if args.command == "status":
        print_json(summarize(data))
        return

    if args.command == "next":
        print_json(choose_next(data))
        return

    status_by_command = {
        "start": "in_progress",
        "complete": "completed",
        "block": "blocked",
    }
    status = status_by_command[args.command]
    task = update_task(
        data,
        args.task_id,
        status=status,
        agent=args.agent,
        note=args.note,
    )
    save_prd(data)
    append_progress(f"{args.agent}: {args.command} {args.task_id} - {args.note}")
    print_json(task)


if __name__ == "__main__":
    main()
