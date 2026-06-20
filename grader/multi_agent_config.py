"""
多 Agent 并行批改 — 配置 + agent client 工厂

5-agent early-return voting architecture:
- 3 fast agents (deepseek-chat, qwen-plus, glm-4-plus) 正常 5–8s 返回
- 2 accurate agents (qwen-max-latest, glm-5.1) 10–25s 返回，作为仲裁
- 前 3 个返回且一致即提前出结果，剩余 agent 结果忽略（已调用的 API 不取消）

设计目标：提升准确率（5 票冗余）不增加延迟（早返回跳过慢 agent）
"""
from __future__ import annotations

import logging
import os
import threading
import time
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(override=True)

_log = logging.getLogger("multi_agent_config")

# ======== 超时配置 ========
AGENT_TIMEOUT_SECONDS = 30          # 单 agent 最大等待（给 glm-5.1 / qwen-max 留空间）
TOTAL_GRADING_TIMEOUT = 35          # 整体硬上限（早返回通常用不到）
AGENT_MAX_RETRIES = 1               # API 错误重试次数（超时不重试）

# ======== 早返回投票配置 ========
EARLY_RETURN_ENABLED = True         # 总开关
EARLY_RETURN_MIN_AGENTS = 3         # 达成一致所需最少 agent 数
EARLY_RETURN_SCORE_TOLERANCE = 1.0  # 分数差容忍（差 ≤ 1 分视为一致）

# ======== 投票配置 ========
SCORE_VARIANCE_THRESHOLD = 20       # 分数方差 <= 此值取 median，> 此值取最佳 feedback 方的分数

# ======== Confidence 调整配置 ========
CONFIDENCE_ADJUSTMENTS = {
    "unanimous":    +0.15,          # 5/5 或全员一致
    "majority":     +0.05,          # 过半一致
    "early_return": +0.10,          # 早返回命中（3 个快速达成一致）
    "needs_review": -0.25,          # 无多数（分裂）
}
SCORE_VARIANCE_PENALTY_THRESHOLD = 30   # 分数方差超过此值额外扣 confidence
SCORE_VARIANCE_PENALTY = -0.1
LOW_CONFIDENCE_THRESHOLD = 0.5          # 低于此值自动标记 needs_review

# Viviai / New API unified gateway defaults. Override in .env if the model
# pool changes on the gateway.
VIVIAI_FAST_MODELS_DEFAULT = (
    "gemini-2.5-flash-lite,"
    "gemini-2.5-flash,"
    "gemini-3-flash-preview"
)
VIVIAI_ACCURATE_MODELS_DEFAULT = "gemini-2.5-pro,gemini-3-pro-preview"


class _RateLimitedClient:
    """
    包装 ModelClient，加入请求间隔限制（线程安全）。
    用于 GLM 等 RPM 较低的 API，防止多题并发时触发 429。
    """

    def __init__(self, inner, min_interval: float = 3.0):
        self._inner = inner
        self._min_interval = min_interval
        self._lock = threading.Lock()
        self._last_call = 0.0

        # 透传 Protocol 属性
        self.role = inner.role
        self.model_id = inner.model_id
        self.provider = inner.provider

    def supports_images(self) -> bool:
        return self._inner.supports_images()

    def call(self, request, _attempt: int = 0):
        with self._lock:
            elapsed = time.monotonic() - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()
        return self._inner.call(request, _attempt=_attempt)


# GLM 请求最小间隔（秒），防止 429（glm-5.1 RPM 限制较严）
GLM_MIN_REQUEST_INTERVAL = 5.0

# 共享 GLM 限流锁（跨 GLM-Fast / GLM-Thinking 生效，防止并发 429）
_GLM_SHARED_LOCK = threading.Lock()
_GLM_LAST_CALL = [0.0]  # list to allow closure mutation


class _SharedGLMClient:
    """所有 GLM agent 共用同一把锁，确保 GLM 端点整体 RPM 不超标。"""

    def __init__(self, inner, min_interval: float = GLM_MIN_REQUEST_INTERVAL):
        self._inner = inner
        self._min_interval = min_interval
        self.role = inner.role
        self.model_id = inner.model_id
        self.provider = inner.provider

    def supports_images(self) -> bool:
        return self._inner.supports_images()

    def call(self, request, _attempt: int = 0):
        with _GLM_SHARED_LOCK:
            elapsed = time.monotonic() - _GLM_LAST_CALL[0]
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            _GLM_LAST_CALL[0] = time.monotonic()
        return self._inner.call(request, _attempt=_attempt)


def _split_models(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]


def _as_openai_base_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    return clean if clean.endswith("/v1") else f"{clean}/v1"


def _looks_like_viviai(base_url: str) -> bool:
    return "viviai.cc" in urlparse(base_url).netloc.lower()


