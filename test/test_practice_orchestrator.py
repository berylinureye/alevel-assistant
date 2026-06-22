from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.practice_orchestrator import (
    PracticeRecommendationContext,
    PracticeRecommendationRequest,
    choose_recommendation_mode,
    derive_candidate_topics,
    normalise_paper_num,
)


def test_confirmed_past_paper_uses_auto_mode():
    ctx = PracticeRecommendationContext(
        upload_intent="past_paper",
        paper_num=1,
        match_confidence="high",
        confirmed_by_user=False,
        grading_route="past_paper_mark_scheme",
    )

    assert choose_recommendation_mode(ctx, has_topic=True, has_review_risk=False) == "auto"


def test_single_question_photo_asks_first():
    ctx = PracticeRecommendationContext(
        upload_intent="single_question_photo",
        paper_num=5,
        match_confidence="medium",
        confirmed_by_user=False,
        grading_route="open_ai_grading",
    )

    assert choose_recommendation_mode(ctx, has_topic=True, has_review_risk=False) == "ask_first"


def test_confirmed_single_question_can_fetch_questions():
    ctx = PracticeRecommendationContext(
        upload_intent="single_question_photo",
        paper_num=5,
        match_confidence="medium",
        confirmed_by_user=True,
        grading_route="open_ai_grading",
    )

    assert choose_recommendation_mode(ctx, has_topic=True, has_review_risk=False) == "auto"


def test_low_confidence_without_topic_returns_none():
    ctx = PracticeRecommendationContext(
        upload_intent="unknown",
        paper_num=None,
        match_confidence="low",
        confirmed_by_user=False,
        grading_route="open_ai_grading",
    )

    assert choose_recommendation_mode(ctx, has_topic=False, has_review_risk=False) == "none"


def test_paper_num_is_limited_to_p1_to_p6():
    assert normalise_paper_num(1) == 1
    assert normalise_paper_num(6) == 6
    assert normalise_paper_num(7) is None
    assert normalise_paper_num(None) is None


def test_derives_topic_from_priority_topic_first():
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="past_paper",
            paper_num=1,
            match_confidence="high",
            confirmed_by_user=False,
            grading_route="past_paper_mark_scheme",
        ),
        priority_topics=[{"topic": "Quadratics", "subtopic": "quadratic equations"}],
        knowledge_tags_summary={"differentiation": 3},
        questions=[],
        exclude_ids=[],
    )

    topics = derive_candidate_topics(req)

    assert topics[0] == "quadratics"
