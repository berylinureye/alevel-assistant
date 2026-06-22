from __future__ import annotations

import re
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from questionbank.database import ensure_db, get_random_questions
from questionbank.models import QuestionBankItem

PracticeRecommendationMode = Literal["auto", "ask_first", "none"]
PracticeUploadIntent = Literal[
    "past_paper",
    "custom_homework",
    "unknown",
    "full_past_paper_pdf",
    "partial_past_paper_pages",
    "answer_pages_only",
    "single_question_photo",
]

SUPPORTED_PAPERS = {1, 2, 3, 4, 5, 6}

TOPIC_ALIASES: dict[str, str] = {
    "quadratic": "quadratics",
    "quadratics": "quadratics",
    "quadratic equations": "quadratics",
    "function": "functions",
    "functions": "functions",
    "coordinate geometry": "coordinate_geometry",
    "circle": "coordinate_geometry",
    "circular measure": "circular_measure",
    "trigonometry": "trigonometry_p1",
    "trig": "trigonometry_p1",
    "series": "series",
    "sequence": "series",
    "differentiation": "differentiation_p1",
    "derivative": "differentiation_p1",
    "integration": "integration_p1",
    "integral": "integration_p1",
    "normal distribution": "normal_distribution",
    "probability": "probability",
    "kinematics": "kinematics",
    "forces": "forces_and_equilibrium",
    "complex numbers": "complex_numbers",
}

BROAD_TOPIC_BY_PAPER: dict[str, dict[int, str]] = {
    "trigonometry": {1: "trigonometry_p1", 2: "trigonometry_p2", 3: "trigonometry_p3"},
    "differentiation": {1: "differentiation_p1", 2: "differentiation_p2", 3: "differentiation_p3"},
    "integration": {1: "integration_p1", 2: "integration_p2", 3: "integration_p3"},
}


class PracticeRecommendationContext(BaseModel):
    upload_intent: PracticeUploadIntent = "unknown"
    paper_num: Optional[int] = None
    question_number: Optional[str] = None
    match_confidence: Optional[Literal["high", "medium", "low"]] = None
    confirmed_by_user: bool = False
    grading_route: Optional[Literal["past_paper_mark_scheme", "open_ai_grading"]] = None
    recommendation_mode: Optional[PracticeRecommendationMode] = None


class PracticeSourceQuestion(BaseModel):
    question_number: str
    score: float = 0
    full_score: float = 0
    is_correct: bool = False
    unanswered: bool = False
    error_type: Optional[str] = None
    knowledge_tags: list[str] = Field(default_factory=list)
    needs_review: bool = False


class PracticeRecommendationRequest(BaseModel):
    context: PracticeRecommendationContext
    priority_topics: list[dict] = Field(default_factory=list)
    knowledge_tags_summary: dict[str, int] = Field(default_factory=dict)
    questions: list[PracticeSourceQuestion] = Field(default_factory=list)
    exclude_ids: list[int] = Field(default_factory=list)
    preferred_difficulty_min: Optional[int] = Field(default=None, ge=1, le=5)
    preferred_difficulty_max: Optional[int] = Field(default=None, ge=1, le=5)
    count: int = Field(default=3, ge=1, le=6)


class PracticeRecommendation(BaseModel):
    id: str
    question_id: Optional[int]
    topic: str
    subtopic: Optional[str] = None
    difficulty: Literal["foundation", "consolidation", "exam-style"]
    title: str
    reason: str
    source_label: Optional[str] = None
    unavailable: bool = False
    trigger: Literal["auto", "ask_first", "unavailable"]
    paper_num: Optional[int] = None
    requires_confirmation: bool = False
    question: Optional[QuestionBankItem] = None


class PracticeRecommendationResponse(BaseModel):
    status: str = "success"
    recommendation_mode: PracticeRecommendationMode
    message: str
    detected_topic: Optional[str] = None
    detected_subtopic: Optional[str] = None
    paper_num: Optional[int] = None
    match_confidence: Optional[Literal["high", "medium", "low"]] = None
    recommendations: list[PracticeRecommendation] = Field(default_factory=list)


practice_orchestrator_router = APIRouter(
    prefix="/practice-orchestrator",
    tags=["practice-orchestrator"],
)


def normalise_paper_num(value: Optional[int]) -> Optional[int]:
    if value in SUPPORTED_PAPERS:
        return value
    return None


def _has_invalid_explicit_paper(value: Optional[int]) -> bool:
    return value is not None and normalise_paper_num(value) is None


def _normalise_topic_key(value: object, paper_num: Optional[int]) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    lower = re.sub(r"[_-]+", " ", text.lower())
    lower = re.sub(r"\s+", " ", lower).strip()
    if lower in BROAD_TOPIC_BY_PAPER and paper_num in BROAD_TOPIC_BY_PAPER[lower]:
        return BROAD_TOPIC_BY_PAPER[lower][paper_num]
    if lower in TOPIC_ALIASES:
        return TOPIC_ALIASES[lower]
    snake = lower.replace(" ", "_")
    if snake:
        return snake
    return None


