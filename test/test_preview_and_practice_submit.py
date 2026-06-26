from __future__ import annotations

import asyncio
import base64
import io
from types import SimpleNamespace

from PIL import Image

import api.qb_routes as qb_routes
from questionbank.database import get_connection, init_db, insert_question, upsert_paper
from questionbank.models import QuestionBankItem, SubmitAnswerRequest


def test_make_preview_data_url_returns_browser_renderable_jpeg(tmp_path):
    from api.routes import _make_preview_data_url

    image_path = tmp_path / "page.png"
    Image.new("RGBA", (120, 80), (255, 255, 255, 0)).save(image_path)

    data_url = _make_preview_data_url(image_path.read_bytes())

    assert data_url is not None
    assert data_url.startswith("data:image/jpeg;base64,")


def test_make_preview_data_url_applies_exif_orientation(tmp_path):
    from api.routes import _make_preview_data_url

    image_path = tmp_path / "iphone-page.jpg"
    img = Image.new("RGB", (120, 80), "white")
    exif = Image.Exif()
    exif[274] = 6
    img.save(image_path, format="JPEG", exif=exif)

    data_url = _make_preview_data_url(image_path.read_bytes())

    assert data_url is not None
    encoded = data_url.removeprefix("data:image/jpeg;base64,")
    preview = Image.open(io.BytesIO(base64.b64decode(encoded)))
    assert preview.size == (80, 120)


def test_submit_answer_uses_fast_local_marking_without_llm(monkeypatch, tmp_path):
    db_path = tmp_path / "questions.db"
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        paper_id = upsert_paper(
            conn,
            subject_code="9709",
            year=2025,
            session="s",
            paper_num=5,
            variant=3,
        )
        question_id = insert_question(
            conn,
            QuestionBankItem(
                paper_id=paper_id,
                question_number="6(b)",
                parent_number="6",
                parent_stem=(
                    "A company sells bags of pasta. The masses of large bags of pasta "
                    "are normally distributed with mean 2.50 kg and standard deviation 0.12 kg."
                ),
                question_text=(
                    "A restaurant manager buys 160 of these large bags of pasta. "
                    "Find the number of bags for which you would expect the mass of pasta "
                    "to be more than 1.65 standard deviations above the mean."
                ),
                marks=3,
                topic="normal_distribution",
                subtopic="normal_distribution",
                correct_answer="15",
                marking_points=["B1: 15"],
                difficulty=3,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(qb_routes, "ensure_db", lambda: get_connection(db_path))

    def fail_grade(*_args, **_kwargs):
        raise AssertionError("practice submit should not depend on the LLM for exact reference answers")

    import grader.grader as grader_module

    monkeypatch.setattr(grader_module, "grade_question", fail_grade)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(registry={})))

    response = asyncio.run(
        qb_routes.submit_answer(
            SubmitAnswerRequest(
                question_id=question_id,
                student_answer="15",
                working_steps=[],
            ),
            request,
        )
    )

    assert response["status"] == "success"
    assert response["grade_result"]["is_correct"] is True
    assert response["grade_result"]["score"] == 3
    assert response["grade_result"]["full_score"] == 3
    assert response["reference_answer"] == "15"


def test_submit_answer_derives_normal_distribution_expected_count(monkeypatch, tmp_path):
    db_path = tmp_path / "questions.db"
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        paper_id = upsert_paper(
            conn,
            subject_code="9709",
            year=2025,
            session="s",
            paper_num=5,
            variant=3,
        )
        question_id = insert_question(
            conn,
            QuestionBankItem(
                paper_id=paper_id,
                question_number="6(b)",
                question_text=(
                    "A restaurant manager buys 160 of these large bags of pasta. "
                    "Find the number of bags for which you would expect the mass of pasta "
                    "to be more than 1.65 standard deviations above the mean."
                ),
                marks=3,
                topic="normal_distribution",
                subtopic="expected_value",
                correct_answer=None,
                difficulty=3,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(qb_routes, "ensure_db", lambda: get_connection(db_path))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(registry={})))

    response = asyncio.run(
        qb_routes.submit_answer(
            SubmitAnswerRequest(
                question_id=question_id,
                student_answer="15",
                working_steps=[],
            ),
            request,
        )
    )

    assert response["status"] == "success"
    assert response["reference_answer"] == "8"
    assert response["grade_result"]["is_correct"] is False
    assert response["grade_result"]["score"] == 0
    assert response["grade_result"]["error_type"] == "incorrect_answer"
