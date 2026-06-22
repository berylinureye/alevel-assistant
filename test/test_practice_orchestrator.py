from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.practice_orchestrator import (
    PracticeRecommendationContext,
    PracticeRecommendation,
    PracticeRecommendationRequest,
    choose_recommendation_mode,
    derive_candidate_topics,
    normalise_paper_num,
    recommend_practice,
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


def test_invalid_explicit_paper_never_uses_auto_mode():
    ctx = PracticeRecommendationContext(
        upload_intent="past_paper",
        paper_num=7,
        match_confidence="high",
        confirmed_by_user=True,
        grading_route="past_paper_mark_scheme",
        recommendation_mode="auto",
    )

    assert choose_recommendation_mode(ctx, has_topic=True, has_review_risk=False) == "none"


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


def test_invalid_explicit_paper_returns_boundary_message_without_query(monkeypatch):
    def fail_if_queried(_req, _topic):
        raise AssertionError("invalid explicit paper must not query unscoped recommendations")

    import api.practice_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "_query_recommendations", fail_if_queried)
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="past_paper",
            paper_num=7,
            match_confidence="high",
            confirmed_by_user=True,
            grading_route="past_paper_mark_scheme",
        ),
        priority_topics=[{"topic": "Quadratics"}],
    )

    response = asyncio.run(recommend_practice(req))

    assert response.recommendation_mode == "none"
    assert response.recommendations == []
    assert response.paper_num is None
    assert "P1-P6" in response.message


def test_auto_recommendations_fall_back_to_later_candidate_topic(monkeypatch):
    calls: list[str] = []

    def fake_query(_req, topic):
        calls.append(topic)
        if topic == "differentiation_p1":
            return [
                PracticeRecommendation(
                    id="foundation-42",
                    question_id=42,
                    topic="differentiation_p1",
                    difficulty="foundation",
                    title="基础修复",
                    reason="fallback topic had a real question",
                    trigger="auto",
                    paper_num=1,
                )
            ]
        return []

    import api.practice_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "_query_recommendations", fake_query)
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="past_paper",
            paper_num=1,
            match_confidence="high",
            confirmed_by_user=False,
            grading_route="past_paper_mark_scheme",
        ),
        priority_topics=[{"topic": "calculus"}],
        knowledge_tags_summary={"differentiation": 3},
    )

    response = asyncio.run(recommend_practice(req))

    assert calls == ["calculus", "differentiation_p1"]
    assert response.recommendation_mode == "auto"
    assert response.detected_topic == "differentiation_p1"
    assert response.recommendations[0].question_id == 42


def test_query_recommendations_does_not_unscope_invalid_confirmed_paper(monkeypatch):
    class FakeConnection:
        def close(self):
            pass

    def fail_if_random_questions_called(*_args, **_kwargs):
        raise AssertionError("invalid explicit paper must not become an unscoped DB query")

    import api.practice_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "ensure_db", lambda: FakeConnection())
    monkeypatch.setattr(orchestrator, "get_random_questions", fail_if_random_questions_called)
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="past_paper",
            paper_num=7,
            match_confidence="high",
            confirmed_by_user=True,
            grading_route="past_paper_mark_scheme",
        ),
        priority_topics=[{"topic": "Quadratics"}],
    )

    assert orchestrator._query_recommendations(req, "quadratics") == []
