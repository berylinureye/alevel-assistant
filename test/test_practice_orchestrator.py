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
from questionbank.models import QuestionBankItem


def _bank_question(question_id: int, *, topic: str = "quadratics", paper_num: int = 1) -> QuestionBankItem:
    return QuestionBankItem(
        id=question_id,
        question_number=str(question_id),
        question_text=f"Question {question_id}",
        topic=topic,
        difficulty=3,
        paper_num=paper_num,
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


def test_query_recommendations_honors_count_six_with_default_slots(monkeypatch):
    class FakeConnection:
        def close(self):
            pass

    pools = {
        (1, 2): [_bank_question(1), _bank_question(2)],
        (3, 3): [_bank_question(3), _bank_question(4)],
        (4, 5): [_bank_question(5), _bank_question(6)],
    }

    def fake_get_random_questions(_conn, *, difficulty_min, difficulty_max, count, exclude_ids, **_kwargs):
        available = [
            question
            for question in pools[(difficulty_min, difficulty_max)]
            if question.id not in set(exclude_ids or [])
        ]
        return available[:count], len(available)

    import api.practice_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "ensure_db", lambda: FakeConnection())
    monkeypatch.setattr(orchestrator, "get_random_questions", fake_get_random_questions)
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="custom_homework",
            paper_num=None,
            match_confidence="medium",
            confirmed_by_user=True,
            grading_route="open_ai_grading",
        ),
        priority_topics=[{"topic": "Quadratics"}],
        count=6,
    )

    recommendations = orchestrator._query_recommendations(req, "quadratics")

    assert [rec.question_id for rec in recommendations] == [1, 3, 5, 2, 4, 6]


def test_query_recommendations_honors_adaptive_count(monkeypatch):
    class FakeConnection:
        def close(self):
            pass

    questions = [_bank_question(question_id) for question_id in range(10, 15)]

    def fake_get_random_questions(_conn, *, difficulty_min, difficulty_max, count, exclude_ids, **_kwargs):
        assert difficulty_min == 2
        assert difficulty_max == 4
        available = [question for question in questions if question.id not in set(exclude_ids or [])]
        return available[:count], len(available)

    import api.practice_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "ensure_db", lambda: FakeConnection())
    monkeypatch.setattr(orchestrator, "get_random_questions", fake_get_random_questions)
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="custom_homework",
            paper_num=None,
            match_confidence="medium",
            confirmed_by_user=True,
            grading_route="open_ai_grading",
        ),
        priority_topics=[{"topic": "Quadratics"}],
        preferred_difficulty_min=2,
        preferred_difficulty_max=4,
        count=4,
    )

    recommendations = orchestrator._query_recommendations(req, "quadratics")

    assert [rec.question_id for rec in recommendations] == [10, 11, 12, 13]
    assert all(rec.difficulty == "consolidation" for rec in recommendations)


def test_query_recommendations_scopes_confirmed_paper(monkeypatch):
    class FakeConnection:
        def close(self):
            pass

    paper_nums_seen: list[list[int] | None] = []

    def fake_get_random_questions(_conn, *, paper_nums, **_kwargs):
        paper_nums_seen.append(paper_nums)
        return [], 0

    import api.practice_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "ensure_db", lambda: FakeConnection())
    monkeypatch.setattr(orchestrator, "get_random_questions", fake_get_random_questions)
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="past_paper",
            paper_num=2,
            match_confidence="high",
            confirmed_by_user=True,
            grading_route="past_paper_mark_scheme",
        ),
        priority_topics=[{"topic": "Quadratics"}],
        count=1,
    )

    orchestrator._query_recommendations(req, "quadratics")

    assert paper_nums_seen
    assert all(paper_nums == [2] for paper_nums in paper_nums_seen)


def test_query_recommendations_accumulates_exclude_ids_between_calls(monkeypatch):
    class FakeConnection:
        def close(self):
            pass

    calls: list[list[int]] = []
    questions_by_call = [_bank_question(1), _bank_question(2), _bank_question(3)]

    def fake_get_random_questions(_conn, *, exclude_ids, **_kwargs):
        calls.append(list(exclude_ids or []))
        return [questions_by_call[len(calls) - 1]], 1

    import api.practice_orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "ensure_db", lambda: FakeConnection())
    monkeypatch.setattr(orchestrator, "get_random_questions", fake_get_random_questions)
    req = PracticeRecommendationRequest(
        context=PracticeRecommendationContext(
            upload_intent="custom_homework",
            paper_num=None,
            match_confidence="medium",
            confirmed_by_user=True,
            grading_route="open_ai_grading",
        ),
        priority_topics=[{"topic": "Quadratics"}],
        exclude_ids=[99],
        count=3,
    )

    recommendations = orchestrator._query_recommendations(req, "quadratics")

    assert [rec.question_id for rec in recommendations] == [1, 2, 3]
    assert calls == [[99], [99, 1], [99, 1, 2]]
