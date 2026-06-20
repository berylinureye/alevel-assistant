"""上传预提取缓存：用户上传时预跑 segment_and_extract，/analyze 阶段复用结果。

简单内存实现：单进程，线程安全，TTL 30 分钟。多进程部署时需换 Redis。
"""
from __future__ import annotations

import threading
import time
import uuid

_TTL_SECONDS = 1800
_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()


def _sweep_locked() -> None:
    now = time.monotonic()
    stale = [k for k, v in _CACHE.items() if now - v["ts"] > _TTL_SECONDS]
    for k in stale:
        _CACHE.pop(k, None)


def store(
    extracted: list[dict],
    user_hint: str = "",
    starts_with_qnum: bool | None = None,
) -> str:
    upload_id = uuid.uuid4().hex
    with _LOCK:
        _sweep_locked()
        _CACHE[upload_id] = {
            "extracted": extracted,
            "user_hint": user_hint,
            # OCR-probed at /prepare-upload time: does this image's header start
            # with a numbered question marker? Consumed by _resolve_prepared
            # to tag non-leader images' items with _continuation_page so
            # _merge_cross_page_answers can fold their handwriting back.
            "starts_with_qnum": starts_with_qnum,
            "ts": time.monotonic(),
        }
    return upload_id


def get(upload_id: str) -> dict | None:
    with _LOCK:
        _sweep_locked()
        entry = _CACHE.get(upload_id)
        return dict(entry) if entry else None


def pop(upload_id: str) -> dict | None:
    with _LOCK:
        _sweep_locked()
        return _CACHE.pop(upload_id, None)
