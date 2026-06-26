from __future__ import annotations

import base64
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import fitz
from fastapi import HTTPException

from api import large_pdf_cache
from api.paper_resolver import parse_paper_code, resolve_paper_context
from questionbank.mineru_adapter import (
    MinerUError,
    MinerUNotAvailableError,
    read_mineru_text,
    run_mineru_parse,
)

MAX_LARGE_PDF_BYTES = 80 * 1024 * 1024
MAX_LARGE_PDF_PAGES = 40
THUMBNAIL_WIDTH = 360
OCR_HINT_CHARS = 180
MINERU_MARKDOWN_PREVIEW_CHARS = 1200
MINERU_PIPELINE_HINT_CHARS = 700
MINERU_QUESTION_SNIPPET_CHARS = 240
MINERU_HINT_MAX_SPANS = 4
DEFAULT_MINERU_PREPARE_PAGES = 8
DEFAULT_LARGE_PDF_MINERU_METHOD = "txt"
DEFAULT_LARGE_PDF_MINERU_TIMEOUT_SECONDS = 8
LARGE_PDF_RECOGNITION_TIMEOUT_SECONDS = 10.0
DEFAULT_LARGE_PDF_MINERU_OUTPUT_DIR = Path("data/large_pdf_mineru")

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


def _truthy_env(value: str | None, *, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(1, value)


def _clip_hint_text(text: object, max_chars: int) -> str:
    compact = _normalise_text(str(text or ""))
    if len(compact) <= max_chars:
        return compact
    return compact[: max(0, max_chars - 3)].rstrip() + "..."


def _read_markdown_file(result: Any) -> str:
    markdown_path = getattr(result, "markdown_path", None)
    if markdown_path and Path(markdown_path).exists():
        return Path(markdown_path).read_text(encoding="utf-8").strip()
    return ""


def _safe_mineru_error(exc: Exception) -> str:
    if isinstance(exc, MinerUNotAvailableError):
        return "MinerU CLI unavailable; using PDF text fallback."
    if isinstance(exc, MinerUError):
        return "MinerU parse failed; using PDF text fallback."
    return "MinerU parse unavailable; using PDF text fallback."


def _question_number_from_match(match: re.Match[str]) -> str | None:
    raw = match.group("number")
    number = re.search(r"\d+", raw)
    if not number:
        return None
    try:
        if int(number.group(0)) > 40:
            return None
    except ValueError:
        return None
    return re.sub(r"\s+", "", raw)


def _extract_question_spans(markdown: str) -> list[dict]:
    text = markdown.strip()
    if not text:
        return []
    pattern = re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:question\s*)?(?P<number>\d{1,2}(?:\s*\([a-zivx]+\))?)\b"
    )
    matches: list[tuple[str, int]] = []
    seen_at: set[int] = set()
    for match in pattern.finditer(text):
        number = _question_number_from_match(match)
        if not number or match.start() in seen_at:
            continue
        seen_at.add(match.start())
        matches.append((number, match.start()))

    spans: list[dict] = []
    for idx, (number, start) in enumerate(matches):
        end = matches[idx + 1][1] if idx + 1 < len(matches) else len(text)
        snippet = _normalise_text(text[start:end])[:700]
        spans.append(
            {
                "question_number": number,
                "markdown_start": start,
                "markdown_end": end,
                "snippet": snippet,
            }
        )
    return spans


def _mineru_prepare_page_window(page_count: int) -> tuple[int, int]:
    configured = os.environ.get("LARGE_PDF_MINERU_PREPARE_PAGES")
    try:
        window = int(configured) if configured is not None else DEFAULT_MINERU_PREPARE_PAGES
    except ValueError:
        window = DEFAULT_MINERU_PREPARE_PAGES
    window = max(1, window)
    return 0, min(max(0, page_count - 1), window - 1)


def _mineru_document_parse(path: Path, *, page_count: int) -> dict:
    if not _truthy_env(os.environ.get("LARGE_PDF_USE_MINERU"), default=True):
        return {
            "engine": "mineru",
            "status": "skipped",
            "markdown": "",
            "text": "",
            "question_spans": [],
            "public": {
                "engine": "mineru",
                "status": "skipped",
                "text_chars": 0,
                "markdown_chars": 0,
                "markdown_preview": "",
                "question_count": 0,
            },
        }

    try:
        start_page, end_page = _mineru_prepare_page_window(page_count)
        result = run_mineru_parse(
            path,
            output_dir=os.environ.get(
                "LARGE_PDF_MINERU_OUTPUT_DIR",
                str(DEFAULT_LARGE_PDF_MINERU_OUTPUT_DIR),
            ),
            method=os.environ.get("LARGE_PDF_MINERU_METHOD", DEFAULT_LARGE_PDF_MINERU_METHOD),
            timeout_seconds=_positive_int_env(
                "LARGE_PDF_MINERU_TIMEOUT_SECONDS",
                DEFAULT_LARGE_PDF_MINERU_TIMEOUT_SECONDS,
            ),
            start_page=start_page,
            end_page=end_page,
        )
        text = read_mineru_text(result).strip()
        markdown = _read_markdown_file(result) or text
        question_spans = _extract_question_spans(markdown or text)
        preview_source = markdown or text
        return {
            "engine": "mineru",
            "status": "ready",
            "markdown": markdown,
            "text": text,
            "question_spans": question_spans,
            "public": {
                "engine": "mineru",
                "status": "ready",
                "text_chars": len(text),
                "markdown_chars": len(markdown),
                "markdown_preview": preview_source[:MINERU_MARKDOWN_PREVIEW_CHARS],
                "question_count": len(question_spans),
            },
        }
    except MinerUNotAvailableError as exc:
        status = "unavailable"
        message = _safe_mineru_error(exc)
    except Exception as exc:
        status = "failed"
        message = _safe_mineru_error(exc)

    return {
        "engine": "mineru",
        "status": status,
        "markdown": "",
        "text": "",
        "question_spans": [],
        "public": {
            "engine": "mineru",
            "status": status,
            "text_chars": 0,
            "markdown_chars": 0,
            "markdown_preview": "",
            "question_count": 0,
            "message": message,
        },
    }