def _build_viviai_agents():
    """Build the 5-agent debate roster from a single Viviai/New API key."""
    from router.models import ModelRole, OpenAICompatClient

    api_key = (
        os.environ.get("VIVIAI_API_KEY", "").strip()
        or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    )
    base_url = os.environ.get("VIVIAI_BASE_URL", "").strip() or os.environ.get(
        "ANTHROPIC_BASE_URL", ""
    ).strip()
    if not api_key or not _looks_like_viviai(base_url):
        return []

    base_url = _as_openai_base_url(base_url)
    fast_models = _split_models(
        os.environ.get("VIVIAI_FAST_MODELS", VIVIAI_FAST_MODELS_DEFAULT)
    )
    accurate_models = _split_models(
        os.environ.get("VIVIAI_ACCURATE_MODELS", VIVIAI_ACCURATE_MODELS_DEFAULT)
    )

    agents: list[tuple[str, object]] = []
    for idx, model_id in enumerate(fast_models, start=1):
        name = f"Viviai-Fast-{idx}"
        client = OpenAICompatClient(
            base_url=base_url,
            model_id=model_id,
            provider="viviai",
            role=ModelRole.base,
            api_key=api_key,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        agents.append((name, client))
        AGENT_TIERS[name] = "fast"
        _log.info("Grading agent registered: %s (%s)", name, model_id)

    for idx, model_id in enumerate(accurate_models, start=1):
        name = f"Viviai-Accurate-{idx}"
        client = OpenAICompatClient(
            base_url=base_url,
            model_id=model_id,
            provider="viviai",
            role=ModelRole.base,
            api_key=api_key,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        agents.append((name, client))
        AGENT_TIERS[name] = "accurate"
        _log.info("Grading agent registered: %s (%s)", name, model_id)

    return agents


def build_grading_agents():
    """
    构建可用的 agent clients。5-agent 架构：

    Fast tier (3–8s):
      - DeepSeek (deepseek-chat)
      - Qwen-Fast (qwen-plus)
      - GLM-Fast (glm-4-plus)
    Accurate tier (10–25s):
      - Qwen-Accurate (qwen-max-latest)
      - GLM-Thinking (glm-5.1)

    返回 [(agent_name, ModelClient), ...] — 至少 1 个，否则 raise。
    Tier 信息通过模块级 AGENT_TIERS 映射暴露。
    """
    # Prefer the unified Viviai gateway when configured. This keeps the
    # debate/voting architecture intact without requiring separate provider keys.
    viviai_agents = _build_viviai_agents()
    if viviai_agents:
        _log.info(
            "Multi-agent grading via Viviai: %d agents available (fast=%d, accurate=%d)",
            len(viviai_agents),
            sum(1 for n, _ in viviai_agents if AGENT_TIERS.get(n) == "fast"),
            sum(1 for n, _ in viviai_agents if AGENT_TIERS.get(n) == "accurate"),
        )
        return viviai_agents

    from router.models import ModelRole, OpenAICompatClient

    agents: list[tuple[str, object]] = []

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    dashscope_key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
    glm_key = os.environ.get("GLM_API_KEY", "").strip()

    # ---- Fast tier ----
    if deepseek_key:
        client = OpenAICompatClient(
            base_url="https://api.deepseek.com/v1",
            model_id="deepseek-chat",
            provider="deepseek",
            role=ModelRole.base,
            api_key=deepseek_key,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        agents.append(("DeepSeek-Fast", client))
        _log.info("Grading agent registered: DeepSeek-Fast (deepseek-chat)")

    if dashscope_key:
        client = OpenAICompatClient(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_id="qwen-plus",
            provider="dashscope",
            role=ModelRole.base,
            api_key=dashscope_key,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        agents.append(("Qwen-Fast", client))
        _log.info("Grading agent registered: Qwen-Fast (qwen-plus)")

    if glm_key:
        client = OpenAICompatClient(
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model_id="glm-4-plus",
            provider="glm",
            role=ModelRole.base,
            api_key=glm_key,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        # 共享 GLM 限流锁（跨所有 GLM agent 生效）
        client = _SharedGLMClient(client)
        agents.append(("GLM-Fast", client))
        _log.info("Grading agent registered: GLM-Fast (glm-4-plus)")

    # ---- Accurate tier ----
    if dashscope_key:
        client = OpenAICompatClient(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_id="qwen-max-latest",
            provider="dashscope",
            role=ModelRole.base,
            api_key=dashscope_key,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        agents.append(("Qwen-Accurate", client))
        _log.info("Grading agent registered: Qwen-Accurate (qwen-max-latest)")

    if glm_key:
        client = OpenAICompatClient(
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model_id="glm-5.1",  # thinking model, slowest but strongest for reasoning
            provider="glm",
            role=ModelRole.base,
            api_key=glm_key,
            timeout=AGENT_TIMEOUT_SECONDS,
        )
        # 共享 GLM 限流锁（跨所有 GLM agent 生效）
        client = _SharedGLMClient(client)
        agents.append(("GLM-Thinking", client))
        _log.info("Grading agent registered: GLM-Thinking (glm-5.1)")

    if not agents:
        raise RuntimeError(
            "至少需要配置一个 agent 的 API key "
            "(DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / GLM_API_KEY)"
        )

    _log.info(
        "Multi-agent grading: %d agents available (fast=%d, accurate=%d)",
        len(agents),
        sum(1 for n, _ in agents if AGENT_TIERS.get(n) == "fast"),
        sum(1 for n, _ in agents if AGENT_TIERS.get(n) == "accurate"),
    )
    return agents


# ======== Tier 映射（agent_name → tier）========
AGENT_TIERS: dict[str, str] = {
    "DeepSeek-Fast":  "fast",
    "Qwen-Fast":      "fast",
    "GLM-Fast":       "fast",
    "Qwen-Accurate":  "accurate",
    "GLM-Thinking":   "accurate",
}
