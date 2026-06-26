"""上传预提取缓存：用户上传时预跑 segment_and_extract，/analyze 阶段复用结果。

简单内存实现：单进程，线程安全，TTL 30 分钟。多进程部署时需换 Redis。
"""
from __future__ import annotations

import copy
import threading
import time
import uuid

_TTL_SECONDS = 1800
_CACHE: dict[str, dict] = {}
_CONTENT_CACHE: dict[str, dict] = {}
_INFLIGHT_CONTENT: dict[str, threading.Event] = {}
_LOCK = threading.Lock()


def _sweep_locked() -> None:
    now = time.monotonic()
    stale = [k for k, v in _CACHE.items() if now - v["ts"] > _TTL_SECONDS]
    for k in stale:
        _CACHE.pop(k, None)
    stale_content = [k for k, v in _CONTENT_CACHE.items() if now - v["ts"] > _TTL_SECONDS]
    for k in stale_content:
        _CONTENT_CACHE.pop(k, None)


def _content_key(content_hash: str, user_hint: str) -> str:
    return f"{content_hash}:{user_hint.strip()}"


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


def get_prepared_template(content_hash: str, user_hint: str = "") -> dict | None:
    with _LOCK:
        _sweep_locked()
        entry = _CONTENT_CACHE.get(_content_key(content_hash, user_hint))
        if not entry:
            return None
        return {
            "extracted": copy.deepcopy(entry["extracted"]),
            "starts_with_qnum": entry.get("starts_with_qnum"),
        }


def claim_prepared_template(content_hash: str, user_hint: str = "") -> tuple[str, threading.Event | dict | None]:
    key = _content_key(content_hash, user_hint)
    with _LOCK:
        _sweep_locked()
        entry = _CONTENT_CACHE.get(key)
        if entry:
            return (
                "hit",
                {
                    "extracted": copy.deepcopy(entry["extracted"]),
                    "starts_with_qnum": entry.get("starts_with_qnum"),
                },
            )
        event = _INFLIGHT_CONTENT.get(key)
        if event is not None:
            return ("wait", event)
        event = threading.Event()
        _INFLIGHT_CONTENT[key] = event
        return ("owner", event)


def release_prepared_template_claim(content_hash: str, user_hint: str = "") -> None:
    key = _content_key(content_hash, user_hint)
    with _LOCK:
        event = _INFLIGHT_CONTENT.pop(key, None)
        if event is not None:
            event.set()


def store_prepared_template(
    content_hash: str,
    extracted: list[dict],
    user_hint: str = "",
    starts_with_qnum: bool | None = None,
) -> None:
    with _LOCK:
        _sweep_locked()
        _CONTENT_CACHE[_content_key(content_hash, user_hint)] = {
            "extracted": copy.deepcopy(extracted),
            "starts_with_qnum": starts_with_qnum,
            "ts": time.monotonic(),
        }


def get(upload_id: str) -> dict | None:
    with _LOCK:
        _sweep_locked()
        entry = _CACHE.get(upload_id)
        return dict(entry) if entry else None


def pop(upload_id: str) -> dict | None:
    with _LOCK:
        _sweep_locked()
        return _CACHE.pop(upload_id, None)


def clear() -> None:
    with _LOCK:
        _CACHE.clear()
        _CONTENT_CACHE.clear()
        for event in _INFLIGHT_CONTENT.values():
            event.set()
        _INFLIGHT_CONTENT.clear()
