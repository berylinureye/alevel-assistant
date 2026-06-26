from __future__ import annotations

from pathlib import Path

from questionbank.database import (
    get_connection,
    get_random_questions,
    init_db,
    insert_question,
    upsert_paper,
)
from questionbank.models import QuestionBankItem


def _seed_question(db_path: Path) -> None:
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
            pdf_path="9709_s22_qp_11.pdf",
        )
        insert_question(
            conn,
            QuestionBankItem(
                paper_id=paper_id,
                question_number="7",
                question_text="The circle has centre C and tangent at A.",
                topic="coordinate_geometry",
                subtopic="equation_of_circle",
                difficulty=3,
                tags=["equation_of_circle", "tangent_to_circle"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_get_random_questions_matches_parent_topic(tmp_path):
    db_path = tmp_path / "questions.db"
    _seed_question(db_path)
    conn = get_connection(db_path)
    try:
        questions, total = get_random_questions(conn, topics=["coordinate_geometry"], count=5)
    finally:
        conn.close()

    assert total == 1
    assert [q.question_number for q in questions] == ["7"]


def test_get_random_questions_matches_subtopic_key(tmp_path):
    db_path = tmp_path / "questions.db"
    _seed_question(db_path)
    conn = get_connection(db_path)
    try:
        questions, total = get_random_questions(conn, topics=["equation_of_circle"], count=5)
    finally:
        conn.close()

    assert total == 1
    assert [q.question_number for q in questions] == ["7"]


def test_get_random_questions_matches_tag_key(tmp_path):
    db_path = tmp_path / "questions.db"
    _seed_question(db_path)
    conn = get_connection(db_path)
    try:
        questions, total = get_random_questions(conn, topics=["tangent_to_circle"], count=5)
    finally:
        conn.close()

    assert total == 1
    assert [q.question_number for q in questions] == ["7"]


def test_get_random_questions_keeps_exclude_filter_with_tag_lookup(tmp_path):
    db_path = tmp_path / "questions.db"
    _seed_question(db_path)
    conn = get_connection(db_path)
    try:
        first, _total = get_random_questions(conn, topics=["tangent_to_circle"], count=1)
        questions, total = get_random_questions(
            conn,
            topics=["tangent_to_circle"],
            count=5,
            exclude_ids=[first[0].id],
        )
    finally:
        conn.close()

    assert total == 0
    assert questions == []
