"""
Shared JSON repair utilities for parsing LLM output that contains LaTeX.

LLM models often produce JSON with unescaped LaTeX backslashes (e.g. \frac, \sqrt, \bar)
which break json.loads(). This module provides robust repair functions used by the grader,
segmenter, and feedback modules.
"""
from __future__ import annotations

import json
import re


def strip_code_fence(text: str) -> str:
    """Remove Markdown code fences (```json ... ```) from text."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text


def extract_json_object(text: str) -> str | None:
    """Extract the first JSON object ({...}) from surrounding text."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1].strip()


def extract_json_array(text: str) -> str | None:
    """Extract the first JSON array ([...]) from surrounding text."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1].strip()


def fix_json_backslashes(text: str) -> str:
    r"""Fix unescaped backslashes in LLM JSON output (typically LaTeX commands).

    Handles three categories:
    1. \command (2+ alpha chars): \frac, \sqrt, \bar, \sum, \cdot, \times, etc.
    2. LaTeX spacing/symbols: \, \; \! \: \> \< \_ \# \% \& \^
    3. LaTeX braces: \{ \}

    The negative lookbehind (?<!\\) prevents double-escaping already-escaped sequences.
    """
    # 1. LaTeX commands: \frac, \sqrt, \bar, \sum, \cdot, \times, \text, etc.
    text = re.sub(r'(?<!\\)\\([a-zA-Z]{2,})', r'\\\\\1', text)
    # 2. LaTeX spacing/special chars: \, \; \! \: \> \< \_ \# \% \& \^
    text = re.sub(r'(?<!\\)\\([,;!:><_#%&^])', r'\\\\\1', text)
    # 3. LaTeX literal braces: \{ \}
    text = re.sub(r'(?<!\\)\\([{}])', r'\\\\\1', text)
    return text


def cleanup_common_json_issues(text: str) -> str:
    """Apply all common JSON fixes: LaTeX escaping, trailing commas, smart quotes."""
    text = fix_json_backslashes(text)
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Fix smart quotes
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2019", "'")
    return text


def parse_json_object(text: str) -> dict:
    """Parse LLM output as a JSON object with multiple repair strategies.

    1. Try raw parse (fastest path).
    2. Try after stripping code fences + extracting {...}.
    3. Try after applying LaTeX/backslash fixes.
    4. Last resort: regex extraction of key fields.

    Raises ValueError if all strategies fail.
    """
    raw = strip_code_fence(text)

    candidates: list[str] = [raw]
    extracted = extract_json_object(raw)
    if extracted and extracted != raw:
        candidates.insert(0, extracted)

    last_err: Exception | None = None
    for cand in candidates:
        # Try raw first
        try:
            result = json.loads(cand)
            if isinstance(result, dict):
                return result
        except Exception:
            pass
        # Try with backslash/cleanup fixes
        cleaned = cleanup_common_json_issues(cand)
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except Exception as e:
            last_err = e
            continue

    # Last resort: regex extraction of individual fields
    fallback = _extract_fields_by_regex(text)
    if fallback:
        return fallback

    raise ValueError(f"Model output is not valid JSON: {last_err}") from last_err


def parse_json_array(text: str) -> list[dict]:
    """Parse LLM output as a JSON array with multiple repair strategies."""
    raw = strip_code_fence(text)

    candidates: list[str] = [raw]
    extracted = extract_json_array(raw)
    if extracted and extracted != raw:
        candidates.insert(0, extracted)

    last_err: Exception | None = None
    for cand in candidates:
        try:
            result = json.loads(cand)
            if isinstance(result, list):
                return result
        except Exception:
            pass
        cleaned = cleanup_common_json_issues(cand)
        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
        except Exception as e:
            last_err = e
            continue

    raise ValueError(f"Model output is not valid JSON array: {last_err}") from last_err


def _extract_fields_by_regex(text: str) -> dict | None:
    """Last-resort regex extraction when JSON parsing completely fails.

    Extracts the most critical grading fields individually.
    Returns None if not enough fields can be extracted.
    """
    fields: dict = {}

    # Boolean fields
    for key in ("is_correct", "needs_review"):
        m = re.search(rf'"{key}"\s*:\s*(true|false)', text, re.IGNORECASE)
        if m:
            fields[key] = m.group(1).lower() == "true"

    # Numeric fields
    for key in ("score", "full_score", "grading_confidence"):
        m = re.search(rf'"{key}"\s*:\s*([\d.]+)', text)
        if m:
            try:
                fields[key] = float(m.group(1))
            except ValueError:
                pass

    # String fields (capture content between quotes, handling escaped quotes)
    for key in ("error_type", "short_feedback"):
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            fields[key] = m.group(1)

    # Must have at least score or is_correct to be useful
    if "score" in fields or "is_correct" in fields:
        return fields
    return None
