from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api.paper_resolver as paper_resolver
from api.paper_resolver import build_user_hint_with_resolution, resolve_paper_context


def test_manual_paper_code_exact_catalog_match() -> None:
    result = resolve_paper_context(
        upload_intent="past_paper",
        paper_code="9709/12/M/J/16",
        question_numbers="3, 4",
        page_count=2,
    )

    assert result.upload_intent == "past_paper"
    assert result.paper_id == "9709_s16_12"
    assert result.question_numbers == ["3", "4"]
    assert result.match_confidence == "high"
    assert result.match_source == "manual"
    assert result.grading_route == "past_paper_mark_scheme"
    assert result.needs_user_confirmation is False
    assert result.catalog_match is not None
    assert result.catalog_match["has_ms"] is True


def test_external_resolution_detail_and_user_hint_do_not_leak_local_paths() -> None:
    result = resolve_paper_context(
        upload_intent="past_paper",
        paper_code="9709/12/M/J/16",
        question_numbers="1",
        page_count=1,
    )

    detail = result.event_detail()
    catalog_detail = detail["catalog_match"]
    assert catalog_detail is not None
    assert "qp_path" not in catalog_detail
    assert "ms_path" not in catalog_detail

    hint = build_user_hint_with_resolution("", result)
    assert "data/papers" not in hint
    assert "local_question_paper" not in hint
    assert "local_mark_scheme" not in hint

    pipeline_context = result.pipeline_context()
    assert pipeline_context["catalog_match"]["qp_path"]
    assert pipeline_context["catalog_match"]["ms_path"]


def test_past_paper_without_code_needs_context() -> None:
    result = resolve_paper_context(
        upload_intent="past_paper",
        paper_code="",
        question_numbers="",
        page_count=4,
    )

    assert result.match_confidence == "low"
    assert result.match_source == "none"
    assert result.grading_route == "open_ai_grading"
    assert result.needs_user_confirmation is True
    assert "paper code" in result.summary.lower()


def test_custom_homework_routes_to_open_grading() -> None:
    result = resolve_paper_context(
        upload_intent="custom_homework",
        paper_code="9709/12/M/J/16",
        question_numbers="",
        page_count=1,
    )

    assert result.upload_intent == "custom_homework"
    assert result.match_confidence == "low"
    assert result.match_source == "none"
    assert result.grading_route == "open_ai_grading"
    assert result.paper_id is None
    assert result.needs_user_confirmation is False


def test_manual_paper_code_missing_mark_scheme_file_falls_back(monkeypatch) -> None:
    def fake_catalog_match(parsed):
        return {
            "subject": parsed.subject,
            "year": parsed.year,
            "session": parsed.session,
            "paper_num": parsed.paper_num,
            "variant": parsed.variant,
            "paper_name": "Pure Mathematics 1",
            "level": "AS",
            "component": "pure_math",
            "topics": "quadratics",
            "has_qp": True,
            "has_ms": True,
            "qp_path": "data/papers/9709/2016/9709_s16_qp_12.pdf",
            "ms_path": "data/papers/9709/2016/does-not-exist.pdf",
        }

    monkeypatch.setattr(paper_resolver, "_find_catalog_match", fake_catalog_match)

    result = resolve_paper_context(
        upload_intent="past_paper",
        paper_code="9709/12/M/J/16",
        question_numbers="1",
        page_count=1,
    )

    assert result.paper_id == "9709_s16_12"
    assert result.match_confidence == "medium"
    assert result.grading_route == "open_ai_grading"
    assert result.needs_user_confirmation is True
    assert "mark scheme" in result.summary.lower()
    assert "data/papers" not in result.summary
    assert "does-not-exist.pdf" not in result.summary


def test_manual_paper_code_missing_question_paper_file_falls_back(monkeypatch) -> None:
    def fake_catalog_match(parsed):
        return {
            "subject": parsed.subject,
            "year": parsed.year,
            "session": parsed.session,
            "paper_num": parsed.paper_num,
            "variant": parsed.variant,
            "paper_name": "Pure Mathematics 1",
            "level": "AS",
            "component": "pure_math",
            "topics": "quadratics",
            "has_qp": True,
            "has_ms": True,
            "qp_path": "data/papers/9709/2016/does-not-exist.pdf",
            "ms_path": "data/papers/9709/2016/9709_s16_ms_12.pdf",
        }

    monkeypatch.setattr(paper_resolver, "_find_catalog_match", fake_catalog_match)

    result = resolve_paper_context(
        upload_intent="past_paper",
        paper_code="9709/12/M/J/16",
        question_numbers="1",
        page_count=1,
    )

    assert result.paper_id == "9709_s16_12"
    assert result.match_confidence == "medium"
    assert result.grading_route == "open_ai_grading"
    assert result.needs_user_confirmation is True
    assert "question paper" in result.summary.lower()
    assert "data/papers" not in result.summary
    assert "does-not-exist.pdf" not in result.summary
