"""
Summarizer：List[GradeResult] + List[QuestionFeedback] → PageSummary

统计字段全部由 Python 规则计算，不依赖 LLM。
overall_teacher_comment 由 LLM 生成，失败时降级为保守文案，不抛异常。
"""
from __future__ import annotations

import json
from collections import Counter

from models.schemas import GradeResult, PageSummary, QuestionFeedback
from router.models import ModelClient, ModelRequest, TaskType

# ---------------------------------------------------------------------------
# 统计规则常量
# ---------------------------------------------------------------------------
EXCLUDED_ERROR_TYPES = {"", "correct", "unknown"}

FALLBACK_COMMENT = "自动评语生成失败，请参考上方统计数据了解学生表现。"

_COMMENT_PROMPT = """\
You are writing a brief teacher comment for an A-Level math homework page.

Statistics:
{stats}

Write an overall_teacher_comment (max 100 words) that:
- identifies the main strength (if any)
- identifies the main weakness or error pattern
- gives one specific, actionable teaching recommendation

Formatting:
- Wrap mathematical expressions in $...$ (LaTeX). Do not wrap ordinary English sentences in $...$.

Tone: professional, for a teacher audience.
Return ONLY the comment text — no JSON, no markdown, no labels.
"""

# ---------------------------------------------------------------------------
# 统计计算（纯 Python，确定性）
# ---------------------------------------------------------------------------

def compute_common_error_types(grades: list[GradeResult]) -> list[str]:
    normalized = [(g.error_type or "").lower().strip() for g in grades]
    filtered   = [e for e in normalized if e not in EXCLUDED_ERROR_TYPES]
    counts     = Counter(filtered)
    return [et for et, cnt in counts.most_common() if cnt >= 2]


def compute_knowledge_tags_summary(grades: list[GradeResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for g in grades:
        for tag in (g.knowledge_tags or []):
            key = tag.lower().strip().replace(" ", "_")
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def _compute_stats(grades: list[GradeResult]) -> dict:
    # pending_review：图表题或低置信度安全网结果，既非对也非错，不计入对错分子分母
    def _is_pending(g: GradeResult) -> bool:
        return (g.error_type or "") == "pending_review"
    unanswered_count = sum(1 for g in grades if g.unanswered)
    correct_count    = sum(1 for g in grades if g.is_correct and not _is_pending(g))
    incorrect_count  = sum(
        1 for g in grades if not g.is_correct and not g.unanswered and not _is_pending(g)
    )
    result = {
        "total_questions"        : len(grades),
        "correct_count"          : correct_count,
        "incorrect_count"        : incorrect_count,
        "unanswered_count"       : unanswered_count,
        "review_count"           : sum(1 for g in grades if g.needs_review),
        "score_total"            : round(sum(g.score for g in grades), 2),
        "full_score_total"       : round(sum(g.full_score for g in grades), 2),
        "common_error_types"     : compute_common_error_types(grades),
        "knowledge_tags_summary" : compute_knowledge_tags_summary(grades),
        "estimated_review_minutes": compute_estimated_review_minutes(grades),
        "priority_topics"        : compute_priority_topics(grades),
    }
    return result


def compute_estimated_review_minutes(grades: list[GradeResult]) -> int:
    """
    Heuristic: each incorrect question ~5 min review,
    each unique weak topic ~3 min extra, minimum 10 min if any errors.
    """
    incorrect = [g for g in grades if not g.is_correct]
    if not incorrect:
        return 0
    base_time = len(incorrect) * 5
    unique_error_types = set(
        (g.error_type or "").lower().strip()
        for g in incorrect
        if (g.error_type or "").lower().strip() not in EXCLUDED_ERROR_TYPES
    )
    unique_topics = set()
    for g in incorrect:
        for t in (g.syllabus_topics or []):
            if not isinstance(t, dict):
                continue
            subtopic = t.get("subtopic", "")
            if subtopic:
                unique_topics.add(subtopic.lower())
    extra_time = len(unique_error_types) * 5 + len(unique_topics) * 3
    return max(10, base_time + extra_time)


def compute_priority_topics(grades: list[GradeResult]) -> list[dict]:
    """
    聚合错题的 syllabus_topics，按出现频次排序。
    关键公式来自本地静态公式库（formatter.topic_formulas），
    不再直接使用学生题面抽取的 relevant_formulas，避免带入具体数字 / 噪声。
    """
    from formatter.topic_formulas import lookup_formulas

    topic_counts: dict[str, dict] = {}
    for g in grades:
        if g.is_correct:
            continue
        for t in (g.syllabus_topics or []):
            if not isinstance(t, dict):
                continue
            key = t.get("subtopic", t.get("topic", "unknown"))
            if key not in topic_counts:
                topic_counts[key] = {
                    "topic": t.get("topic", ""),
                    "subtopic": t.get("subtopic", ""),
                    "chapter": t.get("chapter", ""),
                    "error_count": 0,
                }
            topic_counts[key]["error_count"] += 1

    result = []
    for info in sorted(topic_counts.values(), key=lambda x: x["error_count"], reverse=True):
        formulas = lookup_formulas(
            subtopic=info["subtopic"],
            topic=info["topic"],
            chapter=info["chapter"],
        )
        result.append({
            "topic": info["topic"],
            "subtopic": info["subtopic"],
            "chapter": info["chapter"],
            "error_count": info["error_count"],
            "key_formulas": formulas[:3],
        })
    return result


# ---------------------------------------------------------------------------
# LLM comment 生成
# ---------------------------------------------------------------------------

def _generate_comment(
    stats: dict,
    client: ModelClient,
    max_retries: int,
) -> str:
    prompt  = _COMMENT_PROMPT.format(stats=json.dumps(stats, ensure_ascii=False, indent=2))
    request = ModelRequest(task=TaskType.review, prompt=prompt, max_tokens=256)

    for attempt in range(max_retries + 1):
        try:
            return client.call(request).strip()
        except Exception:
            if attempt == max_retries:
                return FALLBACK_COMMENT
    return FALLBACK_COMMENT


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_summary(
    grades: list[GradeResult],
    feedbacks: list[QuestionFeedback],   # 保留参数，供后续分析 feedback 模式
    client: ModelClient,
    max_retries: int = 1,
    generate_comment: bool = False,
) -> PageSummary:
    stats = _compute_stats(grades)
    if generate_comment:
        comment = _generate_comment(stats, client, max_retries)
    else:
        incorrect = stats["incorrect_count"]
        unanswered = stats.get("unanswered_count", 0)
        total = stats["total_questions"]
        if incorrect == 0 and unanswered == 0:
            comment = f"全部 {total} 道题均答对，表现优秀。"
        else:
            parts = []
            if incorrect > 0:
                parts.append(f"{incorrect} 道答错")
            if unanswered > 0:
                parts.append(f"{unanswered} 道未作答")
            error_types = stats.get("common_error_types", [])
            pattern = f" 常见错误类型：{'、'.join(error_types)}。" if error_types else ""
            comment = f"共 {total} 道题中有{'、'.join(parts)}。{pattern} 请查看各题反馈了解详情。"
    return PageSummary(**stats, overall_teacher_comment=comment)
