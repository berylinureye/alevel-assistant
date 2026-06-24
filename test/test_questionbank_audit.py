from __future__ import annotations

from pathlib import Path

from questionbank.database import get_connection, init_db, insert_question, upsert_paper
from questionbank.models import QuestionBankItem
from questionbank.audit import audit_questionbank


def _make_qp(root: Path, name: str) -> Path:
    path = root / "9709" / "2022" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n")
    return path


def test_audit_counts_complete_tagged_paper(tmp_path):
    pdf_root = tmp_path / "papers"
    db_path = tmp_path / "questions.db"
    qp = _make_qp(pdf_root, "9709_s22_qp_11.pdf")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        paper_id = upsert_paper(
            conn,
            subject_code="9709",
            year=2022,
            session="s",
            paper_num=1,
            variant=1,
            pdf_path=str(qp),
        )
        insert_question(
            conn,
            QuestionBankItem(
                paper_id=paper_id,
                question_number="1",
                question_text="Find x.",
                topic="coordinate_geometry",
                subtopic="equation_of_circle",
                tags=["equation_of_circle"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    audit = audit_questionbank(pdf_root=pdf_root, db_path=db_path)

    assert audit.local_qp_count == 1
    assert audit.db_paper_count == 1
    assert audit.db_question_count == 1
    assert audit.db_tag_count == 1
    assert audit.missing_in_db == []
    assert audit.papers_without_questions == []
    assert audit.questions_without_tags == []
    assert audit.questions_without_topic == []


def test_audit_reports_local_qp_missing_from_db(tmp_path):
    pdf_root = tmp_path / "papers"
    db_path = tmp_path / "questions.db"
    _make_qp(pdf_root, "9709_s22_qp_11.pdf")
    init_db(db_path)

    audit = audit_questionbank(pdf_root=pdf_root, db_path=db_path)

    assert audit.local_qp_count == 1
    assert audit.db_paper_count == 0
    assert audit.missing_in_db == ["9709_s22_qp_11.pdf"]


def test_audit_reports_questions_without_tags(tmp_path):
    pdf_root = tmp_path / "papers"
    db_path = tmp_path / "questions.db"
    qp = _make_qp(pdf_root, "9709_s22_qp_11.pdf")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        paper_id = upsert_paper(
            conn,
            subject_code="9709",
            year=2022,
            session="s",
            paper_num=1,
            variant=1,
            pdf_path=str(qp),
        )
        insert_question(
            conn,
            QuestionBankItem(
                paper_id=paper_id,
                question_number="1",
                question_text="Find x.",
                topic="coordinate_geometry",
                subtopic="equation_of_circle",
                tags=[],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    audit = audit_questionbank(pdf_root=pdf_root, db_path=db_path)

    assert audit.questions_without_tags == [1]
