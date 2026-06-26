from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.routes import FAST_BATCH_RECOGNITION_TIMEOUT_SECONDS, router
from api import upload_cache
from api.routes import _resolve_prepared


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (80, 60), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_fast_batch_stream_uses_recognition_timeout(monkeypatch) -> None:
    captured: dict = {}

    def fake_run_pipeline_streaming(image_paths, *_args, **kwargs):
        captured["image_paths"] = list(image_paths)
        captured["fast_batch"] = kwargs["fast_batch"]
        captured["recognition_timeout_seconds"] = kwargs["recognition_timeout_seconds"]
        yield ("segmentation", {"question_count": 0, "questions_preview": []})
        yield ("summary", {})
        yield ("done", {})

    monkeypatch.setattr("api.routes.run_pipeline_streaming", fake_run_pipeline_streaming)

    app = FastAPI()
    app.state.registry = {}
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/analyze-homework-stream",
        data={"fast_batch": "true"},
        files=[("image", ("page.png", _png_bytes(), "image/png"))],
    )

    assert response.status_code == 200
    assert "event: segmentation" in response.text
    assert captured["image_paths"]
    assert captured["fast_batch"] is True
    assert captured["recognition_timeout_seconds"] == FAST_BATCH_RECOGNITION_TIMEOUT_SECONDS


def test_fast_batch_recognition_timeout_default_is_quality_first() -> None:
    assert FAST_BATCH_RECOGNITION_TIMEOUT_SECONDS == 120


def test_resolve_prepared_falls_back_when_prepare_timed_out() -> None:
    upload_id = upload_cache.store(
        [
            {
                "question_number": "本次上传",
                "bbox": [0, 0, 80, 60],
                "question_text": "",
                "parent_stem": "",
                "student_answer": "",
                "working_steps": [],
                "marks": 0,
                "image_quality": "poor",
                "confidence": 0.0,
                "page": 1,
                "recognition_timeout": True,
            }
        ]
    )

    assert _resolve_prepared(upload_id) is None


def test_prepare_upload_reuses_identical_image_content(monkeypatch) -> None:
    upload_cache.clear()
    calls = {"count": 0}

    def fake_prepare_extract(_path: str, _user_hint: str, _registry) -> dict:
        calls["count"] += 1
        return {
            "extracted": [
                {
                    "question_number": "1",
                    "bbox": [0, 0, 80, 60],
                    "question_text": "Find x.",
                    "parent_stem": "",
                    "student_answer": "x=2",
                    "working_steps": ["x=2"],
                    "marks": 1,
                    "image_quality": "good",
                    "confidence": 0.95,
                    "page": 1,
                }
            ],
            "starts_with_qnum": True,
        }

    monkeypatch.setattr("api.routes._do_prepare_extract", fake_prepare_extract)

    app = FastAPI()
    app.state.registry = {}
    app.include_router(router)
    client = TestClient(app)

    first = client.post(
        "/prepare-upload",
        files={"image": ("same.png", _png_bytes(), "image/png")},
    )
    second = client.post(
        "/prepare-upload",
        files={"image": ("same-again.png", _png_bytes(), "image/png")},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["upload_id"] != second.json()["upload_id"]
    assert first.json()["question_count"] == 1
    assert second.json()["question_count"] == 1
    assert calls["count"] == 1
