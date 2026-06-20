"""Reflection Engine · 苏格拉底式追问 + Memory 触发主动推相似题

3 种 trigger，按优先级匹配第一个：
  1. Memory 检测同 topic 反复栽 ≥ N 次 → 推相似题 + 复习教材
  2. 学生明确说"不会" → 反问"你卡在哪一步"
  3. 学生跳步骤（答案给了但中间步骤少于 grader 给的解题步骤） → 引导回顾

设计上做了一件最重要的事：**不替代 grader**。grader 该给的诊断照给，Reflection 是
wrap 在 voter output 外面的一层，用户可选 mode：
  - direct（默认）：grader 直接给答案 + 反馈
  - socratic：grader 结果先暂存，先返回反问
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memory.store import MemoryStore, StudentFact


_log = logging.getLogger("reflection.engine")


class ReflectionMode(str, Enum):
    direct = "direct"        # 不开 reflection
    socratic = "socratic"    # 错了先反问


class ReflectionTrigger(str, Enum):
    none = "none"
    recurring_weakness = "recurring_weakness"  # Memory: 反复栽
    student_dont_know = "student_dont_know"    # 学生说"不会"
    skipped_steps = "skipped_steps"            # 跳步


@dataclass
class ReflectionOutput:
    """Reflection 包装层的输出"""
    trigger: ReflectionTrigger
    response_to_student: str
    keep_grader_output: bool = False  # 是否同时返回 grader 原输出
    recommended_practice: dict | None = None  # 推荐的相似题（如 {"qid": ..., "topic": ...}）


# ──────────────────────────────────────────────────────
# Trigger detection
# ──────────────────────────────────────────────────────
_DONT_KNOW_PATTERNS = [
    r"我不会",
    r"不知道.{0,5}怎么(做|算|解)",
    r"卡住了?",
    r"完全没?思路",
    r"看?不懂",
    r"i\s+don'?t\s+know",
    r"no\s+idea",
    r"stuck",
]
_DONT_KNOW_REGEX = re.compile("|".join(_DONT_KNOW_PATTERNS), re.IGNORECASE)


def _is_student_saying_dont_know(student_input: str) -> bool:
    return bool(_DONT_KNOW_REGEX.search(student_input or ""))


def _detect_skipped_steps(
    student_answer: str,
    grader_step_count: int | None,
    min_expected_steps: int = 2,
) -> bool:
    """学生只给答案没给过程

    Heuristic：grader 解出来需要 N 步骤，学生答案 < 50 字符且没换行 → 大概率跳步
    """
    if not student_answer:
        return False
    if grader_step_count is None or grader_step_count < min_expected_steps:
        return False
    is_short = len(student_answer) < 50 and "\n" not in student_answer
    return is_short


def detect_trigger(
    student_input: str,
    student_answer: str,
    grader_step_count: int | None,
    is_correct: bool,
    memory_weaknesses: list["StudentFact"] | None = None,
    recurring_threshold: int = 2,
) -> ReflectionTrigger:
    """按优先级匹配第一个 trigger"""
    # 学生明确说不会 → 最高优先级（即使 grader 判对了也尊重学生说不会）
    if _is_student_saying_dont_know(student_input):
        return ReflectionTrigger.student_dont_know

    # 错了 + Memory 显示同 topic 反复栽 → 推相似题
    if not is_correct and memory_weaknesses:
        if len(memory_weaknesses) >= recurring_threshold:
            return ReflectionTrigger.recurring_weakness

    # 错了 + 跳步 → 引导回顾
    if not is_correct and _detect_skipped_steps(student_answer, grader_step_count):
        return ReflectionTrigger.skipped_steps

    return ReflectionTrigger.none


# ──────────────────────────────────────────────────────
# Engine
# ──────────────────────────────────────────────────────
class ReflectionEngine:
    """Reflection 包装层

    Usage
    -----
    engine = ReflectionEngine(memory_store=mem, mode=ReflectionMode.socratic)
    output = engine.wrap(
        student_id="alice",
        student_input="我不会",
        student_answer="...",
        grader_output={"is_correct": False, "feedback": "...", "topic": "calc"},
    )
    if output.trigger != ReflectionTrigger.none:
        return output.response_to_student
    else:
        return grader_output  # 走默认 path
    """

    def __init__(
        self,
        memory_store: "MemoryStore | None" = None,
        mode: ReflectionMode = ReflectionMode.socratic,
    ):
        self.memory_store = memory_store
        self.mode = mode

    def wrap(
        self,
        student_id: str,
        student_input: str,
        student_answer: str,
        grader_output: dict,
    ) -> ReflectionOutput:
        """主入口。grader_output 期望含：
          - is_correct: bool
          - topic: str (e.g. 'calculus.chain_rule')
          - feedback: str
          - step_count: int | None
        """
        if self.mode == ReflectionMode.direct:
            return ReflectionOutput(
                trigger=ReflectionTrigger.none,
                response_to_student=grader_output.get("feedback", ""),
                keep_grader_output=True,
            )

        topic = grader_output.get("topic")
        is_correct = bool(grader_output.get("is_correct"))
        step_count = grader_output.get("step_count")

        # 拿 Memory 中同 topic 的 weakness
        memory_weaknesses = []
        if self.memory_store and topic:
            from memory.store import FactType
            memory_weaknesses = self.memory_store.get_facts(
                student_id, fact_type=FactType.weakness, topic=topic,
            )

        trigger = detect_trigger(
            student_input=student_input,
            student_answer=student_answer,
            grader_step_count=step_count,
            is_correct=is_correct,
            memory_weaknesses=memory_weaknesses,
        )

        if trigger == ReflectionTrigger.none:
            # 正常 path：直接返回 grader feedback
            return ReflectionOutput(
                trigger=trigger,
                response_to_student=grader_output.get("feedback", ""),
                keep_grader_output=True,
            )

        # 触发了 reflection，生成苏格拉底式响应
        response = self._build_socratic_response(
            trigger=trigger,
            grader_output=grader_output,
            memory_weaknesses=memory_weaknesses,
        )

        # 反复栽时附推荐练习题
        recommended = None
        if trigger == ReflectionTrigger.recurring_weakness and topic:
            recommended = {"topic": topic, "reason": "你在这一类反复栽，建议先做 1 道类似题"}

        return ReflectionOutput(
            trigger=trigger,
            response_to_student=response,
            keep_grader_output=False,
            recommended_practice=recommended,
        )

    def _build_socratic_response(
        self,
        trigger: ReflectionTrigger,
        grader_output: dict,
        memory_weaknesses: list,
    ) -> str:
        topic = grader_output.get("topic", "这块知识点")
        feedback = grader_output.get("feedback", "")

        if trigger == ReflectionTrigger.student_dont_know:
            return (
                f"先别急——你能告诉我**你尝试的第一步是什么**吗？\n"
                f"或者，你在哪一步开始觉得不对劲？\n\n"
                f"我先不给你最终答案——我想知道你的思路卡在哪。"
            )

        if trigger == ReflectionTrigger.skipped_steps:
            return (
                f"答案差不多，但**中间过程我看不到**——\n"
                f"你能写一下从题目到答案中间的 2-3 步推导吗？\n\n"
                f"考试给分主要看过程，不光看最终数字。"
            )

        if trigger == ReflectionTrigger.recurring_weakness:
            count = len(memory_weaknesses)
            return (
                f"我注意到你在 **{topic}** 这块反复栽了 {count} 次了——\n"
                f"不是题难，是这个**概念你的理解还没稳固**。\n\n"
                f"我先给你一道**类似但更简单的题**练手，等你做对了再回头看这道。\n"
                f"先做这道：(系统将从题库随机抽 1 道相同 topic 的简单题)"
            )

        return feedback  # fallback
