from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from questionbank.mark_scheme import resolve_paper_asset_paths

UploadIntent = Literal[
    "past_paper",
    "custom_homework",
    "unknown",
    "full_past_paper_pdf",
    "partial_past_paper_pages",
    "answer_pages_only",
]
MatchConfidence = Literal["high", "medium", "low"]
MatchSource = Literal["cover", "page_header", "question_text", "manual", "none"]
GradingRoute = Literal["past_paper_mark_scheme", "open_ai_grading"]

CATALOG_PATH = Path("data/papers_catalog.csv")

_KNOWN_INTENTS = {
    "past_paper",
    "custom_homework",
    "unknown",
    "full_past_paper_pdf",
    "partial_past_paper_pages",
    "answer_pages_only",
}

_SESSION_DISPLAY = {
    "m": "Feb/Mar",
    "s": "May/Jun",
    "w": "Oct/Nov",
}


@dataclass(frozen=True)
class ParsedPaperCode:
    subject: str
    year: int
    session: str
    paper_num: int
    variant: int

    @property
    def component(self) -> str:
        return f"{self.paper_num}{self.variant}"

    @property
    def paper_id(self) -> str:
        return f"{self.subject}_{self.session}{self.year % 100:02d}_{self.component}"

    @property
    def label(self) -> str:
        session = _SESSION_DISPLAY.get(self.session, self.session.upper())
        return f"CIE {self.subject}/{self.component} {session} {self.year}"


@dataclass(frozen=True)
class PaperResolution:
    upload_intent: UploadIntent
    paper_code_raw: str | None
    question_numbers: list[str]
    page_count: int
    paper_id: str | None
    paper_label: str | None
    match_confidence: MatchConfidence
    match_source: MatchSource
    grading_route: GradingRoute
    needs_user_confirmation: bool
    summary: str
    catalog_match: dict | None = None

    def _public_catalog_match(self) -> dict | None:
        if not self.catalog_match:
            return None
        return {
            key: value
            for key, value in self.catalog_match.items()
            if key not in {"qp_path", "ms_path"}
        }

    def event_detail(self) -> dict:
        return {
            "upload_intent": self.upload_intent,
            "paper_code": self.paper_code_raw,
            "question_numbers": self.question_numbers,
            "paper_id": self.paper_id,
            "paper_label": self.paper_label,
            "match_confidence": self.match_confidence,
            "match_source": self.match_source,
            "grading_route": self.grading_route,
            "needs_user_confirmation": self.needs_user_confirmation,
            "catalog_match": self._public_catalog_match(),
        }

    def pipeline_context(self) -> dict:
        return {
            **self.event_detail(),
            "catalog_match": self.catalog_match,
        }


def _normalise_intent(value: str | None) -> UploadIntent:
    raw = (value or "unknown").strip()
    return raw if raw in _KNOWN_INTENTS else "unknown"  # type: ignore[return-value]


def _normalise_session(raw: str) -> str | None:
    clean = re.sub(r"[^a-z]", "", raw.lower())
    if clean in {"m", "fm", "febmar"}:
        return "m"
    if clean in {"s", "mj", "mayjun", "june"}:
        return "s"
    if clean in {"w", "on", "octnov", "nov"}:
        return "w"
    return None


def _normalise_year(raw: str) -> int:
    value = int(raw)
    if value < 100:
        return 2000 + value
    return value


