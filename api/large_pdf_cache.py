"""Short-lived cache for Large PDF Mode sessions.

Local PDF paths stay inside this module's session entries. Public API responses
must pass through api.large_pdf helpers so paths are not exposed to users.
"""
from __future__ import annotations

from pathlib import Path
import threading
import time
import uuid

_TTL_SECONDS = 1800
_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()


def _remove_pdf_file(entry: dict | None) -> None:
    if not entry:
        return
    if not entry.get("delete_on_remove"):
        return
    pdf_path = entry.get("pdf_path")
    if not pdf_path:
        return
    try:
        Path(str(pdf_path)).unlink(missing_ok=True)
    except Exception:
        # Cache cleanup should never make request handling fail.
        pass


def _sweep_locked() -> None:
    now = time.monotonic()
    stale = [k for k, v in _CACHE.items() if now - v["ts"] > _TTL_SECONDS]
    for key in stale:
        entry = _CACHE.pop(key, None)
        _remove_pdf_file(entry)


def store(
    *,
    pdf_path: str,
    filename: str,
    page_count: int,
    preview_pages: list[dict],
    paper_resolution: dict,
    delete_on_remove: bool = False,
) -> str:
    pdf_id = uuid.uuid4().hex
    with _LOCK:
        _sweep_locked()
        _CACHE[pdf_id] = {
            "pdf_path": pdf_path,
            "filename": filename,
            "page_count": page_count,
            "preview_pages": preview_pages,
            "paper_resolution": paper_resolution,
            "delete_on_remove": delete_on_remove,
            "ts": time.monotonic(),
        }
    return pdf_id


def get(pdf_id: str) -> dict | None:
    with _LOCK:
        _sweep_locked()
        entry = _CACHE.get(pdf_id)
        return dict(entry) if entry else None


def pop(pdf_id: str) -> dict | None:
    with _LOCK:
        _sweep_locked()
        return _CACHE.pop(pdf_id, None)
