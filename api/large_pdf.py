from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import fitz
from fastapi import HTTPException

from api import large_pdf_cache
from api.paper_resolver import resolve_paper_context

MAX_LARGE_PDF_BYTES = 80 * 1024 * 1024
MAX_LARGE_PDF_PAGES = 40
THUMBNAIL_WIDTH = 360
OCR_HINT_CHARS = 180


def _public_resolution(resolution: Any) -> dict:
    detail = resolution.event_detail()
    return {
        key: value
        for key, value in detail.items()
        if key not in {"catalog_match"}
    }


def _thumbnail_for_page(page: fitz.Page) -> dict:
    scale = THUMBNAIL_WIDTH / max(1, page.rect.width)
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    jpeg = pix.tobytes("jpeg")
    text = " ".join(page.get_text("text").split())
    return {
        "page": page.number + 1,
        "thumbnail_b64": f"data:image/jpeg;base64,{base64.b64encode(jpeg).decode('ascii')}",
        "width": pix.width,
        "height": pix.height,
        "ocr_hint": text[:OCR_HINT_CHARS],
    }


def _validate_pdf_path(pdf_path: Path) -> None:
    if not pdf_path.exists():
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_PDF", "message": "PDF file does not exist."},
        )
    if pdf_path.stat().st_size > MAX_LARGE_PDF_BYTES:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "PDF_TOO_LARGE",
                "message": f"Max allowed PDF size is {MAX_LARGE_PDF_BYTES // 1024 // 1024} MB.",
            },
        )


def prepare_large_pdf(
    pdf_path: str | Path,
    *,
    filename: str,
    upload_intent: str = "full_past_paper_pdf",
    paper_code: str = "",
    question_numbers: str = "",
    delete_on_remove: bool = False,
) -> dict:
    path = Path(pdf_path)
    _validate_pdf_path(path)

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_PDF", "message": f"Cannot open PDF: {exc}"},
        ) from exc

    try:
        page_count = doc.page_count
        if page_count <= 0:
            raise HTTPException(
                status_code=400,
                detail={"error_code": "INVALID_PDF", "message": "PDF has no pages."},
            )
        if page_count > MAX_LARGE_PDF_PAGES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "TOO_MANY_PDF_PAGES",
                    "message": f"Max {MAX_LARGE_PDF_PAGES} pages per Large PDF session.",
                },
            )

        preview_pages = [_thumbnail_for_page(doc.load_page(i)) for i in range(page_count)]
    finally:
        doc.close()

    resolution = resolve_paper_context(
        upload_intent=upload_intent,
        paper_code=paper_code,
        question_numbers=question_numbers,
        page_count=page_count,
    )
    public_resolution = _public_resolution(resolution)
    pdf_id = large_pdf_cache.store(
        pdf_path=str(path),
        filename=filename,
        page_count=page_count,
        preview_pages=preview_pages,
        paper_resolution=public_resolution,
        delete_on_remove=delete_on_remove,
    )

    return {
        "status": "ready",
        "pdf_id": pdf_id,
        "filename": filename,
        "page_count": page_count,
        "preview_pages": preview_pages,
        "paper_resolution": public_resolution,
    }
