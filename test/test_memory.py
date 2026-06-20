"""Memory store 单测 · 不依赖 LLM key"""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import pytest

from memory.store import FactType, MemoryStore, StudentFact
from memory.extractor import _parse_facts_json


# ──────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────
@pytest.fixture
def tmp_store():
    """每个 test 用一个独立 tmp sqlite"""
    with tempfile.TemporaryDirectory() as d:
        store = MemoryStore(db_path=Path(d) / "memory.db")
        yield store


# ──────────────────────────────────────────────────────
# 基础 CRUD
# ──────────────────────────────────────────────────────
def test_save_and_get_single_fact(tmp_store):
    fact = StudentFact(
        student_id="alice",
        fact_type=FactType.weakness,
        fact_text="导数链式法则反复错",
        topic="calculus.chain_rule",
        confidence=0.8,
        source_session_id="s001",
    )
    rowid = tmp_store.save_fact(fact)
    assert rowid > 0

    facts = tmp_store.get_facts("alice")
    assert len(facts) == 1
    assert facts[0].fact_text == "导数链式法则反复错"
    assert facts[0].fact_type == FactType.weakness
    assert facts[0].confidence == 0.8


def test_get_facts_filtered_by_type(tmp_store):
    tmp_store.save_fact(
        StudentFact("alice", FactType.weakness, "薄弱 1", confidence=0.9)
    )
    tmp_store.save_fact(
        StudentFact("alice", FactType.goal, "冲 A*", confidence=0.7)
    )

    weaknesses = tmp_store.get_facts("alice", fact_type=FactType.weakness)
    assert len(weaknesses) == 1
    assert weaknesses[0].fact_text == "薄弱 1"

    goals = tmp_store.get_facts("alice", fact_type=FactType.goal)
    assert len(goals) == 1


def test_min_confidence_filter(tmp_store):
    tmp_store.save_fact(
        StudentFact("alice", FactType.weakness, "强证据", confidence=0.9)
    )
    tmp_store.save_fact(
        StudentFact("alice", FactType.weakness, "弱证据", confidence=0.15)
    )

    facts = tmp_store.get_facts("alice", min_confidence=0.3)
    assert len(facts) == 1
    assert facts[0].fact_text == "强证据"


def test_facts_ordered_by_confidence_desc(tmp_store):
    tmp_store.save_fact(
        StudentFact("alice", FactType.weakness, "中等", confidence=0.5)
    )
    tmp_store.save_fact(
        StudentFact("alice", FactType.weakness, "最强", confidence=0.95)
    )
    tmp_store.save_fact(
        StudentFact("alice", FactType.weakness, "次强", confidence=0.7)
    )

    facts = tmp_store.get_facts("alice")
    assert facts[0].fact_text == "最强"
    assert facts[1].fact_text == "次强"
    assert facts[2].fact_text == "中等"


# ──────────────────────────────────────────────────────
# Conflict Resolution（核心特性）
# ──────────────────────────────────────────────────────
def test_conflict_resolution_old_fact_decays(tmp_store):
    """旧 fact 在新 fact 入库时 confidence × 0.5"""
    # 旧 fact: confidence 1.0
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "导数链式法则反复错",
        topic="calculus.chain_rule", confidence=1.0,
    ))

    # 新 fact 入库（同 student + 同 topic + 同 fact_type）
    result = tmp_store.save_facts_with_conflict_resolve(
        "alice",
        [StudentFact(
            "alice", FactType.weakness, "导数链式法则又错了",
            topic="calculus.chain_rule", confidence=0.7,
        )],
    )

    assert result["saved"] == 1
    assert result["decayed"] == 1
    assert result["forgotten"] == 0

    # 现在应该有 2 条 fact（新+旧），旧的 confidence 0.5
    facts = tmp_store.get_facts("alice", min_confidence=0.0)
    assert len(facts) == 2
    confidences = sorted([f.confidence for f in facts])
    assert confidences == [0.5, 0.7]


def test_conflict_resolution_forgets_when_decayed_below_threshold(tmp_store):
    """旧 fact 衰减到 < 0.05 就实际删除"""
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "极弱旧证据",
        topic="algebra", confidence=0.08,  # 0.08 * 0.5 = 0.04 < 0.05
    ))

    result = tmp_store.save_facts_with_conflict_resolve(
        "alice",
        [StudentFact(
            "alice", FactType.weakness, "新证据",
            topic="algebra", confidence=0.8,
        )],
    )

    assert result["forgotten"] == 1
    assert result["decayed"] == 0
    assert result["saved"] == 1

    facts = tmp_store.get_facts("alice", min_confidence=0.0)
    assert len(facts) == 1
    assert facts[0].fact_text == "新证据"


