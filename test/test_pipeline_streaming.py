from __future__ import annotations

import time

from PIL import Image

from pipeline import pipeline as pipeline_module
from pipeline.pipeline import run_pipeline_streaming
from router.models import ModelRole


class _FakeClient:
    role = ModelRole.base
    model_id = "fake"
    provider = "test"

    def supports_images(self) -> bool:
        return True

    def call(self, request):
        return "[]"


def _fake_registry() -> dict:
    client = _FakeClient()
    return {
        ModelRole.base: client,
        ModelRole.review: client,
        ModelRole.vision: client,
    }


def _disable_grading_agents(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_module, "build_grading_agents", lambda: None)
    monkeypatch.setattr(pipeline_module, "_build_solution_client", lambda *_args: None)
    monkeypatch.setattr(pipeline_module, "_build_aggregator_client", lambda *_args: None)


def test_streaming_question_extracted_event_clips_long_question_text(monkeypatch) -> None:
    _disable_grading_agents(monkeypatch)
    long_question_text = "Find x. " + ("very long printed context " * 80)

    events = run_pipeline_streaming(
        "unused.jpg",
        grade=False,
        registry=_fake_registry(),
        prepared_extracted=[
            {
                "question_number": "1",
                "bbox": [0, 0, 10, 10],
                "question_text": long_question_text,
                "parent_stem": "",
                "student_answer": "",
                "working_steps": [],
                "marks": 2,
                "page": 1,
                "image_quality": "good",
                "confidence": 0.9,
            }
        ],
    )

    assert next(events)[0] == "segmentation"
    event_type, payload = next(events)

    assert event_type == "question_extracted"
    assert len(payload["question_text"]) <= 523
    assert payload["question_text"].endswith("...")


def test_streaming_segmentation_timeout_yields_fallback_quickly(
    tmp_path,
    monkeypatch,
) -> None:
    _disable_grading_agents(monkeypatch)
    image_path = tmp_path / "page.jpg"
    Image.new("RGB", (80, 60), "white").save(image_path)

    def slow_segment(*_args, **_kwargs):
        time.sleep(0.2)
        return [
            {
                "question_number": "late",
                "bbox": [0, 0, 80, 60],
                "question_text": "Late result",
                "student_answer": "",
                "working_steps": [],
                "image_quality": "good",
                "confidence": 0.9,
            }
        ]

    monkeypatch.setattr(pipeline_module, "_segment_with_grouping", slow_segment)

    started = time.monotonic()
    events = run_pipeline_streaming(
        str(image_path),
        grade=False,
        registry=_fake_registry(),
        recognition_timeout_seconds=0.01,
    )
    event_type, payload = next(events)
    elapsed = time.monotonic() - started

    assert event_type == "segmentation"
    assert elapsed < 0.15
    assert payload["recognition_timed_out"] is True
    assert payload["question_count"] == 1
