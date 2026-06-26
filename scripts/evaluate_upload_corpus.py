"""Batch-upload evaluation for the local test corpus.

Examples:
    python scripts/evaluate_upload_corpus.py --dry-run
    python scripts/evaluate_upload_corpus.py --api-base http://localhost:8000 --repeat 3
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.effectiveness import compute_upload_corpus_effectiveness


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
PDF_SUFFIXES = {".pdf"}
DEFAULT_REPORT_DIR = Path("reports/effectiveness")


@dataclass(frozen=True)
class UploadAsset:
    path: Path
    kind: str
    size_bytes: int


def discover_assets(input_dir: str | Path) -> list[UploadAsset]:
    root = Path(input_dir)
    assets: list[UploadAsset] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        suffix = path.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            assets.append(UploadAsset(path=path, kind="image", size_bytes=path.stat().st_size))
        elif suffix in PDF_SUFFIXES:
            assets.append(UploadAsset(path=path, kind="pdf", size_bytes=path.stat().st_size))
    return assets


def _load_expectations(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Expectation file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _now_report_path() -> Path:
    DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return DEFAULT_REPORT_DIR / f"upload_corpus_{stamp}.json"


def _event_records_from_sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        name = ""
        data_lines: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip("\r")
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if not name or not data_lines:
            continue
        try:
            payload = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            payload = {"raw": "\n".join(data_lines)}
        events.append((name, payload))
    return events


def _consume_sse_blocks(
    chunks: list[str],
    *,
    started: float,
    now=time.perf_counter,
    include_event_timings: bool = False,
) -> tuple[list[tuple[str, dict[str, Any]]], int | None] | tuple[list[tuple[str, dict[str, Any]]], int | None, dict[str, int]]:
    events: list[tuple[str, dict[str, Any]]] = []
    first_question_ms: int | None = None
    event_timings: dict[str, int] = {}
    buffer = ""

    def consume_block(block: str, observed_at: float) -> None:
        nonlocal first_question_ms
        if not block.strip():
            return
        observed_ms = int((observed_at - started) * 1000)
        parsed = _event_records_from_sse(block + "\n\n")
        for name, payload in parsed:
            events.append((name, payload))
            event_timings.setdefault("first_event_ms", observed_ms)
            if name == "segmentation":
                event_timings.setdefault("segmentation_ms", observed_ms)
            if name == "question" and first_question_ms is None:
                first_question_ms = observed_ms
                event_timings.setdefault("first_question_ms", observed_ms)
            if name == "summary":
                event_timings.setdefault("summary_ms", observed_ms)

    for chunk in chunks:
        if not chunk:
            continue
        observed_at = now()
        buffer += chunk
        while "\n\n" in buffer:
            block, buffer = buffer.split("\n\n", 1)
            consume_block(block, observed_at)
    if buffer.strip():
        consume_block(buffer, now())
    if include_event_timings:
        return events, first_question_ms, event_timings
    return events, first_question_ms


def _phase_timings_from_event_timings(event_timings: dict[str, int]) -> dict[str, int]:
    phase_timings: dict[str, int] = {}
    first_event_ms = event_timings.get("first_event_ms")
    segmentation_ms = event_timings.get("segmentation_ms")
    first_question_ms = event_timings.get("first_question_ms")
    summary_ms = event_timings.get("summary_ms")

    if first_event_ms is not None:
        phase_timings["sse_first_event_ms"] = first_event_ms
    if segmentation_ms is not None:
        phase_timings["segmentation_done_ms"] = segmentation_ms
    if first_question_ms is not None:
        phase_timings["first_question_ms"] = first_question_ms
    if segmentation_ms is not None and first_question_ms is not None:
        phase_timings["first_grading_after_segmentation_ms"] = max(0, first_question_ms - segmentation_ms)
    if first_question_ms is not None and summary_ms is not None:
        phase_timings["summary_after_first_question_ms"] = max(0, summary_ms - first_question_ms)
    return phase_timings


async def _post_sse(
    client: httpx.AsyncClient,
    url: str,
    *,
    files: Any,
    data: dict[str, str],
    started: float,
) -> tuple[list[tuple[str, dict[str, Any]]], int | None, dict[str, int]]:
    chunks: list[str] = []
    first_question_ms: int | None = None
    event_timings: dict[str, int] = {}
    buffer = ""
    events: list[tuple[str, dict[str, Any]]] = []

    def consume_block(block: str) -> None:
        nonlocal first_question_ms
        if not block.strip():
            return
        observed_ms = int((time.perf_counter() - started) * 1000)
        parsed = _event_records_from_sse(block + "\n\n")
        for name, payload in parsed:
            events.append((name, payload))
            event_timings.setdefault("first_event_ms", observed_ms)
            if name == "segmentation":
                event_timings.setdefault("segmentation_ms", observed_ms)
            if name == "question" and first_question_ms is None:
                first_question_ms = observed_ms
                event_timings.setdefault("first_question_ms", observed_ms)
            if name == "summary":
                event_timings.setdefault("summary_ms", observed_ms)

    kwargs: dict[str, Any] = {"data": data, "timeout": None}
    if files is not None:
        kwargs["files"] = files
    async with client.stream("POST", url, **kwargs) as response:
        response.raise_for_status()
        async for chunk in response.aiter_text():
            chunks.append(chunk)
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                consume_block(block)
    if buffer.strip():
        consume_block(buffer)
    if first_question_ms is None:
        _events, first_question_ms, fallback_timings = _consume_sse_blocks(
            chunks,
            started=started,
            include_event_timings=True,
        )
        if not events:
            events = _events
        event_timings = event_timings or fallback_timings
    return events, first_question_ms, _phase_timings_from_event_timings(event_timings)


def _normalise_question(payload: dict[str, Any]) -> dict[str, Any]:
    grade = payload.get("grade_result") or payload.get("grading") or {}
    if not isinstance(grade, dict):
        grade = {}
    return {
        "question_number": str(payload.get("question_number") or grade.get("question_number") or ""),
        "is_correct": bool(payload.get("is_correct") if "is_correct" in payload else grade.get("is_correct")),
        "score": payload.get("score", grade.get("score")),
        "full_score": payload.get("full_score", grade.get("full_score")),
        "unanswered": bool(payload.get("unanswered") or payload.get("is_unanswered") or grade.get("unanswered") or grade.get("is_unanswered")),
        "needs_review": bool(payload.get("needs_review") or grade.get("needs_review")),
        "error_type": payload.get("error_type", grade.get("error_type")),
        "knowledge_tags": payload.get("knowledge_tags", grade.get("knowledge_tags") or []),
    }


def _summary_from_events(events: list[tuple[str, dict[str, Any]]]) -> dict[str, Any] | None:
    for name, payload in reversed(events):
        if name == "summary" and isinstance(payload, dict):
            summary = payload.get("page_summary") or payload.get("summary") or payload
            if isinstance(summary, dict):
                return summary
    return None


def _questions_from_events(events: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for name, payload in events:
        if name == "question" and isinstance(payload, dict):
            questions.append(_normalise_question(payload))
    return questions


def _image_analyze_form_data() -> dict[str, str]:
    return {
        "feedback_mode": "both",
        "review_mode": "auto",
        "upload_intent": "unknown",
        "fast_batch": "true",
    }


def _question_error_counts(questions: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for question in questions:
        error_type = str(question.get("error_type") or "").strip().lower()
        if error_type:
            counts[error_type] = counts.get(error_type, 0) + 1
    return counts


def _practice_request_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    summary = result.get("summary")
    questions = result.get("questions")
    if not isinstance(summary, dict) or not isinstance(questions, list) or not questions:
        return None
    context = {
        "upload_intent": "full_past_paper_pdf" if result.get("kind") == "pdf" else "unknown",
        "paper_num": None,
        "question_number": None,
        "match_confidence": None,
        "confirmed_by_user": False,
        "grading_route": None,
    }
    return {
        "context": context,
        "priority_topics": summary.get("priority_topics") or [],
        "knowledge_tags_summary": summary.get("knowledge_tags_summary") or {},
        "questions": [
            {
                "question_number": q.get("question_number") or "",
                "score": q.get("score") or 0,
                "full_score": q.get("full_score") or 0,
                "is_correct": bool(q.get("is_correct")),
                "unanswered": bool(q.get("unanswered")),
                "error_type": q.get("error_type"),
                "knowledge_tags": q.get("knowledge_tags") or [],
                "needs_review": bool(q.get("needs_review")),
            }
            for q in questions
        ],
        "exclude_ids": [],
        "count": 3,
    }


def _compact_track_meta(result: dict[str, Any]) -> dict[str, Any]:
    questions = [
        {
            "question_number": q.get("question_number"),
            "is_correct": q.get("is_correct"),
            "score": q.get("score"),
            "full_score": q.get("full_score"),
            "unanswered": q.get("unanswered"),
            "needs_review": q.get("needs_review"),
            "error_type": q.get("error_type"),
            "knowledge_tags": (q.get("knowledge_tags") or [])[:5],
        }
        for q in result.get("questions", [])
        if isinstance(q, dict)
    ]
    recommendation = result.get("recommendation") if isinstance(result.get("recommendation"), dict) else {}
    meta = {
        "run_id": result.get("run_id"),
        "asset_path": result.get("asset_path"),
        "filename": result.get("filename"),
        "filenames": result.get("filenames"),
        "kind": result.get("kind"),
        "batch_size": result.get("batch_size"),
        "size_bytes": result.get("size_bytes"),
        "repeat_index": result.get("repeat_index"),
        "status": result.get("status"),
        "elapsed_ms": result.get("elapsed_ms"),
        "prepare_elapsed_ms": result.get("prepare_elapsed_ms"),
        "analyze_elapsed_ms": result.get("analyze_elapsed_ms"),
        "first_question_ms": result.get("first_question_ms"),
        "phase_timings": result.get("phase_timings"),
        "question_count": result.get("question_count"),
        "question_error_counts": result.get("question_error_counts"),
        "prepared": result.get("prepared"),
        "prepare_concurrency": result.get("prepare_concurrency"),
        "fast_batch": result.get("fast_batch"),
        "questions": questions,
        "recommendation": {
            "mode": recommendation.get("mode"),
            "recommendations": [
                {
                    "question_id": item.get("question_id"),
                    "topic": item.get("topic"),
                    "subtopic": item.get("subtopic"),
                    "paper_num": item.get("paper_num"),
                }
                for item in recommendation.get("recommendations", [])
                if isinstance(item, dict)
            ],
        },
    }
    meta = {key: value for key, value in meta.items() if value is not None}
    original_question_count = len(questions)
    while len(json.dumps(meta, ensure_ascii=False)) > 3900 and meta.get("questions"):
        meta["questions"] = meta["questions"][:-1]
        meta["questions_truncated"] = original_question_count - len(meta["questions"])
    if len(json.dumps(meta, ensure_ascii=False)) > 3900:
        meta["recommendation"] = {
            "mode": (result.get("recommendation") or {}).get("mode")
            if isinstance(result.get("recommendation"), dict)
            else None
        }
    if len(json.dumps(meta, ensure_ascii=False)) > 3900:
        meta.pop("asset_path", None)
        meta.pop("filenames", None)
        meta.pop("prepared", None)
    return meta


async def _track_result(client: httpx.AsyncClient, result: dict[str, Any]) -> None:
    try:
        duration = int(result.get("elapsed_ms") or 0)
        response = await client.post(
            "/feedback/track",
            json={
                "event_type": "ui_upload_corpus_asset_result",
                "duration_ms": max(0, min(duration, 3_600_000)),
                "meta": _compact_track_meta(result),
            },
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"[upload-corpus] track_event failed: {exc}", file=sys.stderr, flush=True)


async def _recommend(client: httpx.AsyncClient, result: dict[str, Any]) -> dict[str, Any]:
    body = _practice_request_from_result(result)
    if not body:
        return {"mode": "none", "recommendations": [], "message": "No summary/questions for recommendation."}
    try:
        response = await client.post("/practice-orchestrator/recommendations", json=body, timeout=60)
        response.raise_for_status()
        data = response.json()
        return {
            "mode": data.get("recommendation_mode"),
            "message": data.get("message"),
            "detected_topic": data.get("detected_topic"),
            "paper_num": data.get("paper_num"),
            "match_confidence": data.get("match_confidence"),
            "recommendations": [
                {
                    "question_id": item.get("question_id"),
                    "topic": item.get("topic"),
                    "subtopic": item.get("subtopic"),
                    "difficulty": item.get("difficulty"),
                    "paper_num": item.get("paper_num"),
                }
                for item in data.get("recommendations", [])
                if isinstance(item, dict)
            ],
        }
    except Exception as exc:
        return {"mode": "none", "recommendations": [], "message": f"Recommendation failed: {exc}"}


async def _run_image(client: httpx.AsyncClient, asset: UploadAsset, repeat_index: int, track: bool) -> dict[str, Any]:
    started = time.perf_counter()
    first_question_ms: int | None = None
    try:
        with asset.path.open("rb") as fh:
            files = {"image": (asset.path.name, fh, "application/octet-stream")}
            data = _image_analyze_form_data()
            events, first_question_ms, phase_timings = await _post_sse(
                client,
                "/analyze-homework-stream",
                files=files,
                data=data,
                started=started,
            )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        questions = _questions_from_events(events)
        result = {
            "asset_path": str(asset.path),
            "filename": asset.path.name,
            "kind": asset.kind,
            "size_bytes": asset.size_bytes,
            "repeat_index": repeat_index,
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "first_question_ms": first_question_ms,
            "phase_timings": phase_timings,
            "question_count": len(questions),
            "question_error_counts": _question_error_counts(questions),
            "questions": questions,
            "summary": _summary_from_events(events),
        }
        result["recommendation"] = await _recommend(client, result)
    except Exception as exc:
        result = {
            "asset_path": str(asset.path),
            "filename": asset.path.name,
            "kind": asset.kind,
            "size_bytes": asset.size_bytes,
            "repeat_index": repeat_index,
            "status": "error",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "first_question_ms": first_question_ms,
            "question_count": 0,
            "question_error_counts": {},
            "questions": [],
            "error": str(exc),
            "recommendation": {"mode": "none", "recommendations": []},
        }
    if track:
        await _track_result(client, result)
    return result


async def _run_image_batch(
    client: httpx.AsyncClient,
    assets: list[UploadAsset],
    repeat_index: int,
    track: bool,
    fast_batch: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    first_question_ms: int | None = None
    handles = []
    try:
        files = []
        for asset in assets:
            handle = asset.path.open("rb")
            handles.append(handle)
            files.append(("image", (asset.path.name, handle, "application/octet-stream")))
        data = {
            "feedback_mode": "both",
            "review_mode": "auto",
            "upload_intent": "unknown",
            "fast_batch": "true" if fast_batch else "false",
        }
        events, first_question_ms, phase_timings = await _post_sse(
            client,
            "/analyze-homework-stream",
            files=files,
            data=data,
            started=started,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        questions = _questions_from_events(events)
        result = {
            "asset_path": "batch:" + ",".join(str(asset.path) for asset in assets),
            "filename": f"batch_{len(assets)}_images",
            "filenames": [asset.path.name for asset in assets],
            "kind": "image_batch",
            "batch_size": len(assets),
            "size_bytes": sum(asset.size_bytes for asset in assets),
            "repeat_index": repeat_index,
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "first_question_ms": first_question_ms,
            "phase_timings": phase_timings,
            "question_count": len(questions),
            "question_error_counts": _question_error_counts(questions),
            "questions": questions,
            "summary": _summary_from_events(events),
        }
        result["recommendation"] = await _recommend(client, result)
    except Exception as exc:
        result = {
            "asset_path": "batch:" + ",".join(str(asset.path) for asset in assets),
            "filename": f"batch_{len(assets)}_images",
            "filenames": [asset.path.name for asset in assets],
            "kind": "image_batch",
            "batch_size": len(assets),
            "size_bytes": sum(asset.size_bytes for asset in assets),
            "repeat_index": repeat_index,
            "status": "error",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "first_question_ms": first_question_ms,
            "question_count": 0,
            "question_error_counts": {},
            "questions": [],
            "error": str(exc),
            "recommendation": {"mode": "none", "recommendations": []},
        }
    finally:
        for handle in handles:
            handle.close()
    if track:
        await _track_result(client, result)
    return result


async def _prepare_one_image(client: httpx.AsyncClient, asset: UploadAsset) -> dict[str, Any]:
    with asset.path.open("rb") as fh:
        response = await client.post(
            "/prepare-upload",
            files={"image": (asset.path.name, fh, "application/octet-stream")},
            data={"user_hint": ""},
            timeout=None,
        )
    response.raise_for_status()
    data = response.json()
    return {
        "filename": asset.path.name,
        "upload_id": data.get("upload_id"),
        "question_count": data.get("question_count"),
    }


async def _run_image_batch_prepared(
    client: httpx.AsyncClient,
    assets: list[UploadAsset],
    repeat_index: int,
    track: bool,
    prepare_concurrency: int,
    fast_batch: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    first_question_ms: int | None = None
    handles = []
    try:
        semaphore = asyncio.Semaphore(max(1, prepare_concurrency))

        async def prepare(asset: UploadAsset) -> dict[str, Any]:
            async with semaphore:
                return await _prepare_one_image(client, asset)

        prepare_started = time.perf_counter()
        prepared = await asyncio.gather(*(prepare(asset) for asset in assets))
        prepare_elapsed_ms = int((time.perf_counter() - prepare_started) * 1000)
        upload_ids = [str(item.get("upload_id") or "") for item in prepared]
        if any(not upload_id for upload_id in upload_ids):
            raise RuntimeError("prepare-upload returned an empty upload_id")

        files = []
        for asset in assets:
            handle = asset.path.open("rb")
            handles.append(handle)
            files.append(("image", (asset.path.name, handle, "application/octet-stream")))
        data = {
            "feedback_mode": "both",
            "review_mode": "auto",
            "upload_intent": "unknown",
            "upload_ids": ",".join(upload_ids),
            "fast_batch": "true" if fast_batch else "false",
        }
        analyze_started = time.perf_counter()
        events, first_question_ms, phase_timings = await _post_sse(
            client,
            "/analyze-homework-stream",
            files=files,
            data=data,
            started=analyze_started,
        )
        analyze_elapsed_ms = int((time.perf_counter() - analyze_started) * 1000)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        questions = _questions_from_events(events)
        result = {
            "asset_path": "prepared-batch:" + ",".join(str(asset.path) for asset in assets),
            "filename": f"prepared_batch_{len(assets)}_images",
            "filenames": [asset.path.name for asset in assets],
            "kind": "image_batch_prepared",
            "batch_size": len(assets),
            "size_bytes": sum(asset.size_bytes for asset in assets),
            "repeat_index": repeat_index,
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "prepare_elapsed_ms": prepare_elapsed_ms,
            "analyze_elapsed_ms": analyze_elapsed_ms,
            "first_question_ms": first_question_ms,
            "phase_timings": phase_timings,
            "question_count": len(questions),
            "question_error_counts": _question_error_counts(questions),
            "prepared": prepared,
            "prepare_concurrency": prepare_concurrency,
            "fast_batch": fast_batch,
            "questions": questions,
            "summary": _summary_from_events(events),
        }
        result["recommendation"] = await _recommend(client, result)
    except Exception as exc:
        result = {
            "asset_path": "prepared-batch:" + ",".join(str(asset.path) for asset in assets),
            "filename": f"prepared_batch_{len(assets)}_images",
            "filenames": [asset.path.name for asset in assets],
            "kind": "image_batch_prepared",
            "batch_size": len(assets),
            "size_bytes": sum(asset.size_bytes for asset in assets),
            "repeat_index": repeat_index,
            "status": "error",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "first_question_ms": first_question_ms,
            "question_count": 0,
            "question_error_counts": {},
            "questions": [],
            "error": str(exc),
            "prepare_concurrency": prepare_concurrency,
            "fast_batch": fast_batch,
            "recommendation": {"mode": "none", "recommendations": []},
        }
    finally:
        for handle in handles:
            handle.close()
    if track:
        await _track_result(client, result)
    return result


async def _run_pdf(client: httpx.AsyncClient, asset: UploadAsset, repeat_index: int, track: bool) -> dict[str, Any]:
    started = time.perf_counter()
    first_question_ms: int | None = None
    try:
        with asset.path.open("rb") as fh:
            prepare = await client.post(
                "/large-pdf/prepare",
                files={"pdf": (asset.path.name, fh, "application/pdf")},
                data={"upload_intent": "full_past_paper_pdf"},
                timeout=None,
            )
        prepare.raise_for_status()
        prepared = prepare.json()
        preview_pages = prepared.get("preview_pages") or []
        selected = [
            int(page["page"])
            for page in preview_pages
            if isinstance(page, dict) and page.get("selected_by_default")
        ]
        if not selected:
            selected = [
                int(page["page"])
                for page in preview_pages
                if isinstance(page, dict) and page.get("page")
            ]
        selected = selected[:24]
        if not selected:
            raise RuntimeError("Large PDF prepare returned no selectable pages")

        events, first_question_ms, phase_timings = await _post_sse(
            client,
            f"/large-pdf/{prepared['pdf_id']}/analyze-stream",
            files=None,
            data={
                "selected_pages": ",".join(str(page) for page in selected),
                "feedback_mode": "both",
                "review_mode": "auto",
                "upload_intent": "full_past_paper_pdf",
            },
            started=started,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        questions = _questions_from_events(events)
        result = {
            "asset_path": str(asset.path),
            "filename": asset.path.name,
            "kind": asset.kind,
            "size_bytes": asset.size_bytes,
            "repeat_index": repeat_index,
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "first_question_ms": first_question_ms,
            "phase_timings": phase_timings,
            "selected_pages": selected,
            "page_count": prepared.get("page_count"),
            "question_count": len(questions),
            "question_error_counts": _question_error_counts(questions),
            "questions": questions,
            "summary": _summary_from_events(events),
        }
        result["recommendation"] = await _recommend(client, result)
    except Exception as exc:
        result = {
            "asset_path": str(asset.path),
            "filename": asset.path.name,
            "kind": asset.kind,
            "size_bytes": asset.size_bytes,
            "repeat_index": repeat_index,
            "status": "error",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "first_question_ms": first_question_ms,
            "question_count": 0,
            "question_error_counts": {},
            "questions": [],
            "error": str(exc),
            "recommendation": {"mode": "none", "recommendations": []},
        }
    if track:
        await _track_result(client, result)
    return result


async def run_upload_corpus(
    assets: list[UploadAsset],
    *,
    api_base: str,
    repeat: int,
    max_concurrency: int,
    track: bool,
    run_id: str,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    records: list[dict[str, Any]] = []

    async with httpx.AsyncClient(base_url=api_base.rstrip("/"), timeout=None, trust_env=False) as client:
        async def run_one(asset: UploadAsset, repeat_index: int) -> dict[str, Any]:
            async with semaphore:
                print(f"[upload-corpus] start repeat={repeat_index}/{repeat} kind={asset.kind} file={asset.path}", flush=True)
                if asset.kind == "pdf":
                    result = await _run_pdf(client, asset, repeat_index, False)
                else:
                    result = await _run_image(client, asset, repeat_index, False)
                result["run_id"] = run_id
                if track:
                    await _track_result(client, result)
                print(
                    f"[upload-corpus] done status={result.get('status')} questions={result.get('question_count')} file={asset.path}",
                    flush=True,
                )
                return result

        tasks = [
            run_one(asset, repeat_index)
            for repeat_index in range(1, repeat + 1)
            for asset in assets
        ]
        for task in asyncio.as_completed(tasks):
            records.append(await task)
    return records


async def run_image_batch_corpus(
    assets: list[UploadAsset],
    *,
    api_base: str,
    repeat: int,
    batch_images: int,
    track: bool,
    run_id: str,
    use_prepare_upload: bool,
    prepare_concurrency: int,
    fast_batch: bool,
) -> list[dict[str, Any]]:
    image_assets = [asset for asset in assets if asset.kind == "image"][:batch_images]
    if len(image_assets) < batch_images:
        raise ValueError(f"Need {batch_images} images, found {len(image_assets)}")
    records: list[dict[str, Any]] = []
    async with httpx.AsyncClient(base_url=api_base.rstrip("/"), timeout=None, trust_env=False) as client:
        for repeat_index in range(1, repeat + 1):
            print(
                f"[upload-corpus] start repeat={repeat_index}/{repeat} kind=image_batch count={len(image_assets)} prepared={use_prepare_upload}",
                flush=True,
            )
            if use_prepare_upload:
                result = await _run_image_batch_prepared(
                    client,
                    image_assets,
                    repeat_index,
                    False,
                    prepare_concurrency,
                    fast_batch,
                )
            else:
                result = await _run_image_batch(client, image_assets, repeat_index, False, fast_batch)
            result["run_id"] = run_id
            if track:
                await _track_result(client, result)
            print(
                f"[upload-corpus] done status={result.get('status')} questions={result.get('question_count')} kind=image_batch count={len(image_assets)}",
                flush=True,
            )
            records.append(result)
    return records


def _asset_summary(assets: list[UploadAsset]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    for asset in assets:
        by_kind[asset.kind] = by_kind.get(asset.kind, 0) + 1
    return {
        "count": len(assets),
        "by_kind": by_kind,
        "assets": [
            {
                **asdict(asset),
                "path": str(asset.path),
            }
            for asset in assets
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate upload effectiveness using a local corpus.")
    parser.add_argument("--input-dir", default="test")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--expectations")
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--track-events", action="store_true")
    parser.add_argument("--batch-images", type=int, default=0, help="Upload the first N images as one multipart request.")
    parser.add_argument("--batch-only", action="store_true", help="Only run the image batch request.")
    parser.add_argument("--use-prepare-upload", action="store_true", help="Pre-extract batch images via /prepare-upload before analyze.")
    parser.add_argument("--prepare-concurrency", type=int, default=4)
    parser.add_argument("--fast-batch", action="store_true", help="Use API fast_batch mode for large image batches.")
    args = parser.parse_args()

    assets = discover_assets(args.input_dir)
    if args.dry_run:
        print(json.dumps({"status": "dry_run", **_asset_summary(assets)}, ensure_ascii=False, indent=2))
        return

    expectations = _load_expectations(args.expectations)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    if args.batch_only:
        if args.batch_images <= 0:
            raise ValueError("--batch-only requires --batch-images N")
        records = asyncio.run(
            run_image_batch_corpus(
                assets,
                api_base=args.api_base,
                repeat=max(1, args.repeat),
                batch_images=args.batch_images,
                track=args.track_events,
                run_id=run_id,
                use_prepare_upload=args.use_prepare_upload,
                prepare_concurrency=max(1, args.prepare_concurrency),
                fast_batch=args.fast_batch,
            )
        )
    else:
        records = asyncio.run(
        # One run id groups repeated passes over the same corpus so the
        # dashboard can show the latest benchmark without mixing setup runs.
            run_upload_corpus(
                assets,
                api_base=args.api_base,
                repeat=max(1, args.repeat),
                max_concurrency=max(1, args.max_concurrency),
                track=args.track_events,
                run_id=run_id,
            )
        )
        if args.batch_images > 0:
            records.extend(
                asyncio.run(
                    run_image_batch_corpus(
                        assets,
                        api_base=args.api_base,
                        repeat=max(1, args.repeat),
                        batch_images=args.batch_images,
                        track=args.track_events,
                        run_id=run_id,
                        use_prepare_upload=args.use_prepare_upload,
                        prepare_concurrency=max(1, args.prepare_concurrency),
                        fast_batch=args.fast_batch,
                    )
                )
            )
    report = {
        "status": "success",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "input_dir": args.input_dir,
        "settings": {
            "api_base": args.api_base,
            "repeat": max(1, args.repeat),
            "max_concurrency": max(1, args.max_concurrency),
            "tracked_events": bool(args.track_events),
        },
        "asset_summary": _asset_summary(assets),
        "effectiveness": compute_upload_corpus_effectiveness(records, expectations=expectations),
        "records": records,
    }
    output = Path(args.output) if args.output else _now_report_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output), "effectiveness": report["effectiveness"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
