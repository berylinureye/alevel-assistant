from __future__ import annotations

import base64
import sys
import time
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.models import (
    FallbackOCRClient,
    LocalOCRClient,
    MathpixOCRClient,
    ModelRequest,
    ModelRole,
    TaskType,
    build_registry,
)
from pipeline.segmenter import segment_and_extract


def _image_b64() -> str:
    buf = BytesIO()
    Image.new("RGB", (80, 60), "white").save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_local_ocr_client_decodes_image_and_returns_text(monkeypatch) -> None:
    client = LocalOCRClient(lang="eng", timeout=1)
    monkeypatch.setattr(client, "_image_to_string", lambda _image: "1. Find x\n")

    text = client.call(
        ModelRequest(
            task=TaskType.extract,
            prompt="OCR",
            images=[_image_b64()],
        )
    )

    assert text == "1. Find x"
    assert client.role is ModelRole.ocr
    assert client.provider == "local_tesseract"
    assert client.supports_images() is True


def test_mathpix_ocr_client_posts_data_uri_and_returns_text(monkeypatch) -> None:
    client = MathpixOCRClient(app_id="app-id", app_key="app-key", timeout=1)
    captured: dict = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"text": "$x=1$", "confidence": 0.99}

    def fake_post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("router.models.httpx.post", fake_post)

    text = client.call(
        ModelRequest(
            task=TaskType.extract,
            prompt="OCR",
            images=[_image_b64()],
        )
    )

    assert text == "$x=1$"
    assert captured["url"] == "https://api.mathpix.com/v3/text"
    assert captured["json"]["src"].startswith("data:image/jpeg;base64,")
    assert captured["json"]["math_inline_delimiters"] == ["$", "$"]
    assert captured["headers"]["app_id"] == "app-id"
    assert captured["headers"]["app_key"] == "app-key"
    assert captured["timeout"] == 1


def test_mathpix_ocr_client_falls_back_to_latex_styled(monkeypatch) -> None:
    client = MathpixOCRClient(app_id="app-id", app_key="app-key", timeout=1)

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"latex_styled": "x^2+1"}

    monkeypatch.setattr("router.models.httpx.post", lambda *args, **kwargs: Response())

    text = client.call(
        ModelRequest(
            task=TaskType.extract,
            prompt="OCR",
            images=[_image_b64()],
        )
    )

    assert text == "x^2+1"


def test_fallback_ocr_uses_secondary_client_when_primary_returns_empty() -> None:
    class EmptyOCR:
        role = ModelRole.ocr
        model_id = "empty"
        provider = "empty"

        def supports_images(self) -> bool:
            return True

        def call(self, _request):
            return ""

    class SecondaryOCR:
        role = ModelRole.ocr
        model_id = "secondary"
        provider = "secondary"

        def supports_images(self) -> bool:
            return True

        def call(self, _request):
            return "fallback text"

    client = FallbackOCRClient(EmptyOCR(), SecondaryOCR())

    text = client.call(
        ModelRequest(
            task=TaskType.extract,
            prompt="OCR",
            images=[_image_b64()],
        )
    )

    assert text == "fallback text"
    assert client.provider == "empty+secondary"


def test_local_ocr_client_timeout_returns_empty_without_blocking(monkeypatch) -> None:
    client = LocalOCRClient(lang="eng", timeout=0.01)

    def slow_ocr(_image):
        time.sleep(0.2)
        return "late"

    monkeypatch.setattr(client, "_image_to_string", slow_ocr)

    started = time.monotonic()
    text = client.call(
        ModelRequest(
            task=TaskType.extract,
            prompt="OCR",
            images=[_image_b64()],
        )
    )

    assert text == ""
    assert time.monotonic() - started < 0.25


def test_build_registry_uses_local_ocr_when_enabled_and_available(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.viviai.cc")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MATHPIX_APP_ID", raising=False)
    monkeypatch.delenv("MATHPIX_APP_KEY", raising=False)
    monkeypatch.delenv("OCR_MODEL", raising=False)
    monkeypatch.setenv("LOCAL_OCR_ENABLED", "1")
    monkeypatch.setenv("LOCAL_OCR_LANG", "eng")
    monkeypatch.setenv("LOCAL_OCR_TIMEOUT_SECONDS", "3")
    monkeypatch.setattr(LocalOCRClient, "is_available", classmethod(lambda cls: True))

    registry = build_registry()

    assert isinstance(registry[ModelRole.ocr], LocalOCRClient)
    assert registry[ModelRole.ocr].model_id == "tesseract:eng"


