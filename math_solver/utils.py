"""
多Agent并行数学解题系统 — 辅助工具（日志、计时）
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Optional


def setup_logger(name: str = "math_solver", level: int = logging.INFO) -> logging.Logger:
    """创建带颜色的 logger"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s │ %(levelname)-5s │ %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger


log = setup_logger()


@contextmanager
def timer(label: str) -> Generator[dict[str, float], None, None]:
    """计时上下文管理器，结果写入 result["elapsed"]"""
    result: dict[str, float] = {"elapsed": 0.0}
    t0 = time.perf_counter()
    try:
        yield result
    finally:
        result["elapsed"] = time.perf_counter() - t0
        log.info(f"⏱  {label}: {result['elapsed']:.2f}s")


@dataclass
class AgentResult:
    """单个 Agent 的解题结果"""
    agent_name: str
    raw_output: str = ""
    raw_answer: str = ""          # 从输出中提取的原始答案
    normalized_answer: str = ""   # 归一化后的答案
    elapsed: float = 0.0          # 耗时（秒）
    error: Optional[str] = None   # 错误信息（超时/API 错误等）
    success: bool = False


@dataclass
class SolveResult:
    """最终解题结果"""
    question: str
    final_answer: str = ""
    confidence: str = "low"       # high / medium / low
    method: str = ""              # unanimous / majority_vote / arbitration / fallback
    total_elapsed: float = 0.0
    agent_results: list[AgentResult] = field(default_factory=list)
    arbitrator_output: Optional[str] = None
    arbitrator_elapsed: Optional[float] = None
