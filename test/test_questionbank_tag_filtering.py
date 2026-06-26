from __future__ import annotations

from pathlib import Path

from questionbank.database import (
    get_connection,
    get_question_by_id,
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


def test_legacy_subquestion_gets_previous_sibling_as_parent_context(tmp_path):
    db_path = tmp_path / "questions.db"
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        paper_id = upsert_paper(
            conn,
            subject_code="9709",
            year=2017,
            session="w",
            paper_num=6,
            variant=3,
            pdf_path="9709_w17_qp_63.pdf",
        )
        insert_question(
            conn,
            QuestionBankItem(
                paper_id=paper_id,
                question_number="4(i)",
                parent_number="4",
                question_text=(
                    "A fair die with faces numbered 1, 2, 2, 2, 3, 6 is thrown. "
                    "The score, $X$, is found by squaring the number on the face "
                    "the die shows and then subtracting 4. Draw up a table to show "
                    "the probability distribution of $X$."
                ),
                topic="discrete_random_variables",
                subtopic="probability_distribution",
                difficulty=2,
            ),
        )
        q4ii_id = insert_question(
            conn,
            QuestionBankItem(
                paper_id=paper_id,
                question_number="4(ii)",
                parent_number="4",
                question_text="Find $E(X)$ and $\\mathrm{Var}(X)$.",
                topic="discrete_random_variables",
                subtopic="expectation_and_variance",
                difficulty=2,
            ),
        )
        conn.commit()

        question = get_question_by_id(conn, q4ii_id)
    finally:
        conn.close()

    assert question is not None
    assert question.question_text == "Find $E(X)$ and $\\mathrm{Var}(X)$."
    assert question.parent_stem is not None
    assert "faces numbered 1, 2, 2, 2, 3, 6" in question.parent_stem
    assert "Q4(i):" in question.parent_stem