def parse_paper_code(value: str | None) -> ParsedPaperCode | None:
    text = (value or "").strip()
    if not text:
        return None

    patterns = [
        # 9709/12/M/J/16, 9709 12 MJ 2016
        re.compile(
            r"(?P<subject>\d{4})\D*(?P<component>[1-6][1-3])\D*"
            r"(?P<session>m\s*/?\s*j|o\s*/?\s*n|f\s*/?\s*m|[msw])\D*"
            r"(?P<year>\d{2,4})",
            re.IGNORECASE,
        ),
        # 9709_s16_qp_12.pdf, 9709-s16-ms-12
        re.compile(
            r"(?P<subject>\d{4})\D*(?P<session>[msw])(?P<year>\d{2})\D*"
            r"(?:qp|ms)?\D*(?P<component>[1-6][1-3])",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            continue
        session = _normalise_session(match.group("session"))
        if session is None:
            continue
        component = match.group("component")
        return ParsedPaperCode(
            subject=match.group("subject"),
            year=_normalise_year(match.group("year")),
            session=session,
            paper_num=int(component[0]),
            variant=int(component[1]),
        )

    return None


def _parse_question_numbers(value: str | None) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []
    return [
        part.strip()
        for part in re.split(r"[,，;\s]+", raw)
        if part.strip()
    ]


@lru_cache(maxsize=1)
def _load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    with CATALOG_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _bool_cell(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _find_catalog_match(parsed: ParsedPaperCode) -> dict | None:
    for row in _load_catalog():
        try:
            if (
                str(row.get("subject", "")).strip() == parsed.subject
                and int(row.get("year", 0)) == parsed.year
                and str(row.get("session", "")).strip().lower() == parsed.session
                and int(row.get("paper_num", 0)) == parsed.paper_num
                and int(row.get("variant", 0)) == parsed.variant
            ):
                return {
                    "subject": parsed.subject,
                    "year": parsed.year,
                    "session": parsed.session,
                    "paper_num": parsed.paper_num,
                    "variant": parsed.variant,
                    "paper_name": row.get("paper_name"),
                    "level": row.get("level"),
                    "component": row.get("component"),
                    "topics": row.get("topics"),
                    "has_qp": _bool_cell(row.get("has_qp")),
                    "has_ms": _bool_cell(row.get("has_ms")),
                    "qp_path": row.get("qp_path"),
                    "ms_path": row.get("ms_path"),
                }
        except (TypeError, ValueError):
            continue
    return None


def resolve_paper_context(
    *,
    upload_intent: str | None,
    paper_code: str | None,
    question_numbers: str | None,
    page_count: int,
) -> PaperResolution:
    intent = _normalise_intent(upload_intent)
    qnums = _parse_question_numbers(question_numbers)
    raw_code = (paper_code or "").strip() or None

    if intent == "custom_homework":
        return PaperResolution(
            upload_intent=intent,
            paper_code_raw=None,
            question_numbers=[],
            page_count=page_count,
            paper_id=None,
            paper_label=None,
            match_confidence="low",
            match_source="none",
            grading_route="open_ai_grading",
            needs_user_confirmation=False,
            summary="这是老师自定义作业，将使用开放 AI 批改模式。",
        )

    parsed = parse_paper_code(raw_code)
    if parsed is not None:
        catalog_match = _find_catalog_match(parsed)
        assets = resolve_paper_asset_paths(catalog_match)
        if catalog_match and catalog_match.get("has_ms") and assets.available:
            suffix = f"；本次优先批改 {', '.join(qnums)}" if qnums else ""
            return PaperResolution(
                upload_intent=intent,
                paper_code_raw=raw_code,
                question_numbers=qnums,
                page_count=page_count,
                paper_id=parsed.paper_id,
                paper_label=parsed.label,
                match_confidence="high",
                match_source="manual",
                grading_route="past_paper_mark_scheme",
                needs_user_confirmation=False,
                summary=f"已匹配到本地 Past Paper 和 mark scheme：{parsed.label}{suffix}。",
                catalog_match=catalog_match,
            )
        if catalog_match and catalog_match.get("has_ms") and not assets.available:
            return PaperResolution(
                upload_intent=intent,
                paper_code_raw=raw_code,
                question_numbers=qnums,
                page_count=page_count,
                paper_id=parsed.paper_id,
                paper_label=parsed.label,
                match_confidence="medium",
                match_source="manual",
                grading_route="open_ai_grading",
                needs_user_confirmation=True,
                summary=f"识别到 {parsed.label}，但本地 mark scheme 文件不可用：{assets.reason} 本次先使用开放 AI 批改。",
                catalog_match=catalog_match,
            )
        return PaperResolution(
            upload_intent=intent,
            paper_code_raw=raw_code,
            question_numbers=qnums,
            page_count=page_count,
            paper_id=parsed.paper_id,
            paper_label=parsed.label,
            match_confidence="medium",
            match_source="manual",
            grading_route="open_ai_grading",
            needs_user_confirmation=True,
            summary=f"识别到 {parsed.label}，但本地题库暂未找到对应 mark scheme，将先作为上下文进入开放批改。",
            catalog_match=catalog_match,
        )

    if raw_code:
        return PaperResolution(
            upload_intent=intent,
            paper_code_raw=raw_code,
            question_numbers=qnums,
            page_count=page_count,
            paper_id=None,
            paper_label=None,
            match_confidence="low",
            match_source="manual",
            grading_route="open_ai_grading",
            needs_user_confirmation=True,
            summary="输入的 paper code 暂时无法解析，请确认格式，例如 9709/12/M/J/16。",
        )

    if intent == "answer_pages_only":
        summary = "当前像是只上传了答案页；请补充题目页、封面或 paper code，才能可靠按 mark scheme 批改。"
    elif intent in {"past_paper", "full_past_paper_pdf", "partial_past_paper_pages"}:
        summary = "你选择了 Past Paper，但还没有 paper code；建议补充封面页或 paper code，当前先使用开放 AI 批改。"
    else:
        summary = "未提供明确卷子信息，系统将先尝试开放 AI 批改。"

    return PaperResolution(
        upload_intent=intent,
        paper_code_raw=None,
        question_numbers=qnums,
        page_count=page_count,
        paper_id=None,
        paper_label=None,
        match_confidence="low",
        match_source="none",
        grading_route="open_ai_grading",
        needs_user_confirmation=intent != "unknown",
        summary=summary,
    )


def build_user_hint_with_resolution(user_hint: str, resolution: PaperResolution) -> str:
    parts = [user_hint.strip()] if user_hint.strip() else []
    context = [
        "Upload context:",
        f"- upload_intent: {resolution.upload_intent}",
        f"- grading_route: {resolution.grading_route}",
        f"- match_confidence: {resolution.match_confidence}",
    ]
    if resolution.paper_label:
        context.append(f"- matched_paper: {resolution.paper_label}")
    if resolution.question_numbers:
        context.append(f"- requested_questions: {', '.join(resolution.question_numbers)}")
    if resolution.catalog_match:
        context.append("- local_paper_assets: available")
        context.append("- mark_scheme_context: attached per question when a reliable match is available")
    context.append(f"- routing_note: {resolution.summary}")
    parts.append("\n".join(context))
    return "\n\n".join(parts)


def build_resolution_steps(resolution: PaperResolution) -> list[dict]:
    detail = resolution.event_detail()
    return [
        {
            "question_number": "本次上传",
            "step_type": "think",
            "title": "识别上传类型",
            "summary": _intent_summary(resolution),
            "status": "completed",
            "agent_name": "Upload Router",
            "confidence": resolution.match_confidence,
            "user_visible": True,
            "severity": "info",
            "detail": detail,
            "match_confidence": resolution.match_confidence,
            "match_source": resolution.match_source,
            "grading_route": resolution.grading_route,
            "needs_user_confirmation": resolution.needs_user_confirmation,
        },
        {
            "question_number": "本次上传",
            "step_type": "observe",
            "title": "匹配 Past Paper",
            "summary": resolution.summary,
            "status": "completed",
            "agent_name": "Paper Resolver",
            "tool": "papers_catalog.csv",
            "confidence": resolution.match_confidence,
            "user_visible": True,
            "severity": "success" if resolution.grading_route == "past_paper_mark_scheme" else "warning",
            "detail": detail,
            "paper_id": resolution.paper_id,
            "question_id": ",".join(resolution.question_numbers) if resolution.question_numbers else None,
            "match_confidence": resolution.match_confidence,
            "match_source": resolution.match_source,
            "grading_route": resolution.grading_route,
            "needs_user_confirmation": resolution.needs_user_confirmation,
        },
        {
            "question_number": "本次上传",
            "step_type": "decide",
            "title": "选择批改路径",
            "summary": _route_summary(resolution),
            "status": "completed",
            "agent_name": "Upload Router",
            "confidence": resolution.match_confidence,
            "user_visible": True,
            "severity": "success" if resolution.grading_route == "past_paper_mark_scheme" else "info",
            "detail": detail,
            "paper_id": resolution.paper_id,
            "question_id": ",".join(resolution.question_numbers) if resolution.question_numbers else None,
            "match_confidence": resolution.match_confidence,
            "match_source": resolution.match_source,
            "grading_route": resolution.grading_route,
            "needs_user_confirmation": resolution.needs_user_confirmation,
        },
    ]


def _intent_summary(resolution: PaperResolution) -> str:
    labels = {
        "past_paper": "用户选择了 Past Paper / 真题卷。",
        "custom_homework": "用户选择了老师布置的自定义作业。",
        "unknown": "用户选择让系统自动识别上传内容。",
        "full_past_paper_pdf": "上传内容按完整 Past Paper PDF 处理。",
        "partial_past_paper_pages": "上传内容按部分 Past Paper 页面处理。",
        "answer_pages_only": "上传内容可能只有学生答案页。",
    }
    return f"{labels.get(resolution.upload_intent, labels['unknown'])} 共 {resolution.page_count} 页。"


def _route_summary(resolution: PaperResolution) -> str:
    if resolution.grading_route == "past_paper_mark_scheme":
        return "已进入 Past Paper 匹配批改：先用本地卷子/mark scheme 上下文，再生成扣分解释和学习建议。"
    if resolution.needs_user_confirmation:
        return "当前信息不足以可靠锁定 mark scheme，本次先走开放 AI 批改，并建议学生补充卷子信息。"
    return "本次使用开放 AI 批改：适合老师自定义作业或暂未匹配到题库的题目。"
