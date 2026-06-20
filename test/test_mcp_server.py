"""MCP server tool dispatcher 单测（不启动 stdio loop，直接测 handler）"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# 让 MCP_server_wrapper 用临时 db
@pytest.fixture(autouse=True)
def tmp_memory_db(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("ALEVEL_MEMORY_DB", str(Path(d) / "memory.db"))
        # reload mcp_server_wrapper module to pick up new env
        import importlib
        import mcp_server_wrapper
        importlib.reload(mcp_server_wrapper)
        yield mcp_server_wrapper


def test_classify_question(tmp_memory_db):
    result = tmp_memory_db._tool_classify({"question_text": "Differentiate y = x^3 + 2x"})
    assert "question_type" in result
    assert result["question_type"]  # 不是空字符串


def test_verify_calculation_correct(tmp_memory_db):
    result = tmp_memory_db._tool_verify({"expression": "186 + 910", "claimed_result": "1096"})
    # v1 verify_calculation 返回 {is_correct, actual_result}
    assert result["is_correct"] is True
    assert result["actual_result"] == "1096"


def test_verify_calculation_detects_wrong_claim(tmp_memory_db):
    result = tmp_memory_db._tool_verify({"expression": "186 + 910", "claimed_result": "1086"})
    assert result["is_correct"] is False


def test_verify_calculation_handles_error(tmp_memory_db):
    """SymPy 无法解析的表达式应该 graceful fail，不抛"""
    result = tmp_memory_db._tool_verify({"expression": "@@@@", "claimed_result": "?"})
    # 不该抛异常，应该返回 dict（含 error 或者特殊标记）
    assert isinstance(result, dict)


def test_save_and_get_memory_full_cycle(tmp_memory_db):
    """端到端：通过 mcp tool 接口存 fact + 读 fact"""
    # 存
    save_result = tmp_memory_db._tool_save_fact({
        "student_id": "alice",
        "fact_type": "weakness",
        "fact_text": "导数链式法则反复错",
        "topic": "calculus.chain_rule",
        "confidence": 0.85,
        "session_id": "test_s001",
    })
    assert save_result["saved"] == 1

    # 读
    get_result = tmp_memory_db._tool_get_memory({
        "student_id": "alice",
        "max_facts": 10,
    })
    assert get_result["fact_count"] == 1
    assert "导数链式法则反复错" in get_result["prompt"]
    assert get_result["facts"][0]["fact_type"] == "weakness"


def test_get_memory_empty_for_new_student(tmp_memory_db):
    result = tmp_memory_db._tool_get_memory({"student_id": "new_kid"})
    assert result["fact_count"] == 0
    assert result["prompt"] == ""
    assert result["facts"] == []


def test_get_memory_filters_by_fact_type(tmp_memory_db):
    # 存 2 类 fact
    tmp_memory_db._tool_save_fact({
        "student_id": "alice", "fact_type": "weakness",
        "fact_text": "w1", "confidence": 0.8,
    })
    tmp_memory_db._tool_save_fact({
        "student_id": "alice", "fact_type": "goal",
        "fact_text": "g1", "confidence": 0.7,
    })

    # 只查 weakness
    result = tmp_memory_db._tool_get_memory({
        "student_id": "alice",
        "fact_type": "weakness",
    })
    assert result["fact_count"] == 1
    assert result["facts"][0]["fact_text"] == "w1"


def test_save_fact_conflict_resolution_via_mcp(tmp_memory_db):
    """通过 mcp 接口存两次同 topic fact，第一次应该 decay"""
    tmp_memory_db._tool_save_fact({
        "student_id": "alice", "fact_type": "weakness",
        "fact_text": "旧 fact", "topic": "calc", "confidence": 1.0,
    })

    result = tmp_memory_db._tool_save_fact({
        "student_id": "alice", "fact_type": "weakness",
        "fact_text": "新 fact", "topic": "calc", "confidence": 0.8,
    })
    assert result["saved"] == 1
    assert result["decayed"] == 1

    # 现在应该有 2 条
    get_result = tmp_memory_db._tool_get_memory({"student_id": "alice"})
    assert get_result["fact_count"] == 2


def test_tools_list_has_4_tools(tmp_memory_db):
    """confirm we export the 4 promised tools"""
    names = [t.name for t in tmp_memory_db.TOOLS]
    assert "classify_question" in names
    assert "verify_calculation" in names
    assert "get_student_memory" in names
    assert "save_student_fact" in names
