"""Question-bank corpus coverage audit utilities."""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class QuestionBankAudit:
    local_qp_count: int
    db_paper_count: int
    db_question_count: int
    db_tag_count: int
    missing_in_db: list[str]
    papers_without_questions: list[int]
    questions_without_tags: list[int]
    questions_without_topic: list[int]


def audit_questionbank(
    pdf_root: str | Path = "data/papers",
    db_path: str | Path = "data/questions.db",
) -> QuestionBankAudit:
    """Compare local QP PDFs with question-bank rows and tag coverage."""
    pdf_root = Path(pdf_root)
    db_path = Path(db_path)
    local_qps = sorted(pdf_root.rglob("*_qp_*.pdf")) if pdf_root.exists() else []
    local_qp_names = {path.name for path in local_qps}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        paper_rows = conn.execute(
            "SELECT id, pdf_path FROM papers ORDER BY id"
        ).fetchall()
        db_pdf_names = {
            Path(row["pdf_path"]).name
            for row in paper_rows
            if row["pdf_path"]
        }
        missing_in_db = sorted(local_qp_names - db_pdf_names)

        papers_without_questions = [
            row["id"]
            for row in conn.execute(
                """SELECT p.id
                   FROM papers p
                   LEFT JOIN questions q ON q.paper_id = p.id
                   GROUP BY p.id
                   HAVING COUNT(q.id) = 0
                   ORDER BY p.id"""
            )
        ]

        questions_without_tags = [
            row["id"]
            for row in conn.execute(
                """SELECT q.id
                   FROM questions q
                   WHERE NOT EXISTS (
                     SELECT 1 FROM question_tags qt WHERE qt.question_id = q.id
                   )
                   ORDER BY q.id"""
            )
        ]
        questions_without_topic = [
            row["id"]
            for row in conn.execute(
                """SELECT id
                   FROM questions
                   WHERE COALESCE(topic, '') = '' OR topic = 'unknown'
                   ORDER BY id"""
            )
        ]

        return QuestionBankAudit(
            local_qp_count=len(local_qps),
            db_paper_count=conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
            db_question_count=conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
            db_tag_count=conn.execute("SELECT COUNT(*) FROM question_tags").fetchone()[0],
            missing_in_db=missing_in_db,
            papers_without_questions=papers_without_questions,
            questions_without_tags=questions_without_tags,
            questions_without_topic=questions_without_topic,
        )
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit local past-paper question-bank coverage.")
    parser.add_argument("--pdf-root", default="data/papers")
    parser.add_argument("--db", default="data/questions.db")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    audit = audit_questionbank(pdf_root=args.pdf_root, db_path=args.db)
    if args.json:
        print(json.dumps(asdict(audit), ensure_ascii=False, indent=2))
        return

    print(f"Local QP PDFs: {audit.local_qp_count}")
    print(f"DB papers: {audit.db_paper_count}")
    print(f"DB questions: {audit.db_question_count}")
    print(f"DB tags: {audit.db_tag_count}")
    print(f"Missing local QPs in DB: {len(audit.missing_in_db)}")
    print(f"Papers without questions: {len(audit.papers_without_questions)}")
    print(f"Questions without tags: {len(audit.questions_without_tags)}")
    print(f"Questions without topic: {len(audit.questions_without_topic)}")
    if audit.missing_in_db:
        print("Missing examples:", ", ".join(audit.missing_in_db[:10]))
    if audit.papers_without_questions:
        print("Paper IDs without questions:", audit.papers_without_questions[:10])
    if audit.questions_without_tags:
        print("Question IDs without tags:", audit.questions_without_tags[:10])
    if audit.questions_without_topic:
        print("Question IDs without topic:", audit.questions_without_topic[:10])


if __name__ == "__main__":
    main()
