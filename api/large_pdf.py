from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

import fitz
from fastapi import HTTPException

from api import large_pdf_cache
from api.paper_resolver import parse_paper_code, resolve_paper_context

MAX_LARGE_PDF_BYTES = 80 * 1024 * 1024
MAX_LARGE_PDF_PAGES = 40
THUMBNAIL_WIDTH = 360
OCR_HINT_CHARS = 180

_COVER_KEYWORDS = (
    "candidate name",
    "centre number",
    "candidate number",
    "instructions",
    "answer all questions",
)
_ADDITIONAL_PAGE_KEYWORDS = (
    "additional page",
    "blank page",
    "if you use the following lined page",
    "not write on this page",
)


def _public_resolution(resolution: Any) -> dict:
    detail = resolution.event_detail()
    return {
        key: value
        for key, value in detail.items()
        if key not in {"catalog_match"}
    }


def _normalise_text(text: str) -> str:
    return " ".join(text.split())


def _cover_style_code(text: str) -> str | None:
    """Extract codes from CAIE cover text such as:
    ``MATHEMATICS 9709/11 ... May/June 2022``.
    """
    match = re.search(
        r"(?P<subject>\d{4})\s*/\s*(?P<component>[1-6][1-3]).{0,220}?"
        r"(?P<session>May\s*/?\s*June|May\s+June|Oct\s*/?\s*Nov|Oct\s+Nov|"
        r"October\s*/?\s*November|Feb\s*/?\s*Mar|Feb\s+Mar|February\s*/?\s*March)"
        r"\D+(?P<year>\d{4})",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    session_raw = match.group("session").lower()
    if "may" in session_raw:
        session = "s"
    elif "oct" in session_raw:
        session = "w"
    elif "feb" in session_raw:
        session = "m"
    else:
        return None

    year = int(match.group("year")) % 100
    return f"{match.group('subject')}_{session}{year:02d}_qp_{match.group('component')}"


def _infer_paper_code(filename: str, first_page_text: str) -> tuple[str, str] | None:
    candidates = [
        (filename, "page_header"),
        (_cover_style_code(first_page_text) or "", "cover"),
        (first_page_text, "cover"),
    ]
    for value, source in candidates:
        parsed = parse_paper_code(value)
        if parsed is not None:
            clean = Path(value).stem if source == "page_header" else value.strip()
            return clean, source
    return None


def _is_cover_page(page_number: int, text: str) -> bool:
    if page_number != 1:
        return False
    lower = text.lower()
    return any(keyword in lower for keyword in _COVER_KEYWORDS)


def _is_additional_or_blank_page(text: str) -> bool:
    lower = text.lower()
    if any(keyword in lower for keyword in _ADDITIONAL_PAGE_KEYWORDS):
        return True
    return len(lower) < 40


def _selected_by_default(page_number: int, text: str) -> bool:
    if _is_cover_page(page_number, text):
        return False
    if _is_additional_or_blank_page(text):
        return False
    return True


def _thumbnail_for_page(page: fitz.Page) -> dict:
    scale = THUMBNAIL_WIDTH / max(1, page.rect.width)
    matrix = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    jpeg = pix.tobytes("jpeg")
    text = _normalise_text(page.get_text("text"))
    page_number = page.number + 1
    return {
        "page": page_number,
        "thumbnail_b64": f"data:image/jpeg;base64,{base64.b64encode(jpeg).decode('ascii')}",
        "width": pix.width,
        "height": pix.height,
        "ocr_hint": text[:OCR_HINT_CHARS],
        "selected_by_default": _selected_by_default(page_number, text),
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

    inferred = None
    effective_paper_code = paper_code
    if not effective_paper_code.strip() and preview_pages:
        inferred = _infer_paper_code(filename, preview_pages[0].get("ocr_hint", ""))
        if inferred is not None:
            effective_paper_code = inferred[0]

    resolution = resolve_paper_context(
        upload_intent=upload_intent,
        paper_code=effective_paper_code,
        question_numbers=question_numbers,
        page_count=page_count,
    )
    public_resolution = _public_resolution(resolution)
    if inferred is not None and public_resolution.get("paper_id"):
        public_resolution["match_source"] = inferred[1]
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