def test_build_registry_prefers_mathpix_and_keeps_local_fallback(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.viviai.cc")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("MATHPIX_APP_ID", "mathpix-id")
    monkeypatch.setenv("MATHPIX_APP_KEY", "mathpix-key")
    monkeypatch.setenv("LOCAL_OCR_ENABLED", "1")
    monkeypatch.setattr(LocalOCRClient, "is_available", classmethod(lambda cls: True))

    registry = build_registry()

    ocr = registry[ModelRole.ocr]
    assert isinstance(ocr, FallbackOCRClient)
    assert isinstance(ocr.primary, MathpixOCRClient)
    assert isinstance(ocr.fallback, LocalOCRClient)
    assert ocr.primary.app_id == "mathpix-id"


def test_build_registry_uses_default_viviai_ocr_model_when_set(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.viviai.cc")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MATHPIX_APP_ID", raising=False)
    monkeypatch.delenv("MATHPIX_APP_KEY", raising=False)
    monkeypatch.setenv("OCR_MODEL", "gemini-3-flash-preview")
    monkeypatch.setenv("LOCAL_OCR_ENABLED", "0")

    registry = build_registry()

    assert registry[ModelRole.ocr].provider == "viviai"
    assert registry[ModelRole.ocr].model_id == "gemini-3-flash-preview"


def test_build_registry_skips_unavailable_local_ocr(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.viviai.cc")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MATHPIX_APP_ID", raising=False)
    monkeypatch.delenv("MATHPIX_APP_KEY", raising=False)
    monkeypatch.delenv("OCR_MODEL", raising=False)
    monkeypatch.setenv("LOCAL_OCR_ENABLED", "1")
    monkeypatch.setattr(LocalOCRClient, "is_available", classmethod(lambda cls: False))

    registry = build_registry()

    assert ModelRole.ocr not in registry


def test_local_ocr_is_not_used_for_full_page_segment_rewrite(monkeypatch) -> None:
    class VisionClient:
        role = ModelRole.vision
        model_id = "vision"
        provider = "test"

        def supports_images(self) -> bool:
            return True

        def call(self, _request):
            return """
            [{
              "question_number": "1",
              "question_text": "Find x.",
              "student_answer": "x = 2",
              "working_steps": [],
              "marks": 1,
              "image_quality": "good",
              "confidence": 0.9,
              "page": 1
            }]
            """

    class LocalProbeOnlyOCR:
        role = ModelRole.ocr
        model_id = "tesseract:eng"
        provider = "local_tesseract"
        calls = 0

        def supports_images(self) -> bool:
            return True

        def call(self, _request):
            self.calls += 1
            return "1. Find x."

    ocr = LocalProbeOnlyOCR()
    image = Image.new("RGB", (80, 60), "white")

    result = segment_and_extract(image, VisionClient(), ocr_client=ocr)

    assert result[0]["question_number"] == "1"
    assert ocr.calls == 0


def test_non_local_ocr_text_is_supplied_as_segment_prompt_reference(monkeypatch) -> None:
    monkeypatch.setenv("SEGMENT_OCR_HINT_ENABLED", "1")
    monkeypatch.setenv("SEGMENT_OCR_HINT_TIMEOUT_SECONDS", "1")

    class VisionClient:
        role = ModelRole.vision
        model_id = "vision"
        provider = "test"
        prompt = ""

        def supports_images(self) -> bool:
            return True

        def call(self, request):
            self.prompt = request.prompt
            return """
            [{
              "question_number": "1",
              "question_text": "Find x.",
              "student_answer": "x = 2",
              "working_steps": [],
              "marks": 1,
              "image_quality": "good",
              "confidence": 0.9,
              "page": 1
            }]
            """

    class MathpixLikeOCR:
        role = ModelRole.ocr
        model_id = "mathpix:v3/text"
        provider = "mathpix"

        def supports_images(self) -> bool:
            return True

        def call(self, _request):
            return "Find x when the printed equation is x + 1 = 3"

    vision = VisionClient()
    image = Image.new("RGB", (80, 60), "white")

    segment_and_extract(image, vision, ocr_client=MathpixLikeOCR())

    assert "Find x when the printed equation is x + 1 = 3" in vision.prompt


def test_handwriting_only_ocr_text_is_not_supplied_as_segment_prompt_reference(monkeypatch) -> None:
    monkeypatch.setenv("SEGMENT_OCR_HINT_ENABLED", "1")
    monkeypatch.setenv("SEGMENT_OCR_HINT_TIMEOUT_SECONDS", "1")

    class VisionClient:
        role = ModelRole.vision
        model_id = "vision"
        provider = "test"
        prompt = ""

        def supports_images(self) -> bool:
            return True

        def call(self, request):
            self.prompt = request.prompt
            return """
            [{
              "question_number": "1",
              "question_text": "",
              "student_answer": "x = 2",
              "working_steps": ["x + 1 = 3", "x = 2"],
              "marks": 1,
              "image_quality": "good",
              "confidence": 0.9,
              "page": 1
            }]
            """

    class MathpixLikeOCR:
        role = ModelRole.ocr
        model_id = "mathpix:v3/text"
        provider = "mathpix"

        def supports_images(self) -> bool:
            return True

        def call(self, _request):
            return "x + 1 = 3\nx = 2"

    vision = VisionClient()
    image = Image.new("RGB", (80, 60), "white")

    segment_and_extract(image, vision, ocr_client=MathpixLikeOCR())

    assert "x + 1 = 3\nx = 2" not in vision.prompt