def derive_candidate_topics(req: PracticeRecommendationRequest) -> list[str]:
    paper_num = normalise_paper_num(req.context.paper_num)
    ordered: list[str] = []

    for item in req.priority_topics:
        for key in ("topic", "subtopic", "chapter"):
            topic = _normalise_topic_key(item.get(key), paper_num)
            if topic and topic not in ordered:
                ordered.append(topic)

    for key, _count in sorted(req.knowledge_tags_summary.items(), key=lambda kv: kv[1], reverse=True):
        topic = _normalise_topic_key(key, paper_num)
        if topic and topic not in ordered:
            ordered.append(topic)

    for question in req.questions:
        if question.is_correct:
            continue
        for tag in question.knowledge_tags:
            topic = _normalise_topic_key(tag, paper_num)
            if topic and topic not in ordered:
                ordered.append(topic)
        topic = _normalise_topic_key(question.error_type, paper_num)
        if topic and topic not in ordered:
            ordered.append(topic)

    return ordered


def choose_recommendation_mode(
    context: PracticeRecommendationContext,
    *,
    has_topic: bool,
    has_review_risk: bool,
) -> PracticeRecommendationMode:
    if _has_invalid_explicit_paper(context.paper_num):
        return "none"
    if context.recommendation_mode in {"auto", "ask_first", "none"}:
        return context.recommendation_mode
    if not has_topic:
        return "none"
    if has_review_risk and not context.confirmed_by_user:
        return "ask_first"
    if context.confirmed_by_user:
        return "auto"
    if context.grading_route == "past_paper_mark_scheme":
        return "auto"
    if context.upload_intent in {"past_paper", "full_past_paper_pdf", "partial_past_paper_pages"}:
        return "auto" if context.match_confidence == "high" else "ask_first"
    if context.upload_intent in {"single_question_photo", "custom_homework", "unknown", "answer_pages_only"}:
        return "ask_first"
    return "none"


def _difficulty_slots(req: PracticeRecommendationRequest) -> list[tuple[str, str, int, int]]:
    if req.preferred_difficulty_min and req.preferred_difficulty_max:
        return [("adaptive", "下一题", req.preferred_difficulty_min, req.preferred_difficulty_max)]
    return [
        ("foundation", "基础修复", 1, 2),
        ("consolidation", "巩固练习", 3, 3),
        ("exam-style", "真题风格", 4, 5),
    ]


def _reason_for_slot(title: str, topic: str, scoped_to_paper: bool) -> str:
    scope = "同一套 paper 范围内" if scoped_to_paper else "按题型"
    if title == "基础修复":
        return f"本次暴露出 {topic} 的薄弱点，先用{scope}的低难度题补稳。"
    if title == "巩固练习":
        return f"继续练 {topic}，检查是否能独立完成完整步骤。"
    if title == "真题风格":
        return f"用更接近考试难度的题确认 {topic} 是否真的掌握。"
    return f"根据刚刚的作答结果，继续练 {topic}。"


def _append_recommendations(
    recommendations: list[PracticeRecommendation],
    *,
    questions: list[QuestionBankItem],
    req_count: int,
    slot: str,
    title: str,
    topic: str,
    scoped_to_paper: bool,
    exclude_ids: list[int],
    selected_ids: set[int],
) -> None:
    for question in questions:
        if len(recommendations) >= req_count:
            break
        if question.id is not None:
            if question.id in selected_ids:
                continue
            selected_ids.add(question.id)
            exclude_ids.append(question.id)
        recommendations.append(
            PracticeRecommendation(
                id=f"{slot}-{question.id}",
                question_id=question.id,
                topic=question.topic,
                subtopic=question.subtopic,
                difficulty=slot if slot in {"foundation", "consolidation", "exam-style"} else "consolidation",
                title=title,
                reason=_reason_for_slot(title, topic, scoped_to_paper),
                source_label="同 paper · 同 topic" if scoped_to_paper else "同 topic · 题库匹配",
                trigger="auto",
                paper_num=question.paper_num,
                requires_confirmation=False,
                question=question,
            )
        )


