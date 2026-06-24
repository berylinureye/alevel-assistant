from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Literal

MatchConfidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class QuestionBankMarkSchemeContext:
    question_id: int
    question_number: str
    confidence: MatchConfidence
    reason: str
    text: str


def _question_key(value: object) -> str | None:
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else None


def _normalise_question_number(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\b(question|q)\b", "", text)
    return re.sub(r"[^0-9a-z]+", "", text)


def _safe_json_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    raw = str(value).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [raw]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    if parsed is None:
        return []
    return [str(parsed)]


def _catalog_int(catalog_match: dict, key: str) -> int | None:
    try:
        return int(catalog_match.get(key))
    except (TypeError, ValueError):
        return None


def _catalog_str(catalog_match: dict, key: str) -> str | None:
    raw = catalog_match.get(key)
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _fetch_candidates(
    conn: sqlite3.Connection,
    *,
    catalog_match: dict,
    question_number: str,
) -> list[sqlite3.Row]:
    subject = _catalog_str(catalog_match, "subject")
    year = _catalog_int(catalog_match, "year")
    session = _catalog_str(catalog_match, "session")
    paper_num = _catalog_int(catalog_match, "paper_num")
    variant = _catalog_int(catalog_match, "variant")
    qkey = _question_key(question_number)
    if not all([subject, year, session, paper_num, variant, qkey]):
        return []

    rows = conn.execute(
        """SELECT q.*, p.subject_code, p.year, p.session, p.paper_num, p.variant
           FROM questions q
           JOIN papers p ON q.paper_id = p.id
           WHERE p.subject_code = ?
             AND p.year = ?
             AND p.session = ?
             AND p.paper_num = ?
             AND p.variant = ?
           ORDER BY q.question_number""",
        (subject, year, session, paper_num, variant),
    ).fetchall()

    return [
        row
        for row in rows
        if _question_key(row["question_number"]) == qkey
    ]


def _select_best_match(
    rows: list[sqlite3.Row],
    *,
    question_number: str,
) -> tuple[sqlite3.Row, MatchConfidence, str] | None:
    if not rows:
        return None

    target_norm = _normalise_question_number(question_number)
    target_key = _question_key(question_number)

    exact = [
        row for row in rows
        if _normalise_question_number(row["question_number"]) == target_norm
    ]
    if exact:
        return exact[0], "high", "Exact question-number match."

    ordered = sorted(
        rows,
        key=lambda row: (
            len(_normalise_question_number(row["question_number"])),
            _normalise_question_number(row["question_number"]),
        ),
    )
    if target_norm == (target_key or ""):
        return ordered[0], "medium", "Matched the same top-level question group."

    return ordered[0], "medium", "Matched by top-level question number; subpart was not exact."


def _fetch_tags(conn: sqlite3.Connection, question_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT tag FROM question_tags WHERE question_id = ? ORDER BY tag",
        (question_id,),
    ).fetchall()
    return [str(row["tag"]) for row in rows]


def _clip(text: object, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n[Clipped for prompt length.]"


def _format_bullets(title: str, items: list[str], *, item_limit: int = 8) -> list[str]:
    if not items:
        return []
    lines = [f"{title}:"]
    for item in items[:item_limit]:
        lines.append(f"- {item}")
    if len(items) > item_limit:
        lines.append(f"- ... {len(items) - item_limit} more")
    return lines


def _format_context(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    confidence: MatchConfidence,
    reason: str,
    max_chars: int,
) -> str:
    question_id = int(row["id"])
    tags = _fetch_tags(conn, question_id)
    marking_points = _safe_json_list(row["marking_points"])
    common_errors = _safe_json_list(row["common_errors"])

    topic = (row["topic"] or "unknown").strip()
    subtopic = (row["subtopic"] or "unknown").strip()

    lines = [
        "Matched question bank record from the same past paper:",
        f"- question_id: {question_id}",
        f"- match_confidence: {confidence} ({reason})",
        f"- stored_question_number: {row['question_number']}",
        f"- marks: {row['marks'] or 0}",
        f"- topic/subtopic: {topic} / {subtopic}",
    ]
    if tags:
        lines.append(f"- tags: {', '.join(tags)}")

    lines.extend(["", "Stored question text:", _clip(row["question_text"], 900)])

    if row["correct_answer"]:
        lines.extend(["", "Stored official answer:", _clip(row["correct_answer"], 500)])

    if marking_points:
        lines.append("")
        lines.extend(_format_bullets("Structured marking points", marking_points))

    if common_errors:
        lines.append("")
        lines.extend(_format_bullets("Common errors seen in parsing/marking", common_errors))

    return _clip("\n".join(lines).strip(), max_chars)


def build_questionbank_mark_scheme_context(
    conn: sqlite3.Connection,
    *,
    catalog_match: dict | None,
    question_number: str,
    max_chars: int = 2600,
) -> QuestionBankMarkSchemeContext | None:
    """Build structured mark-scheme context for a matched past-paper question.

    The match is deliberately strict at the paper level: subject, year, session,
    paper number, and variant must all match the catalog row before any question
    number matching happens.
    """
    if not isinstance(catalog_match, dict):
        return None

    rows = _fetch_candidates(
        conn,
        catalog_match=catalog_match,
        question_number=question_number,
    )
    selected = _select_best_match(rows, question_number=question_number)
    if selected is None:
        return None

    row, confidence, reason = selected
    text = _format_context(
        conn,
        row,
        confidence=confidence,
        reason=reason,
        max_chars=max_chars,
    )
    return QuestionBankMarkSchemeContext(
        question_id=int(row["id"]),
        question_number=str(row["question_number"]),
        confidence=confidence,
        reason=reason,
        text=text,
    )
