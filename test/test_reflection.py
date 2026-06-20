"""Reflection Engine 单测"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from memory.store import FactType, MemoryStore, StudentFact
from reflection.engine import (
    ReflectionEngine,
    ReflectionMode,
    ReflectionTrigger,
    detect_trigger,
    _is_student_saying_dont_know,
    _detect_skipped_steps,
)


# ──────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────
@pytest.fixture
def tmp_memory():
    with tempfile.TemporaryDirectory() as d:
        yield MemoryStore(db_path=Path(d) / "memory.db")


# ──────────────────────────────────────────────────────
# "学生说不会" 检测
# ──────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "我不会",
    "我不会这道题",
    "完全没思路",
    "卡住了",
    "看不懂",
    "i don't know",
    "I'm stuck",
    "no idea how to solve this",
])
def test_dont_know_pattern_matches(text):
    assert _is_student_saying_dont_know(text) is True


@pytest.mark.parametrize("text", [
    "我会",
    "我觉得是这样",
    "答案是 x = 5",
    "",
    "this is the answer",
])
def test_dont_know_pattern_no_false_positive(text):
    assert _is_student_saying_dont_know(text) is False


# ──────────────────────────────────────────────────────
# 跳步检测
# ──────────────────────────────────────────────────────
def test_skipped_when_short_answer_no_newline():
    assert _detect_skipped_steps("x = 5", grader_step_count=3) is True


def test_not_skipped_when_long_answer():
    long_answer = "First, I take dy/dx of the function. Then I set it to zero. Then I solve..."
    assert _detect_skipped_steps(long_answer, grader_step_count=3) is False


def test_not_skipped_when_has_newlines():
    multi_line = "Step 1\nStep 2\nStep 3"
    assert _detect_skipped_steps(multi_line, grader_step_count=3) is False


def test_not_skipped_when_grader_expects_few_steps():
    assert _detect_skipped_steps("x=5", grader_step_count=1) is False


# ──────────────────────────────────────────────────────
# Trigger 优先级
# ──────────────────────────────────────────────────────
def test_dont_know_beats_everything():
    """学生说"不会"最高优先级（即使 grader 判对）"""
    trigger = detect_trigger(
        student_input="我不会",
        student_answer="x = 5",
        grader_step_count=3,
        is_correct=True,  # 即使判对了
        memory_weaknesses=[],
    )
    assert trigger == ReflectionTrigger.student_dont_know


def test_recurring_weakness_triggers_when_2_plus_weakness_facts():
    weaknesses = [
        StudentFact("alice", FactType.weakness, "w1", topic="calc", confidence=0.8),
        StudentFact("alice", FactType.weakness, "w2", topic="calc", confidence=0.7),
    ]
    trigger = detect_trigger(
        student_input="...",
        student_answer="...",
        grader_step_count=3,
        is_correct=False,
        memory_weaknesses=weaknesses,
    )
    assert trigger == ReflectionTrigger.recurring_weakness


def test_skipped_steps_triggers_when_short_wrong_answer():
    trigger = detect_trigger(
        student_input="...",
        student_answer="x=5",
        grader_step_count=3,
        is_correct=False,
        memory_weaknesses=[],
    )
    assert trigger == ReflectionTrigger.skipped_steps


def test_no_trigger_when_correct_no_complaint():
    trigger = detect_trigger(
        student_input="...",
        student_answer="x=5",
        grader_step_count=3,
        is_correct=True,
        memory_weaknesses=[],
    )
    assert trigger == ReflectionTrigger.none


# ──────────────────────────────────────────────────────
# Engine.wrap()
# ──────────────────────────────────────────────────────
def test_direct_mode_bypasses_reflection(tmp_memory):
    engine = ReflectionEngine(tmp_memory, mode=ReflectionMode.direct)
    output = engine.wrap(
        student_id="alice",
        student_input="我不会",  # 即使说不会
        student_answer="",
        grader_output={"is_correct": False, "feedback": "答错了", "topic": "calc"},
    )
    assert output.trigger == ReflectionTrigger.none
    assert output.response_to_student == "答错了"
    assert output.keep_grader_output is True


def test_socratic_mode_responds_to_dont_know(tmp_memory):
    engine = ReflectionEngine(tmp_memory, mode=ReflectionMode.socratic)
    output = engine.wrap(
        student_id="alice",
        student_input="我不会这道题",
        student_answer="",
        grader_output={"is_correct": False, "feedback": "...", "topic": "calc"},
    )
    assert output.trigger == ReflectionTrigger.student_dont_know
    assert "卡在哪" in output.response_to_student
    assert output.keep_grader_output is False


def test_socratic_mode_responds_to_recurring_weakness(tmp_memory):
    # 预先种 2 条 weakness fact
    for i in range(2):
        tmp_memory.save_fact(StudentFact(
            "alice", FactType.weakness, f"w{i}",
            topic="calculus.chain_rule", confidence=0.8,
        ))

    engine = ReflectionEngine(tmp_memory, mode=ReflectionMode.socratic)
    output = engine.wrap(
        student_id="alice",
        student_input="解了一下",
        student_answer="答案 dy/dx = 2x",
        grader_output={
            "is_correct": False,
            "feedback": "链式法则用错了",
            "topic": "calculus.chain_rule",
            "step_count": 4,
        },
    )
    assert output.trigger == ReflectionTrigger.recurring_weakness
    assert "反复栽" in output.response_to_student
    assert "类似但更简单的题" in output.response_to_student
    assert output.recommended_practice is not None
    assert output.recommended_practice["topic"] == "calculus.chain_rule"


def test_socratic_mode_responds_to_skipped_steps(tmp_memory):
    engine = ReflectionEngine(tmp_memory, mode=ReflectionMode.socratic)
    output = engine.wrap(
        student_id="alice",
        student_input="试试",
        student_answer="x = 5",
        grader_output={
            "is_correct": False,
            "feedback": "...",
            "topic": "calc",
            "step_count": 4,  # grader 需要 4 步
        },
    )
    assert output.trigger == ReflectionTrigger.skipped_steps
    assert "中间过程" in output.response_to_student


def test_socratic_falls_through_to_grader_when_correct(tmp_memory):
    """正确题不触发 reflection 走 grader feedback path"""
    engine = ReflectionEngine(tmp_memory, mode=ReflectionMode.socratic)
    output = engine.wrap(
        student_id="alice",
        student_input="搞定",
        student_answer="x = 5\ny = 3",
        grader_output={"is_correct": True, "feedback": "对啦！", "topic": "calc", "step_count": 2},
    )
    assert output.trigger == ReflectionTrigger.none
    assert output.response_to_student == "对啦！"
    assert output.keep_grader_output is True


def test_memory_isolation_between_students(tmp_memory):
    """bob 的 weakness 不该影响 alice 的 trigger"""
    for i in range(3):
        tmp_memory.save_fact(StudentFact(
            "bob", FactType.weakness, f"w{i}", topic="calc", confidence=0.8,
        ))

    engine = ReflectionEngine(tmp_memory, mode=ReflectionMode.socratic)
    output = engine.wrap(
        student_id="alice",  # 不是 bob
        student_input="尝试一下",
        student_answer="dy/dx = 2x",
        grader_output={"is_correct": False, "feedback": "...", "topic": "calc", "step_count": 4},
    )
    # alice 没有 weakness，bob 的 weakness 不该被算进来
    assert output.trigger != ReflectionTrigger.recurring_weakness


def test_engine_without_memory_store():
    """没传 memory_store 时不应该 crash"""
    engine = ReflectionEngine(memory_store=None, mode=ReflectionMode.socratic)
    output = engine.wrap(
        student_id="alice",
        student_input="我不会",
        student_answer="",
        grader_output={"is_correct": False, "feedback": "...", "topic": "calc"},
    )
    # 没 memory 但学生说不会还是该触发
    assert output.trigger == ReflectionTrigger.student_dont_know
