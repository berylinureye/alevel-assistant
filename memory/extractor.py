"""Fact Extraction Pipeline · 每次 session 结束后跑一次

输入：session 内的题目 + 学生答案 + grader 判分 + 反馈
输出：4 类 fact list（weakness / preference / progress / goal）

LLM Prompt 设计（Mem0 风格）：
- 只抽真正暴露的，不要编造
- 每条 fact 给 confidence (0-1) 让上层做衰减
- 强制结构化 JSON 输出
"""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from memory.store import FactType, StudentFact

if TYPE_CHECKING:
    from router.models import ModelClient


_log = logging.getLogger("memory.extractor")


FACT_EXTRACTION_PROMPT = """你是一个学生学情分析师。分析以下 A-Level 数学批改 session，抽取这位学生暴露的 fact。

# 输入
学生 ID：{student_id}
Session ID：{session_id}

## 本次 session 批改的题目
{questions}

## 学生答题情况 + grader 判分
{results}

# 输出要求

抽取以下 4 类 fact（**只抽真正暴露的，不要编造**）：

## 类别
- **weakness** (薄弱点)：反复错的知识点 / 概念混淆。例 "导数链式法则反复错（本 session 3 题中 2 题错）"
- **preference** (偏好)：解题习惯 / 学习方式。例 "倾向先看反例再推导"
- **progress** (进度)：已掌握的章节。例 "二次方程求根公式应用熟练"
- **goal** (目标)：学生明确说过的目标。例 "目标 A* / 准备 5 月考试"

## 严格 JSON 输出格式

```json
[
  {{
    "fact_type": "weakness|preference|progress|goal",
    "fact_text": "一句话描述（中文，含具体证据如'3 题中 2 题错'）",
    "topic": "知识点 slug（如 calculus.chain_rule、algebra.quadratic）或 null",
    "confidence": 0.0-1.0
  }},
  ...
]
```

**confidence 评分指南**：
- 1.0 = 单次 session 极强证据（如同一类型错 3+ 次）
- 0.8 = 强证据（错 2 次）
- 0.5 = 中等证据（错 1 次但概念明显混淆）
- 0.3 = 弱证据（间接暴露）
- < 0.3 不要输出

只输出 JSON 数组，不要其他解释文字。如果没有抽到任何 fact，输出 `[]`。
"""


def _format_questions(session_data: list[dict]) -> str:
    """把 session 数据格式化进 prompt"""
    lines = []
    for i, q in enumerate(session_data, 1):
        question = q.get("question_text", q.get("question", ""))[:200]
        lines.append(f"### Q{i}\n{question}")
    return "\n".join(lines) or "(空)"


def _format_results(session_data: list[dict]) -> str:
    """把每题的批改结果格式化"""
    lines = []
    for i, q in enumerate(session_data, 1):
        student_ans = q.get("student_answer", "")[:100]
        is_correct = q.get("is_correct")
        score = q.get("score", "?")
        feedback = q.get("student_feedback", q.get("feedback", ""))[:200]

        status = "✅ 对" if is_correct else "❌ 错" if is_correct is False else "?"
        lines.append(
            f"### Q{i}: {status} (得分 {score})\n"
            f"  学生答: {student_ans}\n"
            f"  反馈: {feedback}"
        )
    return "\n".join(lines) or "(空)"


def _parse_facts_json(
    raw: str,
    student_id: str,
    session_id: str | None,
) -> list[StudentFact]:
    """从 LLM 输出解析 fact list（容错 markdown code fence）"""
    # 容错：剥 markdown ```json fence
    raw = raw.strip()
    if raw.startswith("```"):
        # 去掉首行 ```json 和末行 ```
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        _log.warning("Fact extraction JSON parse failed: %s\nraw: %s", e, raw[:300])
        return []

    if not isinstance(items, list):
        _log.warning("Fact extraction returned non-list: %s", type(items))
        return []

    facts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            fact_type = FactType(item["fact_type"])
            fact_text = item["fact_text"]
            confidence = float(item.get("confidence", 0.5))
            if confidence < 0.3:
                continue  # 太低不要
        except (KeyError, ValueError) as e:
            _log.warning("Skipping invalid fact: %s (%s)", item, e)
            continue

        facts.append(
            StudentFact(
                student_id=student_id,
                fact_type=fact_type,
                fact_text=fact_text,
                topic=item.get("topic") or None,
                confidence=min(max(confidence, 0.0), 1.0),
                source_session_id=session_id,
            )
        )

    return facts


def extract_facts_from_session(
    student_id: str,
    session_id: str | None,
    session_data: list[dict],
    model_client: "ModelClient | None" = None,
) -> list[StudentFact]:
    """主入口：从 session 数据抽 fact。

    Parameters
    ----------
    student_id : str
        学生 ID
    session_id : str | None
        本次 session ID（追踪 fact 来源）
    session_data : list[dict]
        每个元素含：question_text / student_answer / is_correct / score / student_feedback
    model_client : ModelClient | None
        LLM client (extract 任务，建议用 explain 或 review role)
        如果是 None 返回空 list（fail-open，不让 Memory pipeline 阻塞主 grader）

    Returns
    -------
    list[StudentFact]
        confidence ≥ 0.3 的 fact list
    """
    if not session_data:
        return []
    if model_client is None:
        _log.info("No model_client passed, skip fact extraction")
        return []

    prompt = FACT_EXTRACTION_PROMPT.format(
        student_id=student_id,
        session_id=session_id or "(unknown)",
        questions=_format_questions(session_data),
        results=_format_results(session_data),
    )

    try:
        # 走 model_client.call() 拿到 LLM 输出
        # 假设 ModelRequest 接口签名（参考 router/models.py）
        from router.models import ModelRequest, TaskType

        req = ModelRequest(
            task=TaskType.classify,  # 复用 classify role，输出 JSON 短
            prompt=prompt,
            max_tokens=1024,
            temperature=0.0,
        )
        response = model_client.call(req)
        raw = response if isinstance(response, str) else getattr(response, "text", str(response))
    except Exception as e:
        _log.warning("Fact extraction LLM call failed: %s", e)
        return []

    facts = _parse_facts_json(raw, student_id, session_id)
    _log.info(
        "Extracted %d facts for student %s (session=%s)",
        len(facts), student_id, session_id,
    )
    return facts
