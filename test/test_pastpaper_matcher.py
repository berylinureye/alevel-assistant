from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from questionbank.database import get_connection, init_db, insert_question, upsert_paper
from questionbank.models import QuestionBankItem
from questionbank.pastpaper_matcher import build_questionbank_mark_scheme_context


def _seed_db(tmp_path: Path):
    db_path = tmp_path / "questions.db"
    init_db(db_path)
    conn = get_connection(db_path)
    paper_id = upsert_paper(
        conn,
        subject_code="9709",
        year=2022,
        session="s",
        paper_num=4,
        variant=1,
        pdf_path="data/papers/9709/2022/9709_s22_qp_41.pdf",
        ms_pdf_path="data/papers/9709/2022/9709_s22_ms_41.pdf",
    )
    q1a_id = insert_question(
        conn,
        QuestionBankItem(
            paper_id=paper_id,
            question_number="1(a)",
            question_text="A car starts from rest and accelerates uniformly. Find the time.",
            marks=2,
            topic="mechanics",
            subtopic="kinematics",
            correct_answer="$t=16$ s",
            marking_points=[
                "M1: Use a complete constant acceleration method.",
                "A1: Obtain $t=16\\text{ s}$.",
            ],
            common_errors=["Using final speed as average speed."],
            tags=["constant_acceleration", "velocity_time_graph"],
        )
    )
    insert_question(
        conn,
        QuestionBankItem(
            paper_id=paper_id,
            question_number="1(b)",
            question_text="Sketch the velocity-time graph.",
            marks=2,
            topic="mechanics",
            subtopic="kinematics",
            marking_points=["B1: Correct trapezium shape."],
            tags=["velocity_time_graph"],
        )
    )
    conn.commit()
    return conn, q1a_id


def _catalog_match() -> dict:
    return {
        "subject": "9709",
        "year": 2022,
        "session": "s",
        "paper_num": 4,
        "variant": 1,
    }


def test_questionbank_matcher_finds_exact_subpart_and_formats_scoring_context(tmp_path) -> None:
    conn, q1a_id = _seed_db(tmp_path)

    context = build_questionbank_mark_scheme_context(
        conn,
        catalog_match=_catalog_match(),
        question_number="1(a)",
    )

    assert context is not None
    assert context.question_id == q1a_id
    assert context.question_number == "1(a)"
    assert context.confidence == "high"
    assert "question_id: " + str(q1a_id) in context.text
    assert "stored_question_number: 1(a)" in context.text
    assert "topic/subtopic: mechanics / kinematics" in context.text
    assert "tags: constant_acceleration, velocity_time_graph" in context.text
    assert "A car starts from rest" in context.text
    assert "$t=16$ s" in context.text
    assert "M1: Use a complete constant acceleration method." in context.text
    assert "Using final speed as average speed." in context.text

    conn.close()


def test_questionbank_matcher_falls_back_to_top_level_group(tmp_path) -> None:
    conn, q1a_id = _seed_db(tmp_path)

    context = build_questionbank_mark_scheme_context(
        conn,
        catalog_match=_catalog_match(),
        question_number="1",
    )

    assert context is not None
    assert context.question_id == q1a_id
    assert context.confidence == "medium"
    assert "same top-level question group" in context.reason

    conn.close()


def test_questionbank_matcher_does_not_cross_paper_identity(tmp_path) -> None:
    conn, _q1a_id = _seed_db(tmp_path)
    wrong_variant = {**_catalog_match(), "variant": 2}

    context = build_questionbank_mark_scheme_context(
        conn,
        catalog_match=wrong_variant,
        question_number="1(a)",
    )

    assert context is None
    conn.close()
