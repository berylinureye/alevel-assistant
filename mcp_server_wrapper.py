"""A-Level Agent MCP Server · 把内部能力暴露给外部 Agent

v1.5 升级：让 Claude Code / Cursor / 其他 Agent 能 over MCP 协议调用：
  · classify_question        题型识别
  · verify_calculation       SymPy 符号验证
  · find_similar_question    题库相似题查询
  · get_student_memory       拉学生 memory（薄弱点 / 偏好 / 进度 / 目标）

设计：MCP server 是 wrapper，不重复实现——所有 tool 都委托给 v1 已有的模块。

跑法（stdio）:
    python mcp_server_wrapper.py
然后外部 Claude Code 在 mcpServers config 加：
    {
      "alevel-tools": {
        "command": "python",
        "args": ["/path/to/mcp_server_wrapper.py"]
      }
    }
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Allow import as standalone script
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from grader.solution_verifier import verify_calculation
from grader.classifier import classify_question
from memory.store import FactType, MemoryStore


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("alevel-mcp")


# 全局单例（mcp server 进程级共享）
MEMORY_STORE = MemoryStore(db_path=os.environ.get("ALEVEL_MEMORY_DB", "data/memory.db"))


server = Server("alevel-tools")


# ─────────────────────────────────────────────────
# Tool definitions
# ─────────────────────────────────────────────────
TOOLS = [
    Tool(
        name="classify_question",
        description=(
            "识别 A-Level 数学题的类型（stationary_points / integration / "
            "differentiation / statistics / probability / 等）。输入题目文本，"
            "输出 QuestionType enum 值。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "question_text": {"type": "string", "description": "题目文本"},
            },
            "required": ["question_text"],
        },
    ),
    Tool(
        name="verify_calculation",
        description=(
            "用 SymPy 符号验证一个数学计算表达式。例如 verify_calculation('186 + 910 / 32', '34.25')"
            " 会返回 {correct: true/false, computed: ...}。5 秒 timeout 保护，"
            "卡住返回 inconclusive 而非异常。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "数学表达式，例如 '186 + 910'"},
                "claimed_result": {"type": "string", "description": "声称的结果，例如 '1096'"},
            },
            "required": ["expression", "claimed_result"],
        },
    ),
    Tool(
        name="get_student_memory",
        description=(
            "拉某个学生的 memory（4 类 fact：weakness / preference / progress / goal）。"
            "用于在批改前给 LLM 注入学生背景。返回格式化的 prompt 段落。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "student_id": {"type": "string"},
                "max_facts": {"type": "integer", "default": 10},
                "fact_type": {
                    "type": "string",
                    "enum": ["weakness", "preference", "progress", "goal"],
                    "description": "可选，只查指定类型",
                },
            },
            "required": ["student_id"],
        },
    ),
    Tool(
        name="save_student_fact",
        description=(
            "给学生 memory 加一条 fact。会自动做 conflict resolution（同 topic 旧 fact decay）。"
            "用于 grader 跑完后让 LLM 抽 fact 入库。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "student_id":  {"type": "string"},
                "fact_type":   {"type": "string", "enum": ["weakness", "preference", "progress", "goal"]},
                "fact_text":   {"type": "string"},
                "topic":       {"type": ["string", "null"], "description": "可选 topic slug"},
                "confidence":  {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "session_id":  {"type": ["string", "null"]},
            },
            "required": ["student_id", "fact_type", "fact_text", "confidence"],
        },
    ),
]


# ─────────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """主入口：分发到对应 tool"""
    try:
        if name == "classify_question":
            result = _tool_classify(arguments)
        elif name == "verify_calculation":
            result = _tool_verify(arguments)
        elif name == "get_student_memory":
            result = _tool_get_memory(arguments)
        elif name == "save_student_fact":
            result = _tool_save_fact(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
    except Exception as e:
        _log.exception("Tool %s failed", name)
        result = {"error": str(e), "tool": name}

    # MCP 协议要求返回 list[TextContent]
    import json
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _tool_classify(args: dict) -> dict:
    qt = classify_question(args["question_text"])
    return {
        "question_type": qt.value if hasattr(qt, "value") else str(qt),
        "method": "rule" if qt is not None else "unknown",
    }


def _tool_verify(args: dict) -> dict:
    return verify_calculation(args["expression"], args["claimed_result"])


def _tool_get_memory(args: dict) -> dict:
    ft = None
    if "fact_type" in args and args["fact_type"]:
        ft = FactType(args["fact_type"])

    facts = MEMORY_STORE.get_facts(
        student_id=args["student_id"],
        fact_type=ft,
        min_confidence=0.3,
    )

    return {
        "student_id": args["student_id"],
        "fact_count": len(facts),
        "prompt": MEMORY_STORE.get_memory_prompt(
            args["student_id"],
            max_facts=args.get("max_facts", 10),
        ),
        "facts": [
            {
                "fact_type": f.fact_type.value,
                "fact_text": f.fact_text,
                "topic": f.topic,
                "confidence": f.confidence,
                "updated_at": f.updated_at,
            }
            for f in facts
        ],
    }


def _tool_save_fact(args: dict) -> dict:
    from memory.store import StudentFact

    fact = StudentFact(
        student_id=args["student_id"],
        fact_type=FactType(args["fact_type"]),
        fact_text=args["fact_text"],
        topic=args.get("topic"),
        confidence=float(args["confidence"]),
        source_session_id=args.get("session_id"),
    )
    result = MEMORY_STORE.save_facts_with_conflict_resolve(
        student_id=fact.student_id,
        new_facts=[fact],
    )
    return result


# ─────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────
async def main():
    _log.info("Starting alevel-tools MCP server on stdio")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
