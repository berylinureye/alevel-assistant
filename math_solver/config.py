"""
多Agent并行数学解题系统 — 配置模块

所有 API 端点、模型名、超时、API Key 等集中管理。
API Key 从环境变量读取（通过 .env 文件加载）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv(override=True)


# ---------------------------------------------------------------------------
# 模型配置
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelConfig:
    """单个模型的 API 配置"""
    name: str               # 人类可读名
    base_url: str           # API 端点
    model_id: str           # 模型标识
    api_key_env: str        # 环境变量名
    timeout: float = 15.0   # 请求超时（秒）
    max_tokens: int = 4096
    temperature: float = 0.0

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise RuntimeError(f"Missing API key: set {self.api_key_env} in .env")
        return key


# --- 三个解题 Agent ---

AGENT_A = ModelConfig(
    name="DeepSeek-V3.2",
    base_url="https://api.deepseek.com/v1/chat/completions",
    model_id="deepseek-chat",
    api_key_env="DEEPSEEK_API_KEY",
    timeout=20.0,
    max_tokens=4096,
    temperature=0.0,
)

AGENT_B = ModelConfig(
    name="Qwen-Plus",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    model_id="qwen-plus",
    api_key_env="DASHSCOPE_API_KEY",
    timeout=20.0,
    max_tokens=4096,
    temperature=0.0,
)

AGENT_C = ModelConfig(
    name="GLM-5.1",
    base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
    model_id="glm-5.1",
    api_key_env="GLM_API_KEY",
    timeout=20.0,
    max_tokens=4096,
    temperature=0.0,
)

# --- 仲裁 Agent (thinking model) ---

ARBITRATOR = ModelConfig(
    name="DeepSeek-R1",
    base_url="https://api.deepseek.com/v1/chat/completions",
    model_id="deepseek-reasoner",
    api_key_env="DEEPSEEK_API_KEY",
    timeout=13.0,
    max_tokens=8192,
    temperature=0.0,
)

# 所有解题 Agent（有序列表）
SOLVER_AGENTS: list[ModelConfig] = [AGENT_A, AGENT_B, AGENT_C]

# ---------------------------------------------------------------------------
# 全局超时预算
# ---------------------------------------------------------------------------
TOTAL_TIMEOUT: float = 45.0       # 整体超时（放宽以容纳中国 API 延迟）
SOLVER_TIMEOUT: float = 20.0      # 第一层并行解题超时
VOTE_TIMEOUT: float = 2.0         # 投票逻辑超时（本地，几乎不耗时）
ARBITRATOR_TIMEOUT: float = 20.0  # 仲裁超时

# ---------------------------------------------------------------------------
# 报告模式
# ---------------------------------------------------------------------------
# "model" — 用 DeepSeek V3.2 streaming 生成报告（质量高，多一次 API 调用）
# "local" — 本地模板拼接 + 打字机效果（速度快，零额外调用）
REPORT_MODE: str = "local"

# 报告生成用的模型（仅 REPORT_MODE="model" 时生效）
REPORT_MODEL = AGENT_A  # 默认复用 DeepSeek V3.2

# 流式答案收集：至少 N 个答案到手即可投票（不必等全部完成）
STREAM_MIN_ANSWERS: int = 2
# 流式答案收集的最长等待（秒），超时后用已有答案投票
STREAM_ANSWER_TIMEOUT: float = 10.0

# ---------------------------------------------------------------------------
# 重试
# ---------------------------------------------------------------------------
MAX_RETRIES: int = 1              # API 失败自动重试次数