def test_no_conflict_when_topic_differs(tmp_store):
    """不同 topic 不算冲突"""
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "导数错", topic="calculus", confidence=0.8,
    ))

    result = tmp_store.save_facts_with_conflict_resolve(
        "alice",
        [StudentFact(
            "alice", FactType.weakness, "积分错", topic="integration", confidence=0.8,
        )],
    )

    assert result["decayed"] == 0
    assert result["saved"] == 1
    facts = tmp_store.get_facts("alice", min_confidence=0.0)
    assert len(facts) == 2


def test_conflict_isolation_between_students(tmp_store):
    """不同学生互不影响"""
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "alice 薄弱", topic="t", confidence=1.0,
    ))

    result = tmp_store.save_facts_with_conflict_resolve(
        "bob",
        [StudentFact("bob", FactType.weakness, "bob 薄弱", topic="t", confidence=0.8)],
    )

    # bob 入库不该影响 alice
    assert result["decayed"] == 0
    alice_facts = tmp_store.get_facts("alice")
    assert len(alice_facts) == 1
    assert alice_facts[0].confidence == 1.0  # 没被衰减


# ──────────────────────────────────────────────────────
# Memory prompt 生成
# ──────────────────────────────────────────────────────
def test_memory_prompt_empty_for_new_student(tmp_store):
    assert tmp_store.get_memory_prompt("new_student") == ""


def test_memory_prompt_formats_facts(tmp_store):
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "导数链式法则反复错",
        topic="calculus.chain_rule", confidence=0.9,
    ))
    tmp_store.save_fact(StudentFact(
        "alice", FactType.goal, "目标 A*", confidence=0.85,
    ))

    prompt = tmp_store.get_memory_prompt("alice")
    assert "## 这位学生的已知背景" in prompt
    assert "⚠️ 薄弱点" in prompt
    assert "🎯 目标" in prompt
    assert "导数链式法则反复错" in prompt
    assert "0.90" in prompt or "0.9" in prompt
    assert "[calculus.chain_rule]" in prompt


def test_memory_prompt_filters_low_confidence(tmp_store):
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "强 fact", confidence=0.8,
    ))
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "弱 fact", confidence=0.2,
    ))

    prompt = tmp_store.get_memory_prompt("alice")
    assert "强 fact" in prompt
    assert "弱 fact" not in prompt  # 默认 min_confidence=0.3


# ──────────────────────────────────────────────────────
# GDPR · 用户权利
# ──────────────────────────────────────────────────────
def test_export_all(tmp_store):
    tmp_store.save_fact(StudentFact(
        "alice", FactType.weakness, "f1", confidence=0.8,
    ))
    tmp_store.save_fact(StudentFact(
        "alice", FactType.goal, "f2", confidence=0.6,
    ))

    exported = tmp_store.export_all("alice")
    assert len(exported) == 2
    assert all(isinstance(e, dict) for e in exported)
    assert {e["fact_text"] for e in exported} == {"f1", "f2"}


def test_delete_all(tmp_store):
    for i in range(5):
        tmp_store.save_fact(StudentFact(
            "alice", FactType.weakness, f"f{i}", confidence=0.5,
        ))

    deleted = tmp_store.delete_all("alice")
    assert deleted == 5
    assert tmp_store.get_facts("alice") == []


# ──────────────────────────────────────────────────────
# JSON 解析（extractor 内部）
# ──────────────────────────────────────────────────────
def test_parse_facts_json_clean_array():
    raw = '''[
      {"fact_type": "weakness", "fact_text": "薄弱 1", "topic": "calc", "confidence": 0.8},
      {"fact_type": "goal", "fact_text": "目标 A*", "topic": null, "confidence": 0.7}
    ]'''
    facts = _parse_facts_json(raw, "alice", "s001")
    assert len(facts) == 2
    assert facts[0].fact_type == FactType.weakness
    assert facts[0].topic == "calc"
    assert facts[1].topic is None


def test_parse_facts_json_strips_markdown_fence():
    raw = """```json
    [{"fact_type": "weakness", "fact_text": "X", "topic": null, "confidence": 0.5}]
    ```"""
    facts = _parse_facts_json(raw, "alice", "s001")
    assert len(facts) == 1


def test_parse_facts_json_filters_low_confidence():
    raw = '''[
      {"fact_type": "weakness", "fact_text": "强", "confidence": 0.8},
      {"fact_type": "weakness", "fact_text": "弱", "confidence": 0.1}
    ]'''
    facts = _parse_facts_json(raw, "alice", "s001")
    assert len(facts) == 1
    assert facts[0].fact_text == "强"


def test_parse_facts_json_invalid_input():
    assert _parse_facts_json("not json", "alice", "s001") == []
    assert _parse_facts_json("{}", "alice", "s001") == []  # 不是 list
    assert _parse_facts_json("[1,2,3]", "alice", "s001") == []  # 不是 dict