def _infer_paper_code(
    filename: str,
    first_page_text: str,
    mineru_text: str = "",
) -> tuple[str, str] | None:
    candidates = [
        (filename, "page_header"),
        (_cover_style_code(first_page_text) or "", "cover"),
        (first_page_text, "cover"),
    ]
    if mineru_text.strip():
        candidates.extend(
            [
                (_cover_style_code(mineru_text) or "", "mineru_markdown"),
                (mineru_text, "mineru_markdown"),
            ]
        )
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


def parse_selected_pages(
    raw: str,
    *,
    page_count: int,
    max_pages: int,
) -> list[int]:
    tokens = re.findall(r"\d+", raw or "")
    pages = list(dict.fromkeys(int(token) for token in tokens))
    if not pages:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "NO_PAGES_SELECTED", "message": "Select at least one PDF page."},
        )
    if len(pages) > max_pages:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "TOO_MANY_PAGES_SELECTED",
                "message": f"Max {max_pages} selected pages per analysis.",
            },
        )
    out_of_range = [page for page in pages if page < 1 or page > page_count]
    if out_of_range:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "INVALID_PAGE_SELECTION",
                "message": f"Selected pages must be between 1 and {page_count}.",
            },
        )
    return pages


def render_pdf_pages_to_temp_files(pdf_path: str | Path, selected_pages: list[int]) -> list[Path]:
    path = Path(pdf_path)
    _validate_pdf_path(path)
    tmps: list[Path] = []
    try:
        doc = fitz.open(path)
        try:
            for page_number in selected_pages:
                if page_number < 1 or page_number > doc.page_count:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error_code": "INVALID_PAGE_SELECTION",
                            "message": f"Selected pages must be between 1 and {doc.page_count}.",
                        },
                    )
                page = doc.load_page(page_number - 1)
                scale = min(2.5, max(1.0, 1600 / max(1, page.rect.width)))
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"-page-{page_number}.jpg")
                tmp.write(pix.tobytes("jpeg"))
                tmp.close()
                tmps.append(Path(tmp.name))
        finally:
            doc.close()
    except HTTPException:
        for tmp in tmps:
            tmp.unlink(missing_ok=True)
        raise
    except Exception as exc:
        for tmp in tmps:
            tmp.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail={"error_code": "PDF_RENDER_ERROR", "message": "Cannot render selected PDF pages."},
        ) from exc
    return tmps


def build_large_pdf_user_hint(
    user_hint: str,
    session: dict,
    selected_pages: list[int],
) -> str:
    parts = [user_hint.strip()] if user_hint.strip() else []
    parts.append(f"Large PDF selected pages: {', '.join(str(page) for page in selected_pages)}")

    document_parse = session.get("document_parse") or {}
    if document_parse.get("status") == "ready":
        parts.append("Document parser: MinerU Markdown is available for printed question context.")

    question_spans = session.get("question_spans") or []
    if question_spans:
        labels = [
            str(span.get("question_number"))
            for span in question_spans[:20]
            if span.get("question_number")
        ]
        if labels:
            parts.append(f"MinerU detected question numbers: {', '.join(labels)}")

    markdown = str(session.get("mineru_markdown") or session.get("mineru_text") or "").strip()
    if markdown:
        parts.append(
            "MinerU Markdown excerpt (use as printed question context; verify visual details "
            "against the uploaded page images):\n"
            f"{_clip_hint_text(markdown, MINERU_PIPELINE_HINT_CHARS)}"
        )
    if question_spans:
        snippets = []
        for span in question_spans[:MINERU_HINT_MAX_SPANS]:
            qnum = str(span.get("question_number") or "?").strip()
            snippet = _clip_hint_text(span.get("snippet") or "", MINERU_QUESTION_SNIPPET_CHARS)
            if snippet:
                snippets.append(f"Q{qnum}: {snippet}")
        if snippets:
            parts.append("MinerU question snippets:\n" + "\n".join(snippets))
    return "\n\n".join(parts)


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

    document_parse = _mineru_document_parse(path, page_count=page_count)
    mineru_markdown = document_parse.get("markdown", "")
    mineru_text = document_parse.get("text", "")
    question_spans = document_parse.get("question_spans", [])

    inferred = None
    effective_paper_code = paper_code
    if not effective_paper_code.strip() and preview_pages:
        inferred = _infer_paper_code(
            filename,
            preview_pages[0].get("ocr_hint", ""),
            mineru_markdown or mineru_text,
        )
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
        document_parse=document_parse["public"],
        question_spans=question_spans,
        mineru_markdown=mineru_markdown,
        mineru_text=mineru_text,
        delete_on_remove=delete_on_remove,
    )

    return {
        "status": "ready",
        "pdf_id": pdf_id,
        "filename": filename,
        "page_count": page_count,
        "preview_pages": preview_pages,
        "paper_resolution": public_resolution,
        "document_parse": document_parse["public"],
        "question_spans": question_spans,
    }
