from __future__ import annotations

import sys
from pathlib import Path

import fitz
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.routes import MAX_PAGES_PER_REQUEST, _digital_past_paper_extracted, router
from api.large_pdf import build_large_pdf_user_hint, prepare_large_pdf
from api.large_pdf_cache import get as get_large_pdf_session
from questionbank.mineru_adapter import MinerUNotAvailableError, MinerUResult


FIXTURE_PDF = ROOT / "test" / "9709_s22_qp_11.pdf"


@pytest.fixture(autouse=True)
def _disable_real_mineru(monkeypatch):
    def fake_run_mineru_parse(*_args, **_kwargs):
        raise MinerUNotAvailableError("mineru disabled in tests")

    monkeypatch.setattr("api.large_pdf.run_mineru_parse", fake_run_mineru_parse)


def _blank_pdf(path: Path) -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "Student upload")
        doc.save(path)
    finally:
        doc.close()


def test_prepare_large_pdf_returns_session_and_thumbnails() -> None:
    prepared = prepare_large_pdf(FIXTURE_PDF, filename=FIXTURE_PDF.name)

    assert prepared["status"] == "ready"
    assert prepared["pdf_id"]
    assert prepared["filename"] == FIXTURE_PDF.name
    assert prepared["page_count"] == 20
    assert prepared["page_count"] <= MAX_PAGES_PER_REQUEST
    assert len(prepared["preview_pages"]) == prepared["page_count"]

    first_page = prepared["preview_pages"][0]
    assert first_page["page"] == 1
    assert first_page["thumbnail_b64"].startswith("data:image/jpeg;base64,")
    assert first_page["width"] > 0
    assert first_page["height"] > 0


def test_prepare_large_pdf_uses_mineru_markdown_for_paper_context_and_session(
    tmp_path,
    monkeypatch,
) -> None:
    upload_pdf = tmp_path / "student-upload.pdf"
    _blank_pdf(upload_pdf)
    mineru_dir = tmp_path / "mineru"
    mineru_dir.mkdir()
    markdown_path = mineru_dir / "student-upload.md"
    markdown_path.write_text(
        "# MATHEMATICS 9709/11\n\nMay/June 2022\n\n1 Find x. [2]",
        encoding="utf-8",
    )

    def fake_run_mineru_parse(path, **_kwargs):
        return MinerUResult(
            input_path=Path(path),
            output_dir=mineru_dir,
            markdown_path=markdown_path,
        )

    monkeypatch.setattr("api.large_pdf.run_mineru_parse", fake_run_mineru_parse)
    monkeypatch.setattr(
        "api.large_pdf.read_mineru_text",
        lambda _result: markdown_path.read_text(encoding="utf-8"),
    )

    prepared = prepare_large_pdf(
        upload_pdf,
        filename=upload_pdf.name,
        upload_intent="full_past_paper_pdf",
    )

    assert prepared["paper_resolution"]["paper_code"] == "9709_s22_qp_11"
    assert prepared["paper_resolution"]["paper_id"] == "9709_s22_11"
    assert prepared["paper_resolution"]["match_source"] == "mineru_markdown"
    assert prepared["document_parse"]["engine"] == "mineru"
    assert prepared["document_parse"]["status"] == "ready"
    assert prepared["document_parse"]["markdown_chars"] > 0
    assert "9709/11" in prepared["document_parse"]["markdown_preview"]
    assert "markdown_path" not in str(prepared)

    session = get_large_pdf_session(prepared["pdf_id"])
    assert session is not None
    assert session["mineru_markdown"].startswith("# MATHEMATICS")
    assert session["mineru_text"].startswith("# MATHEMATICS")
    assert session["document_parse"]["status"] == "ready"