def _query_recommendations(req: PracticeRecommendationRequest, topic: str) -> list[PracticeRecommendation]:
    if _has_invalid_explicit_paper(req.context.paper_num):
        return []

    paper_num = normalise_paper_num(req.context.paper_num)
    scoped_to_paper = paper_num is not None and (
        req.context.confirmed_by_user
        or req.context.grading_route == "past_paper_mark_scheme"
        or req.context.upload_intent in {"past_paper", "full_past_paper_pdf", "partial_past_paper_pages"}
    )
    paper_nums = [paper_num] if scoped_to_paper and paper_num else None
    exclude_ids = list(req.exclude_ids)
    selected_ids = set(exclude_ids)
    recommendations: list[PracticeRecommendation] = []
    slots = _difficulty_slots(req)

    conn = ensure_db()
    try:
        if req.preferred_difficulty_min and req.preferred_difficulty_max:
            slot, title, difficulty_min, difficulty_max = slots[0]
            questions, _total = get_random_questions(
                conn,
                topics=[topic],
                difficulty_min=difficulty_min,
                difficulty_max=difficulty_max,
                count=req.count,
                paper_nums=paper_nums,
                exclude_ids=exclude_ids,
            )
            _append_recommendations(
                recommendations,
                questions=questions,
                req_count=req.count,
                slot=slot,
                title=title,
                topic=topic,
                scoped_to_paper=scoped_to_paper,
                exclude_ids=exclude_ids,
                selected_ids=selected_ids,
            )
            return recommendations

        while len(recommendations) < req.count:
            added_this_round = False
            for slot, title, difficulty_min, difficulty_max in slots:
                if len(recommendations) >= req.count:
                    break
                before_count = len(recommendations)
                questions, _total = get_random_questions(
                    conn,
                    topics=[topic],
                    difficulty_min=difficulty_min,
                    difficulty_max=difficulty_max,
                    count=1,
                    paper_nums=paper_nums,
                    exclude_ids=exclude_ids,
                )
                _append_recommendations(
                    recommendations,
                    questions=questions,
                    req_count=req.count,
                    slot=slot,
                    title=title,
                    topic=topic,
                    scoped_to_paper=scoped_to_paper,
                    exclude_ids=exclude_ids,
                    selected_ids=selected_ids,
                )
                added_this_round = added_this_round or len(recommendations) > before_count
            if not added_this_round:
                break
    finally:
        conn.close()

    return recommendations


@practice_orchestrator_router.post("/recommendations", response_model=PracticeRecommendationResponse)
async def recommend_practice(req: PracticeRecommendationRequest) -> PracticeRecommendationResponse:
    topics = derive_candidate_topics(req)
    topic = topics[0] if topics else None
    has_review_risk = any(q.needs_review for q in req.questions)
    paper_num = normalise_paper_num(req.context.paper_num)
    if _has_invalid_explicit_paper(req.context.paper_num):
        return PracticeRecommendationResponse(
            recommendation_mode="none",
            message="当前推荐题库只支持 P1-P6。请确认 paper number 后再生成同 paper 练习。",
            detected_topic=topic,
            paper_num=None,
            match_confidence=req.context.match_confidence,
            recommendations=[],
        )

    mode = choose_recommendation_mode(req.context, has_topic=topic is not None, has_review_risk=has_review_risk)

    if mode == "none" or topic is None:
        return PracticeRecommendationResponse(
            recommendation_mode="none",
            message="这次我还不能可靠地为你匹配练习题。建议先确认题目来源，或上传 Past Paper 封面/题目页。",
            detected_topic=topic,
            paper_num=paper_num,
            match_confidence=req.context.match_confidence,
            recommendations=[],
        )

    if mode == "ask_first":
        label = f"P{paper_num} " if paper_num else ""
        return PracticeRecommendationResponse(
            recommendation_mode="ask_first",
            message=f"我检测到这题像是 {label}{topic}。要不要再做 2-3 道类似题来确认这个点？",
            detected_topic=topic,
            paper_num=paper_num,
            match_confidence=req.context.match_confidence,
            recommendations=[],
        )

    recommendations: list[PracticeRecommendation] = []
    recommended_topic: Optional[str] = None
    selected_ids = set(req.exclude_ids)
    exclude_ids = list(req.exclude_ids)
    for candidate_topic in topics:
        if len(recommendations) >= req.count:
            break
        topic_req = req.model_copy(
            update={
                "exclude_ids": exclude_ids,
                "count": req.count - len(recommendations),
            }
        )
        topic_recommendations = await run_in_threadpool(_query_recommendations, topic_req, candidate_topic)
        for recommendation in topic_recommendations:
            if len(recommendations) >= req.count:
                break
            if recommendation.question_id is not None:
                if recommendation.question_id in selected_ids:
                    continue
                selected_ids.add(recommendation.question_id)
                exclude_ids.append(recommendation.question_id)
            recommendations.append(recommendation)
            if recommended_topic is None:
                recommended_topic = candidate_topic

    if not recommendations:
        return PracticeRecommendationResponse(
            recommendation_mode="none",
            message=f"我找到了薄弱点 {topic}，但当前题库没有可用的真实候选题。",
            detected_topic=topic,
            paper_num=paper_num,
            match_confidence=req.context.match_confidence,
            recommendations=[],
        )

    return PracticeRecommendationResponse(
        recommendation_mode="auto",
        message="已根据本次批改结果推荐真实题库练习。",
        detected_topic=recommended_topic or topic,
        paper_num=paper_num,
        match_confidence=req.context.match_confidence,
        recommendations=recommendations[: req.count],
    )
