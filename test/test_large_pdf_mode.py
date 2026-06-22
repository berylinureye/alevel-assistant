from __future__ import annotations

import sys
from pathlib import Path

import fitz
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.routes import MAX_PAGES_PER_REQUEST, router
from api.large_pdf import prepare_large_pdf
from api.large_pdf_cache import get as get_large_pdf_session


def make_large_pdf(tmp_path: Path) -> Path:
    fixture_pdf = tmp_path / "large-pdf-fixture.pdf"
    doc = fitz.open()
    try:
        for page_number in range(MAX_PAGES_PER_REQUEST + 1):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 72), f"Test PDF page {page_number + 1}")
        doc.save(fixture_pdf)
    finally:
        doc.close()
    return fixture_pdf


def test_prepare_large_pdf_returns_session_and_thumbnails(tmp_path: Path) -> None:
    fixture_pdf = make_large_pdf(tmp_path)
    prepared = prepare_large_pdf(fixture_pdf, filename=fixture_pdf.name)

    assert prepared["status"] == "ready"
    assert prepared["pdf_id"]
    assert prepared["filename"] == fixture_pdf.name
    assert prepared["page_count"] > MAX_PAGES_PER_REQUEST
    assert len(prepared["preview_pages"]) == prepared["page_count"]

    first_page = prepared["preview_pages"][0]
    assert first_page["page"] == 1
    assert first_page["thumbnail_b64"].startswith("data:image/jpeg;base64,")
    assert first_page["width"] > 0
    assert first_page["height"] > 0


def test_large_pdf_session_keeps_pdf_path_internal(tmp_path: Path) -> None:
    fixture_pdf = make_large_pdf(tmp_path)
    prepared = prepare_large_pdf(fixture_pdf, filename=fixture_pdf.name)

    session = get_large_pdf_session(prepared["pdf_id"])

    assert session is not None
    assert session["pdf_path"] == str(fixture_pdf)
    assert "pdf_path" not in prepared
    assert "qp_path" not in str(prepared)
    assert "ms_path" not in str(prepared)


def test_large_pdf_prepare_route_returns_public_session_payload(tmp_path: Path) -> None:
    fixture_pdf = make_large_pdf(tmp_path)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    with fixture_pdf.open("rb") as f:
        response = client.post(
            "/large-pdf/prepare",
            files={"pdf": (fixture_pdf.name, f, "application/pdf")},
            data={"upload_intent": "full_past_paper_pdf"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["pdf_id"]
    assert payload["page_count"] > MAX_PAGES_PER_REQUEST
    assert payload["preview_pages"][0]["thumbnail_b64"].startswith("data:image/jpeg;base64,")
    assert "pdf_path" not in payload
    assert "paper_resolution" in payload