def test_prepare_large_pdf_falls_back_when_mineru_is_unavailable(monkeypatch) -> None:
    def fake_run_mineru_parse(*_args, **_kwargs):
        raise MinerUNotAvailableError("missing mineru")

    monkeypatch.setattr("api.large_pdf.run_mineru_parse", fake_run_mineru_parse)

    prepared = prepare_large_pdf(FIXTURE_PDF, filename=FIXTURE_PDF.name)

    assert prepared["status"] == "ready"
    assert prepared["paper_resolution"]["paper_id"] == "9709_s22_11"
    assert prepared["document_parse"]["engine"] == "mineru"
    assert prepared["document_parse"]["status"] == "unavailable"


def test_prepare_large_pdf_limits_mineru_prepare_page_window(monkeypatch, tmp_path) -> None:
    calls: list[dict] = []
    markdown_path = tmp_path / "limited.md"
    markdown_path.write_text(
        "# MATHEMATICS 9709/11\n\nMay/June 2022\n\n1 Find x. [2]",
        encoding="utf-8",
    )

    def fake_run_mineru_parse(path, **kwargs):
        calls.append(kwargs)
        return MinerUResult(
            input_path=Path(path),
            output_dir=tmp_path,
            markdown_path=markdown_path,
        )

    monkeypatch.setattr("api.large_pdf.run_mineru_parse", fake_run_mineru_parse)
    monkeypatch.setattr(
        "api.large_pdf.read_mineru_text",
        lambda _result: markdown_path.read_text(encoding="utf-8"),
    )

    prepare_large_pdf(FIXTURE_PDF, filename="student-upload.pdf")

    assert calls
    assert calls[0]["start_page"] == 0
    assert calls[0]["end_page"] == 7
    assert calls[0]["method"] == "txt"
    assert calls[0]["timeout_seconds"] <= 10


def test_large_pdf_user_hint_keeps_mineru_context_short() -> None:
    long_markdown = "\n".join(
        f"{i} " + ("x" * 120)
        for i in range(80)
    )
    session = {
        "document_parse": {"status": "ready"},
        "question_spans": [
            {"question_number": "1", "snippet": "Find x. " + ("a" * 800)},
            {"question_number": "2", "snippet": "Show that y=3. " + ("b" * 800)},
        ],
        "mineru_markdown": long_markdown,
    }

    hint = build_large_pdf_user_hint("", session, [1])

    assert len(hint) <= 1800
    assert "MinerU detected question numbers: 1, 2" in hint
    assert "Find x." in hint
    assert "x" * 300 not in hint


def test_prepare_large_pdf_infers_paper_context_without_manual_code() -> None:
    prepared = prepare_large_pdf(
        FIXTURE_PDF,
        filename=FIXTURE_PDF.name,
        upload_intent="full_past_paper_pdf",
    )

    resolution = prepared["paper_resolution"]

    assert resolution["paper_code"] == "9709_s22_qp_11"
    assert resolution["paper_id"] == "9709_s22_11"
    assert resolution["paper_label"] == "CIE 9709/11 May/Jun 2022"
    assert resolution["match_confidence"] == "high"
    assert resolution["match_source"] in {"cover", "page_header"}
    assert resolution["grading_route"] == "past_paper_mark_scheme"
    assert resolution["needs_user_confirmation"] is False


def test_prepare_large_pdf_marks_default_process_pages() -> None:
    prepared = prepare_large_pdf(FIXTURE_PDF, filename=FIXTURE_PDF.name)

    pages = prepared["preview_pages"]
    default_pages = [
        page["page"]
        for page in pages
        if page.get("selected_by_default")
    ]

    assert default_pages
    assert 1 not in default_pages
    assert 20 not in default_pages
    assert default_pages == list(range(2, 20))


