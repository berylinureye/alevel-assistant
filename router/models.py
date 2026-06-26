"""
ModelClient 抽象层 + AnthropicCompatClient 实现 + ModelRegistry 工厂

设计原则：
- ModelClient Protocol 只暴露 call() 和 supports_images()，不绑定厂商
- AnthropicCompatClient 描述协议（Anthropic API 格式），不描述厂商
- build_registry() 从环境变量构造 registry，pipeline 只依赖 registry
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from urllib.parse import urlparse
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

import anthropic
import httpx
import openai
from PIL import Image


_log = logging.getLogger("router.models")


def _as_openai_base_url(base_url: str) -> str:
    """Normalize an OpenAI-compatible gateway base URL to include /v1."""
    clean = base_url.rstrip("/")
    return clean if clean.endswith("/v1") else f"{clean}/v1"


def _looks_like_viviai(base_url: str) -> bool:
    host = urlparse(base_url).netloc.lower()
    return "viviai.cc" in host


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

class ModelRole(str, Enum):
    base    = "base"     # 常规批改（纯文本，快速）
    vision  = "vision"   # 图片识别 + 切题（需要视觉能力）
    ocr     = "ocr"      # 纯文字 OCR（专用模型，与 vision 并行交叉校验）
    review  = "review"   # 复杂题复核 + 详细解析
    explain = "explain"  # 解题思路 + 追问对话（需要强推理能力）


class TaskType(str, Enum):
    segment  = "segment"   # 整页图 → bbox 列表
    extract  = "extract"   # 单题图 → QuestionData 字段
    classify = "classify"  # 题目文字 → QuestionType
    grade    = "grade"     # QuestionData → GradeResult（base 简洁版）
    review   = "review"    # QuestionData → GradeResult（review 详细版）


# ---------------------------------------------------------------------------
# 请求体
# ---------------------------------------------------------------------------

@dataclass
class ModelRequest:
    task:        TaskType
    prompt:      str
    images:      list[str] = field(default_factory=list)  # base64 字符串列表
    max_tokens:  int = 1024
    temperature: float = 0.0  # 批改/分类用 0.0（确定性），feedback 可用 0.3
    max_retries: int = 2


# ---------------------------------------------------------------------------
# ModelClient Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ModelClient(Protocol):
    role:     ModelRole
    model_id: str
    provider: str   # 用于日志 / 计费追踪，如 "vivia_proxy"、"openai"

    def supports_images(self) -> bool:
        """声明该 client 是否支持图片输入"""
        ...

    def call(self, request: ModelRequest) -> str:
        """
        发请求，返回原始文本。
        解析责任在调用方（segmenter / extractor / grader），接口不解析 JSON。
        """
        ...


# ---------------------------------------------------------------------------
# AnthropicCompatClient：使用 Anthropic API 协议的客户端
# （当前用于 api.viviai.cc 多模型代理，也可指向 api.anthropic.com）
# ---------------------------------------------------------------------------

class AnthropicCompatClient:
    def __init__(
        self,
        base_url: str,
        model_id: str,
        provider: str,
        role: ModelRole,
        api_key: str,
        timeout: int = 120,
    ) -> None:
        self.role     = role
        self.model_id = model_id
        self.provider = provider
        self.timeout  = timeout
        self._client  = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=float(timeout),
        )

    def supports_images(self) -> bool:
        return True  # vivia_proxy 下所有模型均支持图片

    def call(self, request: ModelRequest, _attempt: int = 0) -> str:
        """
        发请求并返回文本。
        若模型返回空字符串（vivia proxy 偶发行为），自动重试最多 2 次。
        """
        # 有图片时使用 content 数组格式，无图片时直接传字符串（两种格式 API 均支持）
        if request.images:
            content: list[dict] = []
            for b64 in request.images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64,
                    },
                })
            content.append({"type": "text", "text": request.prompt})
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": request.prompt}]

        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=messages,
        )
        # Thinking models return multiple content blocks:
        #   [thinking_block, text_block]
        # Extract the last text block to skip the thinking/reasoning chain.
        text = ""
        for block in response.content:
            if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                text = block.text
        # Fallback: if no explicit text block found, take first block
        if not text and response.content:
            text = getattr(response.content[0], "text", "")
        if not text.strip() and _attempt < max(0, request.max_retries):
            return self.call(request, _attempt=_attempt + 1)
        return text


# ---------------------------------------------------------------------------
# OpenAICompatClient：使用 OpenAI API 协议的客户端
# （用于 DashScope / DeepSeek / 其他 OpenAI 兼容 API）
# ---------------------------------------------------------------------------

class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        model_id: str,
        provider: str,
        role: ModelRole,
        api_key: str,
        timeout: int = 120,
    ) -> None:
        self.role     = role
        self.model_id = model_id
        self.provider = provider
        self.timeout  = timeout
        self._client  = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=float(timeout),
        )

    def supports_images(self) -> bool:
        return True

    def call(self, request: ModelRequest, _attempt: int = 0) -> str:
        if request.images:
            content: list[dict] = []
            for b64 in request.images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}",
                    },
                })
            content.append({"type": "text", "text": request.prompt})
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": request.prompt}]

        response = self._client.chat.completions.create(
            model=self.model_id,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=messages,
        )
        msg = response.choices[0].message
        text = msg.content or ""
        # Thinking models (e.g. GLM-5.1) put output in reasoning_content
        # when max_tokens is exhausted before generating final content.
        if not text.strip():
            reasoning = getattr(msg, "reasoning_content", None) or ""
            if reasoning.strip():
                text = reasoning
        if not text.strip() and _attempt < max(0, request.max_retries):
            return self.call(request, _attempt=_attempt + 1)
        return text

    def stream(self, request: ModelRequest):
        """
        流式生成：逐 token 产出文本片段。调用方 `for chunk in client.stream(...)`。
        仅用于对话场景（追问 AI 老师），批改不走这里。
        纯文本、无图片模式；出错或不支持时抛异常，由上层 fallback 到 call()。
        """
        messages = [{"role": "user", "content": request.prompt}]
        response = self._client.chat.completions.create(
            model=self.model_id,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            try:
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None) or ""
                if piece:
                    yield piece
            except (IndexError, AttributeError):
                continue


class MathpixOCRClient:
    """Mathpix Convert API adapter for pure OCR text extraction."""

    role = ModelRole.ocr
    provider = "mathpix"

    def __init__(
        self,
        *,
        app_id: str,
        app_key: str,
        base_url: str = "https://api.mathpix.com",
        timeout: float = 15.0,
    ) -> None:
        self.app_id = app_id.strip()
        self.app_key = app_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = max(0.1, float(timeout or 15.0))
        self.model_id = "mathpix:v3/text"

    def supports_images(self) -> bool:
        return True

    def call(self, request: ModelRequest) -> str:
        if not request.images:
            return ""
        texts: list[str] = []
        for b64 in request.images:
            text = self._ocr_b64(b64)
            if text.strip():
                texts.append(text.strip())
        return "\n\n".join(texts)

    def _ocr_b64(self, b64: str) -> str:
        payload = {
            "src": f"data:image/jpeg;base64,{b64}",
            "math_inline_delimiters": ["$", "$"],
            "rm_spaces": True,
        }
        headers = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(
                f"{self.base_url}/v3/text",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            _log.warning("Mathpix OCR failed: %s", exc)
            return ""

        if data.get("error"):
            _log.warning("Mathpix OCR returned error: %s", data.get("error"))
            return ""
        return str(data.get("text") or data.get("latex_styled") or "").strip()


class LocalOCRClient:
    """Small local OCR adapter used as a non-blocking fallback for page probes."""

    role = ModelRole.ocr
    provider = "local_tesseract"

    def __init__(
        self,
        *,
        lang: str = "eng",
        timeout: float = 3.0,
        config: str = "",
    ) -> None:
        self.lang = lang or "eng"
        self.timeout = max(0.1, float(timeout or 3.0))
        self.config = config
        self.model_id = f"tesseract:{self.lang}"

    def supports_images(self) -> bool:
        return True

    @classmethod
    def is_available(cls) -> bool:
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            return True
        except Exception as exc:
            _log.info("local OCR disabled; tesseract unavailable: %s", exc)
            return False

    def call(self, request: ModelRequest) -> str:
        if not request.images:
            return ""
        texts: list[str] = []
        for b64 in request.images:
            text = self._ocr_b64(b64)
            if text.strip():
                texts.append(text.strip())
        return "\n\n".join(texts)

    def _ocr_b64(self, b64: str) -> str:
        try:
            raw = base64.b64decode(b64)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as exc:
            _log.warning("local OCR image decode failed: %s", exc)
            return ""

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(self._image_to_string, image)
        try:
            return future.result(timeout=self.timeout) or ""
        except FutureTimeoutError:
            _log.warning("local OCR timed out after %.1fs", self.timeout)
            future.cancel()
            return ""
        except Exception as exc:
            _log.warning("local OCR failed: %s", exc)
            return ""
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _image_to_string(self, image: Image.Image) -> str:
        import pytesseract

        return pytesseract.image_to_string(
            image,
            lang=self.lang,
            config=self.config,
        )


class FallbackOCRClient:
    """Try a primary OCR client first, then a secondary OCR client if needed."""

    role = ModelRole.ocr

    def __init__(self, primary: ModelClient, fallback: ModelClient) -> None:
        self.primary = primary
        self.fallback = fallback
        self.provider = f"{primary.provider}+{fallback.provider}"
        self.model_id = f"{primary.model_id}->{fallback.model_id}"

    def supports_images(self) -> bool:
        return self.primary.supports_images() or self.fallback.supports_images()

    def call(self, request: ModelRequest) -> str:
        try:
            text = self.primary.call(request)
        except Exception as exc:
            _log.warning("%s OCR failed before fallback: %s", self.primary.provider, exc)
            text = ""
        if text.strip():
            return text
        try:
            return self.fallback.call(request)
        except Exception as exc:
            _log.warning("%s OCR fallback failed: %s", self.fallback.provider, exc)
            return ""


# ---------------------------------------------------------------------------
# ModelRegistry 工厂
# ---------------------------------------------------------------------------

def _env_flag(name: str, default: str = "0") -> bool:
    value = os.environ.get(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_client(
    role: ModelRole,
    model_id: str,
    *,
    api_key: str,
    base_url: str,
    provider: str,
) -> ModelClient:
    """
    根据 provider 类型选择 Anthropic 或 OpenAI 兼容客户端。
    provider 含 "dashscope" / "openai" / "deepseek" / "viviai" → OpenAICompatClient
    其他 → AnthropicCompatClient
    """
    openai_providers = {"dashscope", "openai", "deepseek", "viviai"}
    if provider in openai_providers:
        return OpenAICompatClient(
            base_url=base_url, model_id=model_id,
            provider=provider, role=role, api_key=api_key,
        )
    return AnthropicCompatClient(
        base_url=base_url, model_id=model_id,
        provider=provider, role=role, api_key=api_key,
    )


def _build_local_ocr_from_env() -> ModelClient | None:
    if not _env_flag("LOCAL_OCR_ENABLED"):
        return None

    local_provider = os.environ.get("LOCAL_OCR_PROVIDER", "tesseract").strip().lower()
    if local_provider != "tesseract":
        _log.warning("unsupported LOCAL_OCR_PROVIDER=%r; continuing without local OCR", local_provider)
        return None

    timeout = float(os.environ.get("LOCAL_OCR_TIMEOUT_SECONDS", "3"))
    local_ocr = LocalOCRClient(
        lang=os.environ.get("LOCAL_OCR_LANG", "eng"),
        timeout=timeout,
        config=os.environ.get("LOCAL_OCR_CONFIG", ""),
    )
    if local_ocr.is_available():
        return local_ocr

    _log.info("LOCAL_OCR_ENABLED=1 but local OCR is unavailable; continuing without OCR")
    return None


def build_registry() -> dict[ModelRole, ModelClient]:
    """
    从环境变量构造 registry。

    支持两种配置方式：
    1. 统一配置：ANTHROPIC_API_KEY + ANTHROPIC_BASE_URL（所有角色共用）
    2. 分角色配置：DASHSCOPE_API_KEY / DEEPSEEK_API_KEY 覆盖特定角色

    如果设置了 DASHSCOPE_API_KEY，则 BASE 角色使用 DashScope（阿里云百炼 / Qwen）。
    如果设置了 DEEPSEEK_API_KEY，则 REVIEW/EXPLAIN 角色使用 DeepSeek。
    """
    # --- 默认配置（vivia proxy / Anthropic）---
    default_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    default_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    default_provider = "viviai" if _looks_like_viviai(default_url) else "vivia_proxy"
    if default_provider == "viviai":
        default_url = _as_openai_base_url(default_url)

    # --- DashScope（阿里云百炼）配置 ---
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    dashscope_url = os.environ.get(
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    # --- DeepSeek 配置 ---
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    deepseek_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not default_key and not dashscope_key:
        raise RuntimeError(
            "Missing API key. Set ANTHROPIC_API_KEY or DASHSCOPE_API_KEY. "
            "See .env.example for details."
        )

    registry: dict[ModelRole, ModelClient] = {}

    # --- VISION: 专用视觉模型，用于图片识别/切题 ---
    vision_model = os.environ.get("VISION_MODEL", "")
    if dashscope_key and vision_model:
        registry[ModelRole.vision] = _build_client(
            ModelRole.vision,
            vision_model,
            api_key=dashscope_key, base_url=dashscope_url, provider="dashscope",
        )

    # --- BASE: 优先 DashScope（快速纯文本），否则用默认 ---
    if dashscope_key:
        registry[ModelRole.base] = _build_client(
            ModelRole.base,
            os.environ.get("BASE_MODEL", "qwen3.5-plus"),
            api_key=dashscope_key, base_url=dashscope_url, provider="dashscope",
        )
    else:
        registry[ModelRole.base] = _build_client(
            ModelRole.base,
            os.environ.get("BASE_MODEL", "gemini-3-flash-preview"),
            api_key=default_key, base_url=default_url, provider=default_provider,
        )

    # 如果没有单独配置 VISION，复用 BASE
    if ModelRole.vision not in registry:
        registry[ModelRole.vision] = registry[ModelRole.base]

    # --- OCR: 专用 OCR 模型，与 vision 并行交叉校验 ---
    mathpix_app_id = os.environ.get("MATHPIX_APP_ID", "").strip()
    mathpix_app_key = os.environ.get("MATHPIX_APP_KEY", "").strip()
    local_ocr = _build_local_ocr_from_env()

    if bool(mathpix_app_id) != bool(mathpix_app_key):
        _log.warning("incomplete Mathpix credentials; set both MATHPIX_APP_ID and MATHPIX_APP_KEY")

    ocr_model = os.environ.get("OCR_MODEL", "").strip()
    dashscope_ocr_model = ocr_model or "qwen-vl-ocr-latest"
    if mathpix_app_id and mathpix_app_key:
        mathpix_ocr = MathpixOCRClient(
            app_id=mathpix_app_id,
            app_key=mathpix_app_key,
            base_url=os.environ.get("MATHPIX_BASE_URL", "https://api.mathpix.com"),
            timeout=float(os.environ.get("MATHPIX_TIMEOUT_SECONDS", "15")),
        )
        registry[ModelRole.ocr] = (
            FallbackOCRClient(mathpix_ocr, local_ocr)
            if local_ocr is not None
            else mathpix_ocr
        )
    elif dashscope_key and dashscope_ocr_model:
        registry[ModelRole.ocr] = _build_client(
            ModelRole.ocr,
            dashscope_ocr_model,
            api_key=dashscope_key, base_url=dashscope_url, provider="dashscope",
        )
    elif default_key and ocr_model:
        registry[ModelRole.ocr] = _build_client(
            ModelRole.ocr,
            ocr_model,
            api_key=default_key, base_url=default_url, provider=default_provider,
        )
    elif local_ocr is not None:
        registry[ModelRole.ocr] = local_ocr

    # --- REVIEW: 优先 DeepSeek，否则用默认 ---
    # 默认 deepseek-chat (V3, 5-10s)。以前默认 deepseek-reasoner (R1, 30-75s)
    # 配合 20s timeout 几乎每次都超时降级，白等 20s 不起作用。V3 在有明确 mark
    # scheme 的 review 任务上质量差距很小（<5%），但耗时小一个数量级。
    # 想回到 R1 做精度的场景，设 REVIEW_MODEL=deepseek-reasoner（注意要把
    # pipeline.py 里的 review timeout 同步加到 90s 以上才有意义）。
    if deepseek_key:
        registry[ModelRole.review] = _build_client(
            ModelRole.review,
            os.environ.get("REVIEW_MODEL", "deepseek-chat"),
            api_key=deepseek_key, base_url=deepseek_url, provider="deepseek",
        )
    elif default_key:
        registry[ModelRole.review] = _build_client(
            ModelRole.review,
            os.environ.get("REVIEW_MODEL", "gemini-3-pro-preview"),
            api_key=default_key, base_url=default_url, provider=default_provider,
        )
    else:
        # 没有 REVIEW 专用 key，用 BASE 的 DashScope
        registry[ModelRole.review] = _build_client(
            ModelRole.review,
            os.environ.get("REVIEW_MODEL", "qwen3.5-plus"),
            api_key=dashscope_key, base_url=dashscope_url, provider="dashscope",
        )

    # --- EXPLAIN: 优先 DeepSeek-Chat (V3, 非 thinking)，5-10s 返回 ---
    # 原默认 deepseek-reasoner 要 30-60s，极易触发部署网关 502/504，改用 chat 版
    if deepseek_key:
        registry[ModelRole.explain] = _build_client(
            ModelRole.explain,
            os.environ.get("EXPLAIN_MODEL", "deepseek-chat"),
            api_key=deepseek_key, base_url=deepseek_url, provider="deepseek",
        )
    elif default_key:
        registry[ModelRole.explain] = _build_client(
            ModelRole.explain,
            os.environ.get("EXPLAIN_MODEL", "gemini-2.5-flash-thinking"),
            api_key=default_key, base_url=default_url, provider=default_provider,
        )
    else:
        registry[ModelRole.explain] = _build_client(
            ModelRole.explain,
            os.environ.get("EXPLAIN_MODEL", "qwen3.5-plus"),
            api_key=dashscope_key, base_url=dashscope_url, provider="dashscope",
        )

    return registry
