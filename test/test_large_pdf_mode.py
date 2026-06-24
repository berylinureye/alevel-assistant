from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.routes import MAX_PAGES_PER_REQUEST, router
from api.large_pdf import prepare_large_pdf
from api.large_pdf_cache import get as get_large_pdf_session


FIXTURE_PDF = ROOT / "test" / "9709_s22_qp_11.pdf"


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