def test_digital_past_paper_fallback_uses_questionbank_text() -> None:
    prepared = prepare_large_pdf(
        FIXTURE_PDF,
        filename=FIXTURE_PDF.name,
        upload_intent="full_past_paper_pdf",
    )
    session = get_large_pdf_session(prepared["pdf_id"])
    assert session is not None

    extracted = _digital_past_paper_extracted(
        session=session,
        selected_pages=[2, 3],
        paper_context={
            **prepared["paper_resolution"],
            "catalog_match": {
                "subject": "9709",
                "year": 2022,
                "session": "s",
                "paper_num": 1,
                "variant": 1,
            },
        },
    )

    assert extracted is not None
    assert [item["question_number"] for item in extracted[:3]] == ["1(a)", "1(b)", "2"]
    assert all(item["student_answer"] == "" for item in extracted)
    assert all(item["working_steps"] == [] for item in extracted)
    assert all(item["grading_route"] == "past_paper_mark_scheme" for item in extracted)
    assert all(item["digital_past_paper_fallback"] is True for item in extracted)
    assert "Express $x^2 - 8x + 11$" in extracted[0]["question_text"]


def test_large_pdf_session_keeps_pdf_path_internal() -> None:
    prepared = prepare_large_pdf(FIXTURE_PDF, filename=FIXTURE_PDF.name)

    session = get_large_pdf_session(prepared["pdf_id"])

    assert session is not None
    assert session["pdf_path"] == str(FIXTURE_PDF)
    assert "pdf_path" not in prepared
    assert "qp_path" not in str(prepared)
    assert "ms_path" not in str(prepared)


def test_large_pdf_prepare_route_returns_public_session_payload() -> None:
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    with FIXTURE_PDF.open("rb") as f:
        response = client.post(
            "/large-pdf/prepare",
            files={"pdf": (FIXTURE_PDF.name, f, "application/pdf")},
            data={"upload_intent": "full_past_paper_pdf"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["pdf_id"]
    assert payload["page_count"] == 20
    assert payload["page_count"] <= MAX_PAGES_PER_REQUEST
    assert payload["preview_pages"][0]["thumbnail_b64"].startswith("data:image/jpeg;base64,")
    assert "pdf_path" not in payload
    assert "paper_resolution" in payload


def test_large_pdf_analyze_stream_uses_cached_mineru_context(
    tmp_path,
    monkeypatch,
) -> None:
    upload_pdf = tmp_path / "student-upload.pdf"
    _blank_pdf(upload_pdf)
    mineru_dir = tmp_path / "mineru"
    mineru_dir.mkdir()
    markdown_path = mineru_dir / "student-upload.md"
    markdown_path.write_text(
        "# MATHEMATICS 9709/11\n\nMay/June 2022\n\n1 Find x. [2]",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "api.large_pdf.run_mineru_parse",
        lambda path, **_kwargs: MinerUResult(
            input_path=Path(path),
            output_dir=mineru_dir,
            markdown_path=markdown_path,
        ),
    )
    monkeypatch.setattr(
        "api.large_pdf.read_mineru_text",
        lambda _result: markdown_path.read_text(encoding="utf-8"),
    )
    prepared = prepare_large_pdf(upload_pdf, filename=upload_pdf.name)

    captured: dict = {}

    def fake_run_pipeline_streaming(image_paths, *_args, **kwargs):
        captured["image_paths"] = list(image_paths)
        captured["user_hint"] = _args[2]
        captured["paper_context"] = kwargs["paper_context"]
        captured["recognition_timeout_seconds"] = kwargs["recognition_timeout_seconds"]
        yield ("segmentation", {"question_count": 0, "questions_preview": []})
        yield ("summary", {})
        yield ("done", {})

    monkeypatch.setattr("api.routes.run_pipeline_streaming", fake_run_pipeline_streaming)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.post(
        f"/large-pdf/{prepared['pdf_id']}/analyze-stream",
        data={
            "selected_pages": "1",
            "upload_intent": "full_past_paper_pdf",
        },
    )

    assert response.status_code == 200
    assert "event: segmentation" in response.text
    assert captured["image_paths"]
    assert "MinerU Markdown" in captured["user_hint"]
    assert "9709/11" in captured["user_hint"]
    assert captured["paper_context"]["paper_id"] == "9709_s22_11"
    assert captured["paper_context"]["grading_route"] == "past_paper_mark_scheme"
    assert captured["recognition_timeout_seconds"] <= 10
