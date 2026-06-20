from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

MatchConfidence = Literal["high", "medium", "low"]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_CONTEXT_CHARS = 3200


@dataclass(frozen=True)
class PaperAssetPaths:
    qp_path: Path | None
    ms_path: Path | None
    available: bool
    reason: str


@dataclass(frozen=True)
class QuestionMarkSchemeContext:
    question_number: str
    text: str
    confidence: MatchConfidence
    reason: str


def _resolve_repo_path(value: str | None, *, root: Path = ROOT) -> Path | None:
    raw = (value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    return path


def resolve_paper_asset_paths(catalog_match: dict | None, *, root: Path = ROOT) -> PaperAssetPaths:
    if not catalog_match:
        return PaperAssetPaths(
            qp_path=None,
            ms_path=None,
            available=False,
            reason="No catalog match is available.",
        )

    qp_path = _resolve_repo_path(catalog_match.get("qp_path"), root=root)
    ms_path = _resolve_repo_path(catalog_match.get("ms_path"), root=root)

    if not catalog_match.get("has_qp"):
        return PaperAssetPaths(
            qp_path=qp_path,
            ms_path=ms_path,
            available=False,
            reason="The catalog row does not advertise a question paper.",
        )
    if qp_path is None:
        return PaperAssetPaths(
            qp_path=None,
            ms_path=ms_path,
            available=False,
            reason="The catalog row has no question paper path.",
        )
    if not qp_path.exists():
        return PaperAssetPaths(
            qp_path=qp_path,
            ms_path=ms_path,
            available=False,
            reason="Question paper file is missing from local storage.",
        )
    if not catalog_match.get("has_ms"):
        return PaperAssetPaths(
            qp_path=qp_path,
            ms_path=ms_path,
            available=False,
            reason="The catalog row does not advertise a mark scheme.",
        )
    if ms_path is None:
        return PaperAssetPaths(
            qp_path=qp_path,
            ms_path=None,
            available=False,
            reason="The catalog row has no mark scheme path.",
        )
    if not ms_path.exists():
        return PaperAssetPaths(
            qp_path=qp_path,
            ms_path=ms_path,
            available=False,
            reason="Mark scheme file is missing from local storage.",
        )

    return PaperAssetPaths(
        qp_path=qp_path,
        ms_path=ms_path,
        available=True,
        reason="Question paper and mark scheme assets are available.",
    )


@lru_cache(maxsize=128)
def extract_pdf_text(path: Path) -> str:
    """Extract text from a local PDF using the project's PyMuPDF dependency."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(path) as doc:
            return "\n".join(page.get_text("text") for page in doc)
    except Exception:
        # PyPDF2 is available in some local environments; use it as a best-effort
        # fallback without adding a new runtime dependency.
        try:
            import PyPDF2

            with path.open("rb") as f:
                reader = PyPDF2.PdfReader(f)
                return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            return ""


def _words_to_text(words: list[tuple]) -> str:
    lines: dict[tuple[int, int], list[tuple[float, str]]] = {}
    for word in words:
        try:
            x0, _y0, _x1, _y1, text, block_no, line_no, _word_no = word
        except ValueError:
            continue
        lines.setdefault((int(block_no), int(line_no)), []).append((float(x0), str(text)))

    rendered: list[str] = []
    for key in sorted(lines):
        pieces = [text for _x, text in sorted(lines[key], key=lambda item: item[0])]
        rendered.append(" ".join(pieces))
    return "\n".join(rendered).strip()


@lru_cache(maxsize=128)
def extract_pdf_question_blocks(path: Path) -> dict[str, str]:
    """Return question-number keyed blocks using left-margin headings when available."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(path) as doc:
            page_words: list[list[tuple]] = [page.get_text("words") for page in doc]
    except Exception:
        return {}

    anchors: list[tuple[int, int, float, str]] = []
    for page_index, words in enumerate(page_words):
        for word in words:
            try:
                x0, y0, _x1, _y1, text, *_rest = word
            except ValueError:
                continue
            clean = str(text).strip()
            if not re.fullmatch(r"\d{1,2}", clean):
                continue
            # Cambridge mark schemes put top-level question numbers in a left
            # margin column. Formula numbers sit further to the right.
            if float(x0) <= 90:
                anchors.append((page_index, int(clean), float(y0), clean))

    anchors.sort(key=lambda item: (item[0], item[2], item[1]))
    blocks: dict[str, str] = {}
    for idx, (start_page, _qint, start_y, qkey) in enumerate(anchors):
        end_page = anchors[idx + 1][0] if idx + 1 < len(anchors) else len(page_words) - 1
        end_y = anchors[idx + 1][2] if idx + 1 < len(anchors) else float("inf")
        page_chunks: list[str] = []
        for page_index in range(start_page, end_page + 1):
            selected: list[tuple] = []
            for word in page_words[page_index]:
                try:
                    _x0, y0, _x1, _y1, *_rest = word
                except ValueError:
                    continue
                y = float(y0)
                if page_index == start_page and y < start_y - 2:
                    continue
                if page_index == end_page and y >= end_y - 2:
                    continue
                selected.append(word)
            chunk = _words_to_text(selected)
            if chunk:
                page_chunks.append(chunk)
        block = "\n".join(page_chunks).strip()
        if block:
            blocks[qkey] = block
    return blocks


def _question_key(value: str | int | None) -> str | None:
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else None


def _line_is_question_heading(line: str, question_number: str) -> bool:
    return re.fullmatch(rf"\s*{re.escape(question_number)}\s*", line) is not None


def _line_is_next_question_heading(line: str, current_question: str) -> bool:
    match = re.fullmatch(r"\s*(\d{1,2})\s*", line)
    if not match:
        return False
    return int(match.group(1)) > int(current_question)


def _extract_question_block(text: str, question_number: str) -> str:
    lines = text.splitlines()
    start: int | None = None
    end = len(lines)

    for idx, line in enumerate(lines):
        if _line_is_question_heading(line, question_number):
            start = idx
            break

    if start is None:
        return ""

    for idx in range(start + 1, len(lines)):
        if _line_is_next_question_heading(lines[idx], question_number):
            end = idx
            break

    block = "\n".join(lines[start:end])
    block = re.sub(r"\n{3,}", "\n\n", block).strip()
    return block


def _looks_like_mark_scheme_block(block: str) -> bool:
    if len(block) < 40:
        return False
    mark_tokens = re.findall(r"\b(?:M|A|B|DM|DB)\d\b|\[\d+\]", block)
    return len(mark_tokens) >= 2


def extract_question_mark_scheme_context(
    ms_path: Path,
    question_number: str,
    *,
    paper_label: str | None = None,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> QuestionMarkSchemeContext:
    qkey = _question_key(question_number) or str(question_number)
    block = extract_pdf_question_blocks(ms_path).get(qkey, "")
    text = ""
    if not block:
        text = extract_pdf_text(ms_path)
    if not block and not text.strip():
        return QuestionMarkSchemeContext(
            question_number=qkey,
            text="",
            confidence="low",
            reason="Could not extract text from the mark scheme PDF.",
        )

    if not block:
        block = _extract_question_block(text, qkey)
    if not block:
        return QuestionMarkSchemeContext(
            question_number=qkey,
            text="",
            confidence="low",
            reason=f"Could not locate question {qkey} in the mark scheme text.",
        )

    confidence: MatchConfidence = "high" if _looks_like_mark_scheme_block(block) else "medium"
    clipped = block[:max_chars].rstrip()
    if len(block) > max_chars:
        clipped += "\n[Context clipped for prompt length.]"

    label = paper_label or "matched past paper"
    context_text = (
        f"Official mark scheme context for {label}, question {qkey}:\n"
        f"{clipped}"
    )
    return QuestionMarkSchemeContext(
        question_number=qkey,
        text=context_text,
        confidence=confidence,
        reason="Extracted question-level mark scheme context.",
    )


def build_mark_scheme_context_map(
    *,
    catalog_match: dict | None,
    question_numbers: list[str],
    paper_label: str | None = None,
    root: Path = ROOT,
) -> dict[str, QuestionMarkSchemeContext]:
    assets = resolve_paper_asset_paths(catalog_match, root=root)
    if not assets.available or assets.ms_path is None:
        return {}

    contexts: dict[str, QuestionMarkSchemeContext] = {}
    for raw_qnum in question_numbers:
        qkey = _question_key(raw_qnum)
        if not qkey or qkey in contexts:
            continue
        contexts[qkey] = extract_question_mark_scheme_context(
            assets.ms_path,
            qkey,
            paper_label=paper_label,
        )
    return contexts
