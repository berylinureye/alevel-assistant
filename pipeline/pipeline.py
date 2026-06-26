"""主流程：整页图 → 结构化 JSON（含批改 + 路由 + feedback + 整页汇总）"""
from __future__ import annotations

import logging
import os
import queue
import re
import threading
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from typing import Any

_log = logging.getLogger("pipeline")

from utils.image_utils import load_image
from pipeline.segmenter import segment_and_extract, group_pages_by_continuity
from grader.grader import grade_question
from grader.multi_agent import grade_question_multi_agent, GradingError
from grader.multi_agent_config import build_grading_agents
from grader.solution_explainer import generate_solution, generate_solution_from_deliberations
from grader.diagram_grader import (
    build_diagram_review_grade,
    build_low_confidence_review_grade,
    is_answer_effectively_empty,
)
from formatter.feedback import generate_feedback
from formatter.summarizer import build_summary
from questionbank.database import ensure_db
from questionbank.mark_scheme import build_mark_scheme_context_map
from questionbank.pastpaper_matcher import build_questionbank_mark_scheme_context
from router.models import ModelRole, TaskType, build_registry
from router.context import RouteContext
from router.router import route
from router.router import RouteDecision
from models.schemas import GradeResult, QuestionData, QuestionType

STREAM_QUESTION_TEXT_CHARS = 520
STREAM_PARENT_STEM_CHARS = 900
STREAM_STUDENT_ANSWER_CHARS = 600
STREAM_WORKING_STEP_CHARS = 280
STREAM_MAX_WORKING_STEPS = 8
FAST_BATCH_QUESTION_TIMEOUT_SECONDS = float(os.environ.get("FAST_BATCH_QUESTION_TIMEOUT_SECONDS", "120"))
FAST_BATCH_AFTER_FIRST_QUESTION_TIMEOUT_SECONDS = float(os.environ.get("FAST_BATCH_AFTER_FIRST_QUESTION_TIMEOUT_SECONDS", "25"))
FAST_BATCH_MAX_WORKERS = int(os.environ.get("FAST_BATCH_MAX_WORKERS", "16"))
FAST_BATCH_PREPARE_TIMEOUT_SECONDS = float(os.environ.get("FAST_BATCH_PREPARE_TIMEOUT_SECONDS", "120"))
FAST_BATCH_PREPARE_MAX_WORKERS = int(os.environ.get("FAST_BATCH_PREPARE_MAX_WORKERS", "10"))
FAST_BATCH_PARSE_ATTEMPTS = int(os.environ.get("FAST_BATCH_PARSE_ATTEMPTS", "1"))
FAST_BATCH_REQUEST_RETRIES = int(os.environ.get("FAST_BATCH_REQUEST_RETRIES", "0"))
DEFAULT_RECOGNITION_TIMEOUT_SECONDS = float(os.environ.get("RECOGNITION_TIMEOUT_SECONDS", "90"))


def _clip_stream_text(value: object, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def _clip_stream_steps(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    clipped = [
        _clip_stream_text(value, STREAM_WORKING_STEP_CHARS)
        for value in values[:STREAM_MAX_WORKING_STEPS]
        if str(value or "").strip()
    ]
    if len(values) > STREAM_MAX_WORKING_STEPS:
        clipped.append("...")
    return clipped


def _stream_question_payload(ext: dict) -> dict[str, Any]:
    return {
        "question_number": str(ext.get("question_number", "?")),
        "question_text": _clip_stream_text(ext.get("question_text", ""), STREAM_QUESTION_TEXT_CHARS),
        "parent_stem": _clip_stream_text(ext.get("parent_stem", "") or "", STREAM_PARENT_STEM_CHARS),
        "student_answer": _clip_stream_text(ext.get("student_answer", ""), STREAM_STUDENT_ANSWER_CHARS),
        "working_steps": _clip_stream_steps(ext.get("working_steps", []) or []),
        "marks": ext.get("marks", 0),
        "bbox": ext.get("bbox", []) or [],
        "page": ext.get("page"),
        "image_quality": ext.get("image_quality", ""),
        "confidence": float(ext.get("confidence", 0.0) or 0.0),
        "grading_route": ext.get("grading_route"),
        "mark_scheme_confidence": ext.get("mark_scheme_confidence"),
        "mark_scheme_context_error": ext.get("mark_scheme_context_error"),
        "questionbank_question_id": ext.get("questionbank_question_id"),
        "questionbank_match_confidence": ext.get("questionbank_match_confidence"),
    }


def _build_fast_batch_timeout_result(
    extracted: dict,
    timeout_seconds: float,
) -> dict[str, Any]:
    qnum = str(extracted.get("question_number", "?"))
    full_score = float(extracted.get("marks") or 0.0)
    timeout_label = int(timeout_seconds) if timeout_seconds >= 1 else timeout_seconds
    grade = GradeResult(
        question_number=qnum,
        question_type=QuestionType.unknown,
        is_correct=False,
        score=0.0,
        full_score=full_score,
        error_type="fast_batch_timeout",
        knowledge_tags=[],
        needs_review=True,
        short_feedback=f"快评模式单题超过 {timeout_label} 秒，已转为需复核。",
        grading_confidence=0.0,
        correct_answer=None,
        syllabus_topics=[],
        relevant_formulas=[],
        student_feedback="这题需要老师复核，系统已先返回本次批量上传结果。",
        teacher_feedback="Fast batch reached the per-question budget; manual review is required.",
    )
    record = {
        "question_number": qnum,
        "bbox": extracted.get("bbox", []) or [],
        "question_text": extracted.get("question_text", "") or "",
        "parent_stem": extracted.get("parent_stem", "") or "",
        "student_answer": extracted.get("student_answer", "") or "",
        "working_steps": extracted.get("working_steps", []) or [],
        "marks": extracted.get("marks", 0),
        "page": extracted.get("page"),
        "image_quality": extracted.get("image_quality", "unknown"),
        "confidence": float(extracted.get("confidence", 0.0) or 0.0),
        "grading": {
            **grade.model_dump(),
            "used_model": "fast_batch_timeout",
        },
        "feedback": {
            "question_number": qnum,
            "student_feedback": grade.student_feedback or "",
            "teacher_feedback": grade.teacher_feedback or "",
        },
        "solution_text": None,
        "grading_route": extracted.get("grading_route"),
        "mark_scheme_confidence": extracted.get("mark_scheme_confidence"),
        "mark_scheme_context_error": extracted.get("mark_scheme_context_error"),
        "questionbank_question_id": extracted.get("questionbank_question_id"),
        "questionbank_match_confidence": extracted.get("questionbank_match_confidence"),
    }
    return {"record": record, "grade": grade}


def _recognition_timeout_fallback(images: list[Any]) -> list[dict]:
    width, height = (1, 1)
    if images:
        width, height = getattr(images[0], "size", (1, 1))
    return [
        {
            "question_number": "本次上传",
            "bbox": [0, 0, int(width), int(height)],
            "question_text": "",
            "parent_stem": "",
            "student_answer": "",
            "working_steps": [],
            "marks": 0,
            "image_quality": "poor",
            "confidence": 0.0,
            "page": 1,
            "recognition_timeout": True,
        }
    ]


def _segment_with_timeout(
    images: list[Any],
    vision_client,
    user_hint: str,
    ocr_client,
    timeout_seconds: float | None,
) -> list[dict]:
    if timeout_seconds is None or timeout_seconds <= 0:
        return _segment_with_grouping(images, vision_client, user_hint, ocr_client)

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(_segment_with_grouping, images, vision_client, user_hint, ocr_client)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        _log.warning("question recognition timed out after %.1fs", timeout_seconds)
        future.cancel()
        return _recognition_timeout_fallback(images)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _segment_with_grouping(
    images,
    vision_client,
    user_hint: str,
    ocr_client,
) -> list[dict]:
    """根据页首题号把图片分组，每组独立并行走 segment_and_extract，最后做一次跨组
    parent_stem 二次回填。独立页并行 → 不比旧的 per-image 慢；跨页续题合并 → 解决
    Q6(c) 在 page 2 找不到 page 1 的主题干的问题。"""
    if not images:
        return []
    groups = group_pages_by_continuity(list(images), ocr_client)

    def _annotate_group(items: list[dict], group_idxs: list[int]) -> list[dict]:
        """Tag each item with its global page number AND whether its page is
        a continuation of the group leader (used by
        _merge_cross_page_answers to fold handwritten answer overflow back
        into the originating sub-question). A non-leader page within a group
        means ``group_pages_by_continuity`` detected no new printed question
        number on its header — i.e. pure continuation.
        """
        for it in items:
            try:
                local = int(it.get("page", 1) or 1)
            except (ValueError, TypeError):
                local = 1
            local = max(1, min(local, len(group_idxs)))
            it["page"] = group_idxs[local - 1] + 1
            it["_continuation_page"] = (local > 1)
        return items

    if len(groups) == 1:
        # 单组：保留旧行为（也涵盖单图 + 没 ocr_client 的情况）。
        # 即便单组也要标 _continuation_page —— 若本组跨多页，后续页仍是 continuation。
        items = segment_and_extract(
            images, vision_client, user_hint=user_hint, ocr_client=ocr_client
        )
        return _annotate_group(items, groups[0])

    _log.info("segmenter 分 %d 组并行执行 (groups=%s)", len(groups), groups)

    def _run_one_group(group_idxs: list[int]) -> list[dict]:
        group_imgs = [images[i] for i in group_idxs]
        items = segment_and_extract(
            group_imgs, vision_client, user_hint=user_hint, ocr_client=ocr_client
        )
        return _annotate_group(items, group_idxs)

    merged: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(len(groups), 4)) as pool:
        for items in pool.map(_run_one_group, groups):
            merged.extend(items)

    # 按全局 page 重排，然后跨组再做一次 parent_stem 回填：
    # 如果 group 2 的某小题是孤儿 "(c)"，它需要找 group 1 最后一道带数字前缀的父题的 stem。
    merged.sort(key=lambda it: (int(it.get("page", 1) or 1),))
    from pipeline.segmenter import _attach_parent_stems
    _attach_parent_stems(merged)
    return merged


def _segment_fast_batch_individual(
    images: list[Any],
    vision_client,
    user_hint: str,
    ocr_client,
    *,
    timeout_seconds: float = FAST_BATCH_PREPARE_TIMEOUT_SECONDS,
) -> list[dict]:
    """Fast batch recognition path: identify each page independently in
    parallel, then stitch cross-page context once. This avoids a single large
    multi-image vision request becoming the long pole for 10+ photos.
    """
    if not images:
        return []

    def _run_with_timeout(img: Any) -> tuple[list[dict], bool | None]:
        result: dict[str, Any] = {}

        def _target() -> None:
            items = segment_and_extract(
                [img], vision_client, user_hint=user_hint, ocr_client=ocr_client
            )
            starts_with_qnum: bool | None = None
            if ocr_client is not None:
                try:
                    from pipeline.segmenter import (
                        _page_header_text,
                        page_starts_with_numbered_question,
                    )
                    header_text = _page_header_text(img, ocr_client)
                    starts_with_qnum = page_starts_with_numbered_question(header_text)
                except Exception:
                    starts_with_qnum = None
            result["items"] = items
            result["starts_with_qnum"] = starts_with_qnum

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=max(0.1, timeout_seconds))
        if thread.is_alive():
            _log.warning("fast_batch page recognition timed out after %.1fs", timeout_seconds)
            return _recognition_timeout_fallback([img]), None
        return list(result.get("items") or []), result.get("starts_with_qnum")

    def _run_one(index_and_image: tuple[int, Any]) -> tuple[int, list[dict], bool | None]:
        idx, img = index_and_image
        items, starts_with_qnum = _run_with_timeout(img)
        global_page = idx + 1
        is_continuation = (idx > 0) and (starts_with_qnum is False)
        for item in items:
            item["page"] = global_page
            if is_continuation:
                item["_continuation_page"] = True
        return idx, items, starts_with_qnum

    max_workers = min(len(images), max(1, FAST_BATCH_PREPARE_MAX_WORKERS))
    results: list[tuple[int, list[dict], bool | None]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for result in pool.map(_run_one, enumerate(images)):
            results.append(result)

    merged: list[dict] = []
    for _idx, items, _starts_with_qnum in sorted(results, key=lambda item: item[0]):
        merged.extend(items)

    try:
        from pipeline.segmenter import _attach_parent_stems
        _attach_parent_stems(merged)
    except Exception as exc:
        _log.warning("fast_batch cross-page _attach_parent_stems failed: %s", exc)
    return merged


def _flatten_for_stream(record: dict, feedback_mode: str = "both") -> dict[str, Any]:
    """
    将 pipeline 内部的 record dict 转为与 QuestionResponse 一致的扁平 dict（与 routes._flatten_question 对齐）。
    feedback_mode: "student" | "teacher" | "both"
    """
    grading = record.get("grading", {})
    feedback = record.get("feedback", {})

    student_fb: str | None = feedback.get("student_feedback")
    teacher_fb: str | None = feedback.get("teacher_feedback")
    if feedback_mode == "student":
        teacher_fb = None
    elif feedback_mode == "teacher":
        student_fb = None

    return {
        "question_number": record.get("question_number", ""),
        "bbox": record.get("bbox", []),
        "question_text": _clip_stream_text(record.get("question_text", ""), STREAM_QUESTION_TEXT_CHARS),
        "parent_stem": _clip_stream_text(record.get("parent_stem", ""), STREAM_PARENT_STEM_CHARS),
        "student_answer": _clip_stream_text(record.get("student_answer", ""), STREAM_STUDENT_ANSWER_CHARS),
        "working_steps": _clip_stream_steps(record.get("working_steps", [])),
        "page": record.get("page"),
        "image_quality": record.get("image_quality", ""),
        "confidence": float(record.get("confidence", 0.0)),
        "is_correct": bool(grading.get("is_correct", False)),
        "grading_confidence": float(grading.get("grading_confidence", 0.0)),
        "score": float(grading.get("score", 0.0)),
        "full_score": float(grading.get("full_score", 0.0)),
        "error_type": grading.get("error_type"),
        "knowledge_tags": grading.get("knowledge_tags", []),
        "needs_review": bool(grading.get("needs_review", False)),
        "short_feedback": grading.get("short_feedback", ""),
        "escalation_reasons": grading.get("escalation_reasons", []),
        "syllabus_topics": grading.get("syllabus_topics", []),
        "relevant_formulas": grading.get("relevant_formulas", []),
        "correct_answer": grading.get("correct_answer"),
        "unanswered": bool(grading.get("unanswered", False)),
        "detail_deductions": grading.get("detail_deductions", []) or [],
        "solution_text": record.get("solution_text"),
        "grading_route": record.get("grading_route"),
        "mark_scheme_confidence": record.get("mark_scheme_confidence"),
        "mark_scheme_context_error": record.get("mark_scheme_context_error"),
        "questionbank_question_id": record.get("questionbank_question_id"),
        "questionbank_match_confidence": record.get("questionbank_match_confidence"),
        "student_feedback": student_fb,
        "teacher_feedback": teacher_fb,
        "routing_info": {
            "used_model": grading.get("used_model", "unknown"),
            "escalated": bool(grading.get("escalation_reasons", [])),
            "escalation_reasons": grading.get("escalation_reasons", []),
        },
    }


def _build_fast_page_summary(grades: list[GradeResult]) -> dict[str, Any]:
    correct_count = sum(1 for grade in grades if grade.is_correct)
    unanswered_count = sum(1 for grade in grades if grade.unanswered or grade.error_type == "unanswered")
    incorrect_count = sum(1 for grade in grades if not grade.is_correct and not (grade.unanswered or grade.error_type == "unanswered"))
    review_count = sum(1 for grade in grades if grade.needs_review)
    score_total = sum(float(grade.score or 0) for grade in grades)
    full_score_total = sum(float(grade.full_score or 0) for grade in grades)

    error_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    wrong_tag_counts: dict[str, int] = {}
    for grade in grades:
        if grade.error_type and grade.error_type not in {"correct", "unknown"}:
            error_counts[grade.error_type] = error_counts.get(grade.error_type, 0) + 1
        for tag in grade.knowledge_tags or []:
            key = str(tag).strip()
            if not key:
                continue
            tag_counts[key] = tag_counts.get(key, 0) + 1
            if not grade.is_correct:
                wrong_tag_counts[key] = wrong_tag_counts.get(key, 0) + 1

    priority_topics = [
        {
            "topic": topic,
            "subtopic": None,
            "chapter": "",
            "error_count": count,
            "key_formulas": [],
        }
        for topic, count in sorted(wrong_tag_counts.items(), key=lambda item: -item[1])[:3]
    ]

    return {
        "total_questions": len(grades),
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "review_count": review_count,
        "score_total": score_total,
        "full_score_total": full_score_total,
        "common_error_types": [
            error for error, count in sorted(error_counts.items(), key=lambda item: -item[1]) if count >= 2
        ],
        "knowledge_tags_summary": tag_counts,
        "estimated_review_minutes": max(0, incorrect_count * 6 + review_count * 4),
        "priority_topics": priority_topics,
        "overall_teacher_comment": "已使用快速首轮批改生成结果；重点复查低置信和错题。",
    }


def _question_context_key(value: object) -> str | None:
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else None


def _is_orphan_subpart_number(value: object) -> bool:
    token = str(value or "").strip()
    if not token:
        return False
    # Frontend/page stitching may prefix numbers like "图片 2-c"; only inspect
    # the final question token.
    token = re.split(r"\s*-\s*", token)[-1]
    clean = re.sub(r"[\s().]+", "", token).lower()
    if not clean or any(ch.isdigit() for ch in clean):
        return False
    return bool(re.fullmatch(r"[a-z]{1,2}|[ivxlcdm]+", clean))


def _attach_mark_scheme_contexts(
    extracted_list: list[dict],
    paper_context: dict | None,
) -> None:
    if not paper_context:
        return
    if paper_context.get("grading_route") != "past_paper_mark_scheme":
        return

    catalog_match = paper_context.get("catalog_match")
    if not isinstance(catalog_match, dict):
        return

    requested = [
        q for q in (paper_context.get("question_numbers") or [])
        if _question_context_key(q)
    ]
    detected = [
        key
        for key in (_question_context_key(ext.get("question_number")) for ext in extracted_list)
        if key
    ]
    question_numbers = list(dict.fromkeys(requested + detected))
    if not question_numbers:
        return

    contexts = build_mark_scheme_context_map(
        catalog_match=catalog_match,
        question_numbers=question_numbers,
        paper_label=paper_context.get("paper_label"),
    )

    qb_conn = None
    try:
        for ext in extracted_list:
            if ext.get("mark_scheme_context"):
                continue
            key = _question_context_key(ext.get("question_number"))
            context = contexts.get(key or "")

            qb_context = None
            raw_question_number = str(ext.get("question_number") or key or "").strip()
            if raw_question_number:
                try:
                    if qb_conn is None:
                        qb_conn = ensure_db()
                    qb_context = build_questionbank_mark_scheme_context(
                        qb_conn,
                        catalog_match=catalog_match,
                        question_number=raw_question_number,
                    )
                except Exception as exc:
                    _log.debug("Question-bank mark-scheme context skipped: %s", exc)
                    qb_context = None

            official_ok = (
                context is not None
                and bool(context.text)
                and context.confidence in {"high", "medium"}
            )

            parts: list[str] = []
            if qb_context and qb_context.text:
                parts.append(qb_context.text)
                ext["questionbank_question_id"] = qb_context.question_id
                ext["questionbank_match_confidence"] = qb_context.confidence
            if official_ok:
                parts.append(context.text)

            if parts:
                ext["mark_scheme_context"] = "\n\n".join(parts)
                ext["mark_scheme_confidence"] = (
                    context.confidence if official_ok and context else qb_context.confidence
                )
                ext["grading_route"] = "past_paper_mark_scheme"
                if not official_ok and context and context.reason:
                    ext["mark_scheme_context_error"] = (
                        "Official PDF block unavailable; using structured question-bank "
                        f"mark scheme. {context.reason}"
                    )
            else:
                ext["grading_route"] = "open_ai_grading"
                ext["mark_scheme_context_error"] = (
                    context.reason if context else "No question-level mark scheme context found."
                )
    finally:
        if qb_conn is not None:
            try:
                qb_conn.close()
            except Exception:
                pass


def _build_solution_client(agent_clients, base_client):
    """
    创建独立的 solution 客户端——只在 aggregator 路径失败时作为 fallback 触发。

    默认用 deepseek-chat (V3 非 thinking, 5-10s)。以前默认 deepseek-reasoner
    (R1 thinking, 30-60s/题) 对准确性略好但会让 7 页 PDF 多花 3-5 分钟,而且
    fallback 触发不频繁、作业批改场景对单题 solution 深度要求有限,速度赢了。

    若想回到 thinking 版做精度,设 SOLUTION_MODEL=deepseek-reasoner。
    """
    from router.models import OpenAICompatClient
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if ds_key:
        model_id = os.environ.get("SOLUTION_MODEL", "deepseek-chat").strip() or "deepseek-chat"
        # thinking 版需要更长 timeout，chat 版 30s 足够
        timeout = 120 if "reasoner" in model_id.lower() else 30
        return OpenAICompatClient(
            base_url="https://api.deepseek.com/v1",
            model_id=model_id,
            provider="deepseek",
            role=ModelRole.base,
            api_key=ds_key,
            timeout=timeout,
        )
    if agent_clients:
        return agent_clients[0][1]
    return base_client


def _build_aggregator_client(agent_clients, base_client):
    """
    解题思路 aggregator 客户端：DeepSeek-chat（非 thinking 版）。
    任务是"综合 5 个 agent 已经产出的推理素材"→ 标准格式解题思路，
    不需要深度推理，只需要强指令跟随 + 中文 LaTeX 能力。典型 5-8s 返回。
    比 solution_client (deepseek-reasoner 30-60s) 快一个数量级。
    """
    from router.models import OpenAICompatClient
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if ds_key:
        return OpenAICompatClient(
            base_url="https://api.deepseek.com/v1",
            model_id="deepseek-chat",  # V3，非 thinking
            provider="deepseek",
            role=ModelRole.base,
            api_key=ds_key,
            timeout=30,
        )
    # 降级到已有的 fast 层 agent（通常就是 deepseek-chat / qwen-plus）
    if agent_clients:
        for name, cli in agent_clients:
            if "Fast" in name:
                return cli
        return agent_clients[0][1]
    return base_client


def _process_one_question(
    extracted: dict,
    base_client,
    review_client,
    review_mode: str,
    do_grade: bool,
    agent_clients: list | None = None,
    solution_client=None,
    progress_queue: queue.Queue | None = None,
    generate_solution_inline: bool = True,
    aggregator_client=None,
    fallback_feedback_llm: bool = True,
    fast_batch_mode: bool = False,
) -> dict:
    """处理单题：用 segment 阶段已提取的数据，直接批改 + 生成反馈。"""
    qnum = str(extracted.get("question_number", "?"))
    try:
        question = QuestionData(
            question_number=qnum,
            bbox=extracted["bbox"],
            question_text=extracted["question_text"],
            student_answer=extracted["student_answer"],
            working_steps=extracted["working_steps"],
            marks=extracted.get("marks", 0),
            parent_stem=extracted.get("parent_stem"),
            contains_diagram=bool(extracted.get("contains_diagram", False)),
            diagram_type=extracted.get("diagram_type"),
            image_quality=extracted["image_quality"],
            confidence=extracted["confidence"],
            mark_scheme_context=extracted.get("mark_scheme_context") or None,
        )
        record = question.model_dump()
        record.pop("mark_scheme_context", None)
        if extracted.get("grading_route"):
            record["grading_route"] = extracted.get("grading_route")
        if extracted.get("mark_scheme_confidence"):
            record["mark_scheme_confidence"] = extracted.get("mark_scheme_confidence")
        if extracted.get("mark_scheme_context_error"):
            record["mark_scheme_context_error"] = extracted.get("mark_scheme_context_error")
        if extracted.get("questionbank_question_id") is not None:
            record["questionbank_question_id"] = extracted.get("questionbank_question_id")
        if extracted.get("questionbank_match_confidence"):
            record["questionbank_match_confidence"] = extracted.get("questionbank_match_confidence")
        # 保留 segmenter 产出的 page 字段（跨页识别需要）
        if extracted.get("page") is not None:
            record["page"] = int(extracted["page"])
        if extracted.get("recognition_timeout"):
            record["recognition_timeout"] = True

        if _is_orphan_subpart_number(qnum) and not question.parent_stem:
            full_score = float(question.marks) if question.marks > 0 else 0.0
            missing_context_grade = GradeResult(
                question_number=qnum,
                question_type=QuestionType.unknown,
                is_correct=False,
                score=0.0,
                full_score=full_score,
                error_type="missing_parent_context",
                knowledge_tags=[],
                needs_review=True,
                short_feedback="缺少本小题依赖的父题题干。请补充上一页或完整题目后再批改。",
                grading_confidence=0.0,
                correct_answer=None,
                syllabus_topics=[],
                relevant_formulas=[],
                student_feedback="这道题像是某道大题的子题，但当前图片缺少完整题目条件。请补充上一页或完整题目后重新提交。",
                teacher_feedback="系统检测到裸子题且缺少 parent_stem，未进行自动判分，建议补充完整题干后复核。",
            )
            record["grading"] = missing_context_grade.model_dump()
            record["grading"]["used_model"] = "missing_parent_guard"
            record["feedback"] = {
                "question_number": qnum,
                "student_feedback": missing_context_grade.student_feedback or "",
                "teacher_feedback": missing_context_grade.teacher_feedback or "",
            }
            record["solution_text"] = None
            return {"record": record, "grade": missing_context_grade}

        if extracted.get("recognition_timeout"):
            timeout_grade = GradeResult(
                question_number=qnum,
                question_type=QuestionType.unknown,
                is_correct=False,
                score=0.0,
                full_score=0.0,
                error_type="recognition_timeout",
                knowledge_tags=[],
                needs_review=True,
                short_feedback="图片识别超过本次快速批改预算。请复核或重新提交更清晰的照片。",
                grading_confidence=0.0,
                syllabus_topics=[],
                relevant_formulas=[],
            )
            record["grading"] = timeout_grade.model_dump()
            record["grading"]["used_model"] = "recognition_timeout"
            record["feedback"] = {
                "question_number": qnum,
                "student_feedback": "- 这张图片识别超时，系统已先返回其他可用结果。\n- 可以单独重传这张图，或换更清晰的照片。",
                "teacher_feedback": "- Error: recognition_timeout\n- Gap: 快速批量识别未在预算内完成\n- Action: 建议人工复核或单图重试",
            }
            return {"record": record, "grade": timeout_grade}

        if not question.question_text.strip() and question.confidence < 0.3:
            unreadable_grade = GradeResult(
                question_number=qnum,
                question_type=QuestionType.unknown,
                is_correct=False,
                score=0.0,
                full_score=0.0,
                error_type="unreadable",
                knowledge_tags=[],
                needs_review=True,
                short_feedback="无法识别此题内容。请确保照片清晰、光线充足，重新拍照后再试。",
                grading_confidence=0.0,
                syllabus_topics=[],
                relevant_formulas=[],
            )
            record["grading"] = unreadable_grade.model_dump()
            record["grading"]["used_model"] = "none"
            record["feedback"] = {
                "question_number": qnum,
                "student_feedback": "- 这道题无法被识别，可能是照片不够清晰。\n- 请重新拍一张光线好、文字清楚的照片。",
                "teacher_feedback": "- Error: 图像识别失败，未提取到题目内容\n- Gap: N/A\n- Action: 请学生重新拍照提交",
            }
            return {"record": record, "grade": unreadable_grade}

        # --- 未作答检测：学生没有写答案且没有工作步骤，跳过 LLM 批改 ---
        student_ans_stripped = (question.student_answer or "").strip()
        has_working = bool(question.working_steps and len(question.working_steps) > 0)
        _unanswered = (
            not student_ans_stripped
            or student_ans_stripped.lower() in ("(no answer provided)", "no answer", "none", "n/a", "")
        ) and not has_working  # 有工作步骤时不算未作答，交给 LLM 判断
        if _unanswered and question.question_text.strip():
            _log.info("第 %s 题未作答，跳过批改", qnum)
            unanswered_grade = GradeResult(
                question_number=qnum,
                question_type=QuestionType.unknown,
                is_correct=False,
                score=0.0,
                full_score=float(question.marks) if question.marks > 0 else 1.0,
                error_type="unanswered",
                knowledge_tags=[],
                needs_review=False,
                short_feedback="此题未作答。",
                grading_confidence=1.0,
                correct_answer=None,
                unanswered=True,
                syllabus_topics=[],
                relevant_formulas=[],
            )
            record["grading"] = unanswered_grade.model_dump()
            record["grading"]["used_model"] = "none"
            record["feedback"] = {
                "question_number": qnum,
                "student_feedback": "- 这道题你没有作答。\n- 建议尝试做一做，即使不确定也可以写出思路争取步骤分。",
                "teacher_feedback": "- Error: 学生未作答\n- Gap: 需确认是时间不足还是知识盲区\n- Action: 课后跟进了解原因",
            }
            # 未作答也自动生成解题思路（若 inline 且有 solution_client）
            if solution_client is not None and generate_solution_inline:
                try:
                    _log.info("生成解题思路第 %s 题（未作答）...", qnum)
                    sol = generate_solution(question, unanswered_grade, solution_client)
                    record["solution_text"] = sol
                except Exception as exc:
                    _log.warning("Q%s unanswered solution failed: %s", qnum, exc)
                    record["solution_text"] = None
            else:
                record["solution_text"] = None
            return {"record": record, "grade": unanswered_grade}

        if not do_grade:
            return {"record": record, "grade": None}

        # --- 安全网 A：图表题短路 ---
        # 学生以作图作答时 extractor 无法转录，grader 会判错。这里直接跳过判分、
        # 生成作图参考步骤填入 correct_answer，标 needs_review 让教师复核。
        #
        # 注意：diagram_type="other" 是个兜底类别，实践中经常误触发——例如学生密密麻麻
        # 的手写代数演算被 VL 误读成 "drawing"。对于 "other"（以及没 type 的情况）
        # 走常规 grader 路径，交给 LLM 按代数答案判分；只有被识别成特定图类
        # （stem_leaf/histogram/box_plot/cumulative_frequency/scatter/bar_chart）
        # 时才走专门的 diagram review。
        _specific_diagram = question.diagram_type not in (None, "", "other")
        if question.contains_diagram and _specific_diagram:
            _log.info(
                "第 %s 题为图表题（%s），跳过自动判分，生成作图参考",
                qnum, question.diagram_type or "unknown",
            )
            base_grade = build_diagram_review_grade(
                question, solution_client or base_client,
            )
            final_grade = base_grade
            record["grading"] = final_grade.model_dump()
            record["grading"]["used_model"] = "diagram_review"
            record["feedback"] = {
                "question_number": qnum,
                "student_feedback": final_grade.student_feedback or "",
                "teacher_feedback": final_grade.teacher_feedback or "",
            }
            if solution_client is not None and generate_solution_inline:
                try:
                    sol = generate_solution(question, final_grade, solution_client)
                    record["solution_text"] = sol
                except Exception as exc:
                    _log.warning("Q%s diagram solution failed: %s", qnum, exc)
                    record["solution_text"] = None
            else:
                record["solution_text"] = None
            return {"record": record, "grade": final_grade}

        # --- base 批改（多 agent 并行 or 单 agent 降级）---
        def _progress_cb(data: dict) -> None:
            if progress_queue is not None:
                event_type = "agent_step" if data.get("event") == "agent_step" else "agent_progress"
                payload = {k: v for k, v in data.items() if k != "event"}
                progress_queue.put((event_type, {"question_number": qnum, **payload}))

        if agent_clients and len(agent_clients) >= 1:
            _log.info("批改第 %s 题 (multi-agent, %d agents)...", qnum, len(agent_clients))
            try:
                base_grade = grade_question_multi_agent(
                    question, agent_clients, task=TaskType.grade,
                    progress_callback=_progress_cb,
                )
            except GradingError as e:
                _log.warning("Q%s multi-agent grading failed: %s, falling back to single model", qnum, e)
                if fast_batch_mode:
                    base_grade = grade_question(
                        question,
                        base_client,
                        task=TaskType.grade,
                        allow_llm_classification=False,
                        parse_attempts=FAST_BATCH_PARSE_ATTEMPTS,
                        request_retries=FAST_BATCH_REQUEST_RETRIES,
                    )
                else:
                    base_grade = grade_question(question, base_client, task=TaskType.grade)
        else:
            _log.info("批改第 %s 题 (base, single model)...", qnum)
            if fast_batch_mode:
                base_grade = grade_question(
                    question,
                    base_client,
                    task=TaskType.grade,
                    allow_llm_classification=False,
                    parse_attempts=FAST_BATCH_PARSE_ATTEMPTS,
                    request_retries=FAST_BATCH_REQUEST_RETRIES,
                )
            else:
                base_grade = grade_question(question, base_client, task=TaskType.grade)

        # --- 安全网 B：提取置信度偏低 + student_answer 基本为空 + LLM 判错 ---
        # 很大概率是 extractor 漏识别（而非学生没写），直接判错会误伤。改判 needs_review。
        if (
            not base_grade.is_correct
            and question.confidence < 0.8
            and is_answer_effectively_empty(question)
        ):
            _log.info(
                "第 %s 题触发低置信度安全网 (extraction conf=%.2f, empty answer) → 改判 needs_review",
                qnum, question.confidence,
            )
            base_grade = build_low_confidence_review_grade(
                question, base_grade, reference_answer=base_grade.correct_answer,
            )

        # --- 路由判断 ---
        if review_mode == "force":
            decision = RouteDecision(role=ModelRole.review, reasons=["force_mode"], escalated=True)
        elif review_mode == "off":
            decision = RouteDecision(role=ModelRole.base, reasons=[], escalated=False)
        else:
            # 保守版 B：base 判正确 + 高置信度 → 跳过 review（不影响错题准确率）
            if base_grade.is_correct and base_grade.grading_confidence >= 0.8:
                _log.info("第 %s 题 base 正确且高置信(%.2f)，跳过 review", qnum, base_grade.grading_confidence)
                decision = RouteDecision(role=ModelRole.base, reasons=[], escalated=False)
            else:
                ctx = RouteContext(
                    image_quality         = question.image_quality,
                    extraction_confidence = question.confidence,
                    working_steps_count   = len(question.working_steps),
                    student_answer        = question.student_answer,
                    question_type         = base_grade.question_type,
                    grading_confidence    = base_grade.grading_confidence,
                    needs_review          = base_grade.needs_review,
                )
                decision = route(ctx)

        if decision.escalated:
            _log.info("升级第 %s 题 → review (%s)", qnum, decision.reasons)
            # 方案 C：review 调用加 30s 超时，超时降级到 base 结果
            try:
                _review_pool = ThreadPoolExecutor(max_workers=1)
                _review_future = _review_pool.submit(
                    grade_question, question, review_client, TaskType.review, base_grade,
                )
                final_grade = _review_future.result(timeout=20)
                _review_pool.shutdown(wait=False)
                final_grade.escalation_reasons = decision.reasons
            except Exception as review_exc:
                _review_pool.shutdown(wait=False)
                _log.warning("第 %s 题 review 超时或失败(%s)，降级使用 base 结果", qnum, review_exc)
                final_grade = base_grade
                final_grade.needs_review = True
                final_grade.escalation_reasons = decision.reasons + ["review_timeout"]
        else:
            final_grade = base_grade

        if extracted.get("needs_review"):
            final_grade.needs_review = True
            reason = str(extracted.get("review_reason", "") or "segmenter_inconsistency")
            final_grade.escalation_reasons = list(final_grade.escalation_reasons or []) + [
                f"segmenter:{reason}"
            ]

        if extracted.get("mark_scheme_context_error"):
            reason = str(extracted.get("mark_scheme_context_error"))
            final_grade.escalation_reasons = list(final_grade.escalation_reasons or []) + [
                f"mark_scheme:{reason}"
            ]

        record["grading"] = final_grade.model_dump()
        record["grading"]["used_model"] = (
            review_client.model_id if decision.escalated else base_client.model_id
        )

        # --- feedback (prefer inline from grading to save a separate LLM call) ---
        if final_grade.student_feedback or final_grade.teacher_feedback:
            record["feedback"] = {
                "question_number": qnum,
                "student_feedback": final_grade.student_feedback or "",
                "teacher_feedback": final_grade.teacher_feedback or "",
            }
        elif not fallback_feedback_llm:
            record["feedback"] = {
                "question_number": qnum,
                "student_feedback": final_grade.short_feedback or "已生成快评结果。",
                "teacher_feedback": final_grade.short_feedback or "Fast batch generated a first-pass result.",
            }
        else:
            _log.info("生成反馈第 %s 题 (fallback LLM call)...", qnum)
            fb = generate_feedback(
                grade          = final_grade,
                client         = review_client if decision.escalated else base_client,
                question_text  = question.question_text,
                student_answer = question.student_answer,
                working_steps  = question.working_steps,
            )
            record["feedback"] = fb.model_dump()

        # --- 解题思路：批改后立即生成，缓存到 record（失败不阻塞）---
        # 跳过未作答题目（无需解题思路）
        is_unanswered = (final_grade.error_type == "unanswered"
                         or not question.student_answer
                         or not question.student_answer.strip())
        # 仅对做错的题目自动生成解题思路；做对的题目按需前端调用 /explain-question
        if (solution_client is not None or aggregator_client is not None) and generate_solution_inline and not final_grade.is_correct:
            import time as _time_sol
            _t_sol = _time_sol.monotonic()
            _log.info("生成解题思路第 %s 题...", qnum)
            sol = None
            # 优先走 aggregator（5-8s，复用 5 agent 推理素材）
            if aggregator_client is not None and getattr(final_grade, "_agent_deliberations", None):
                sol = generate_solution_from_deliberations(
                    question, final_grade, aggregator_client,
                )
                _log.info("Q%s aggregator solution: %s (%.1fs)",
                          qnum, "ok" if sol else "fallback",
                          _time_sol.monotonic() - _t_sol)
            # Fallback：从零生成（deepseek-reasoner，慢但稳）
            if sol is None and solution_client is not None:
                _t_fb = _time_sol.monotonic()
                sol = generate_solution(question, final_grade, solution_client)
                _log.info("Q%s fallback solution: %s (%.1fs)",
                          qnum, "ok" if sol else "failed",
                          _time_sol.monotonic() - _t_fb)
            record["solution_text"] = sol
            _log.info("解题思路第 %s 题 total: %s (%.1fs)",
                       qnum, "ok" if sol else "failed", _time_sol.monotonic() - _t_sol)
        else:
            if is_unanswered:
                _log.info("第 %s 题未作答，跳过解题思路", qnum)
            elif not generate_solution_inline:
                _log.info("第 %s 题跳过 inline solution（前端按需调用 /explain-question）", qnum)
            record["solution_text"] = None

        return {"record": record, "grade": final_grade}
    except Exception as exc:
        _log.warning("Q%s processing failed: %s", qnum, exc)
        failed_grade = GradeResult(
            question_number=qnum,
            question_type=QuestionType.unknown,
            is_correct=False,
            score=0.0,
            full_score=0.0,
            error_type="processing_failed",
            knowledge_tags=[],
            needs_review=True,
            short_feedback=f"Processing failed: {exc}",
            grading_confidence=0.0,
            syllabus_topics=[],
            relevant_formulas=[],
        )
        return {
            "record": {
                "question_number": qnum,
                "bbox": extracted.get("bbox", []),
                "question_text": "",
                "student_answer": "",
                "working_steps": [],
                "image_quality": "poor",
                "confidence": 0.0,
                "grading": {
                    **failed_grade.model_dump(),
                    "used_model": "none",
                },
                "feedback": {
                    "question_number": qnum,
                    "student_feedback": "This question could not be processed automatically.",
                    "teacher_feedback": f"Automated processing failed: {exc}. Manual review required.",
                },
            },
            "grade": failed_grade,
        }


def run_pipeline(
    image_path: str | list[str],
    grade: bool = True,
    review_mode: str = "auto",
    user_hint: str = "",
    registry=None,
    prepared_extracted: list[dict] | None = None,
    paper_context: dict | None = None,
    recognition_timeout_seconds: float | None = None,
) -> dict:
    """
    入口函数。支持单图或多图（按阅读顺序的路径列表，用于跨页作业）。

    Returns:
        {
          "questions": [ {QuestionData + grading + feedback}, ... ],
          "page_summary": { PageSummary }
        }
    """
    if registry is None:
        registry  = build_registry()
    base_client   = registry[ModelRole.base]
    review_client = registry[ModelRole.review]
    vision_client = registry.get(ModelRole.vision, base_client)
    ocr_client = registry.get(ModelRole.ocr)

    # 构建多 agent 批改客户端（只构建一次）
    try:
        agent_clients = build_grading_agents()
    except Exception as e:
        _log.warning("Multi-agent init failed (%s), falling back to single model", e)
        agent_clients = None

    # solution 生成：fallback 走 deepseek-reasoner（深度但慢）；主路径走 aggregator
    solution_client = _build_solution_client(agent_clients, base_client)
    aggregator_client = _build_aggregator_client(agent_clients, base_client)
    if solution_client is None:
        solution_client = base_client

    import time as _time
    _pipeline_start = _time.monotonic()

    if prepared_extracted is not None:
        extracted_list = list(prepared_extracted)
        _log.info("使用预提取结果，跳过切题 (questions=%d)", len(extracted_list))
    else:
        paths = [image_path] if isinstance(image_path, str) else list(image_path)
        _log.info("加载图片: %s", paths)
        images = [load_image(p) for p in paths]
        for i, im in enumerate(images):
            _log.info("图片 %d 尺寸: %dx%d", i + 1, im.size[0], im.size[1])

        _t0 = _time.monotonic()
        _log.info("切题+提取中... (pages=%d, vision=%s, ocr=%s)",
                  len(images),
                  vision_client.model_id,
                  ocr_client.model_id if ocr_client else "none")
        extracted_list = _segment_with_timeout(
            images,
            vision_client,
            user_hint,
            ocr_client,
            DEFAULT_RECOGNITION_TIMEOUT_SECONDS if recognition_timeout_seconds is None else recognition_timeout_seconds,
        )
        _log.info("识别到 %d 道题 (segmentation: %.1fs)", len(extracted_list), _time.monotonic() - _t0)

    _attach_mark_scheme_contexts(extracted_list, paper_context)

    questions_out: list[dict]    = []
    all_grades:    list[GradeResult] = []

    _t1 = _time.monotonic()
    max_workers = min(len(extracted_list), 4) if extracted_list else 1
    indexed_results: list[dict | None] = [None] * len(extracted_list)
    _QUESTION_TIMEOUT = 60  # seconds per question (reduced for faster overall response)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(
                _process_one_question,
                ext,
                base_client,
                review_client,
                review_mode,
                grade,
                agent_clients,
                solution_client,
                None,
                False,  # sync mode: skip solution to keep response under 30s; frontend calls /explain-question on demand
                aggregator_client,
            ): i
            for i, ext in enumerate(extracted_list)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                indexed_results[idx] = future.result(timeout=_QUESTION_TIMEOUT)
            except Exception as exc:
                _log.warning("Q%s timed out or failed after %ds: %s",
                             extracted_list[idx].get("question_number", "?"), _QUESTION_TIMEOUT, exc)
                qnum = str(extracted_list[idx].get("question_number", "?"))
                indexed_results[idx] = {
                    "record": {
                        "question_number": qnum,
                        "bbox": extracted_list[idx].get("bbox", []),
                        "question_text": extracted_list[idx].get("question_text", ""),
                        "student_answer": extracted_list[idx].get("student_answer", ""),
                        "working_steps": extracted_list[idx].get("working_steps", []),
                        "image_quality": "poor",
                        "confidence": 0.0,
                        "grading": {
                            "question_number": qnum, "is_correct": False, "score": 0.0,
                            "full_score": 0.0, "error_type": "timeout",
                            "knowledge_tags": [], "needs_review": True,
                            "short_feedback": f"批改超时({_QUESTION_TIMEOUT}s)，请重试。",
                            "grading_confidence": 0.0, "used_model": "none",
                            "syllabus_topics": [], "relevant_formulas": [],
                        },
                        "feedback": {
                            "question_number": qnum,
                            "student_feedback": "这道题批改超时，请重新提交。",
                            "teacher_feedback": "自动批改超时，需人工检查。",
                        },
                    },
                    "grade": None,
                }

    _log.info("批改完成 (grading: %.1fs)", _time.monotonic() - _t1)

    for r in indexed_results:
        questions_out.append(r["record"])
        if r.get("grade"):
            all_grades.append(r["grade"])

    # --- 整页汇总 ---
    if grade and all_grades:
        _log.info("生成整页汇总...")
        feedbacks = [
            q["feedback"] for q in questions_out if "feedback" in q
        ]
        summary = build_summary(
            grades    = all_grades,
            feedbacks = feedbacks,
            client    = base_client,
        )
        page_summary = summary.model_dump()
    else:
        page_summary = {}

    _log.info("Pipeline 总耗时: %.1fs", _time.monotonic() - _pipeline_start)
    return {"questions": questions_out, "page_summary": page_summary}


def run_pipeline_streaming(
    image_path: str | list[str],
    grade: bool = True,
    review_mode: str = "auto",
    user_hint: str = "",
    feedback_mode: str = "both",
    registry=None,
    prepared_extracted: list[dict] | None = None,
    paper_context: dict | None = None,
    recognition_timeout_seconds: float | None = None,
    fast_batch: bool = False,
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """
    流式版本的 run_pipeline。
    yield 一系列 (event_type, data_dict) 元组：

    - ``segmentation``：{{ "question_count", "questions_preview" }}
    - ``question``：单题扁平结果（与 QuestionResponse 字段一致）
    - ``summary``：整页汇总 model_dump，无汇总时为 {{}}
    - ``done``：{{}}
    """
    if registry is None:
        registry = build_registry()
    base_client = registry[ModelRole.base]
    review_client = registry[ModelRole.review]
    vision_client = registry.get(ModelRole.vision, base_client)
    ocr_client = registry.get(ModelRole.ocr)

    if fast_batch:
        _log.info("fast_batch enabled: using single-model grading, review off, no inline solution")
        agent_clients = None
        solution_client = None
        aggregator_client = None
        review_mode = "off"
    else:
        # 构建多 agent 批改客户端（只构建一次）
        try:
            agent_clients = build_grading_agents()
        except Exception as e:
            _log.warning("Multi-agent init failed (%s), falling back to single model", e)
            agent_clients = None

        # solution 生成：fallback 走 deepseek-reasoner（深度但慢）；主路径走 aggregator
        solution_client = _build_solution_client(agent_clients, base_client)
        aggregator_client = _build_aggregator_client(agent_clients, base_client)

    if prepared_extracted is not None:
        extracted_list = list(prepared_extracted)
        _log.info("使用预提取结果(流式)，跳过切题 (questions=%d)", len(extracted_list))
    else:
        paths = [image_path] if isinstance(image_path, str) else list(image_path)
        _log.info("加载图片(流式): %s", paths)
        images = [load_image(p) for p in paths]
        for i, im in enumerate(images):
            _log.info("图片 %d 尺寸: %dx%d", i + 1, im.size[0], im.size[1])

        _log.info("切题+提取中... (pages=%d, vision=%s, ocr=%s)",
                  len(images),
                  vision_client.model_id,
                  ocr_client.model_id if ocr_client else "none")
        if fast_batch:
            extracted_list = _segment_fast_batch_individual(
                images,
                vision_client,
                user_hint,
                ocr_client,
                timeout_seconds=recognition_timeout_seconds or FAST_BATCH_PREPARE_TIMEOUT_SECONDS,
            )
        else:
            extracted_list = _segment_with_timeout(
                images,
                vision_client,
                user_hint,
                ocr_client,
                DEFAULT_RECOGNITION_TIMEOUT_SECONDS if recognition_timeout_seconds is None else recognition_timeout_seconds,
            )
        _log.info("识别到 %d 道题", len(extracted_list))

    _attach_mark_scheme_contexts(extracted_list, paper_context)

    yield (
        "segmentation",
        {
            "question_count": len(extracted_list),
            "questions_preview": [str(e.get("question_number", "?")) for e in extracted_list],
            "recognition_timed_out": any(bool(e.get("recognition_timeout")) for e in extracted_list),
        },
    )

    if not extracted_list:
        yield ("summary", {})
        yield ("done", {})
        return

    # 先把题目原文 / 学生答案 / 工作步骤推给前端，用于骨架卡片（让用户等批改时能看到题目）
    for ext in extracted_list:
        yield (
            "question_extracted",
            _stream_question_payload(ext),
        )

    result_queue: queue.Queue[tuple[int | str, dict]] = queue.Queue()
    questions_out: list[dict | None] = [None] * len(extracted_list)
    all_grades: list[GradeResult] = []
    # 用于收集需要生成解题思路的题目信息
    solution_tasks: list[tuple[int, QuestionData, GradeResult]] = []

    def _worker(ext: dict, idx: int) -> None:
        # 不传 solution_client → 跳过解题思路，先快速返回批改结果
        result = _process_one_question(
            ext, base_client, review_client, review_mode, grade,
            agent_clients=agent_clients, solution_client=None,
            progress_queue=result_queue,
            fallback_feedback_llm=not fast_batch,
            fast_batch_mode=fast_batch,
        )
        result_queue.put((idx, result))

    def _handle_question_result(idx: int, result: dict) -> tuple[str, dict[str, Any]]:
        questions_out[idx] = result["record"]
        grade_obj = result.get("grade")
        if grade_obj:
            all_grades.append(grade_obj)
            # 收集需要生成解题思路的信息
            rec = result["record"]
            is_unanswered = (grade_obj.error_type == "unanswered"
                             or not rec.get("student_answer", "").strip())
            # 对做错的题 + 未作答的题自动生成解题思路；做对的题按需前端调用 /explain-question
            if solution_client is not None and not grade_obj.is_correct:
                q = QuestionData(
                    question_number=rec["question_number"],
                    bbox=rec["bbox"],
                    question_text=rec.get("question_text", ""),
                    student_answer=rec.get("student_answer", ""),
                    working_steps=rec.get("working_steps", []),
                    parent_stem=rec.get("parent_stem"),
                    image_quality=rec.get("image_quality", "good"),
                    confidence=rec.get("confidence", 0.9),
                )
                solution_tasks.append((idx, q, grade_obj))

        return (
            "question",
            _flatten_for_stream(result["record"], feedback_mode=feedback_mode),
        )

    def _consume_question_results(
        pending_idxs: set[int],
        deadline: float | None = None,
        preserve_order: bool = False,
        after_first_result_seconds: float | None = None,
    ) -> Generator[tuple[str, dict[str, Any]], None, None]:
        buffered_results: dict[int, dict] = {}
        next_ordered_idx = min(pending_idxs) if pending_idxs else 0
        effective_deadline = deadline
        first_result_seen = False

        def _tighten_after_first_result() -> None:
            nonlocal effective_deadline, first_result_seen
            if first_result_seen or after_first_result_seconds is None:
                return
            first_result_seen = True
            if after_first_result_seconds <= 0:
                return
            after_first_deadline = time.monotonic() + after_first_result_seconds
            if effective_deadline is None:
                effective_deadline = after_first_deadline
            else:
                effective_deadline = min(effective_deadline, after_first_deadline)

        def _drain_ordered() -> Generator[tuple[str, dict[str, Any]], None, None]:
            nonlocal next_ordered_idx
            while next_ordered_idx in buffered_results:
                result = buffered_results.pop(next_ordered_idx)
                if next_ordered_idx in pending_idxs:
                    pending_idxs.remove(next_ordered_idx)
                yield _handle_question_result(next_ordered_idx, result)
                next_ordered_idx += 1

        while pending_idxs:
            timeout: float | None = None
            if effective_deadline is not None:
                timeout = max(0.0, effective_deadline - time.monotonic())
                if timeout <= 0:
                    break
            try:
                item = result_queue.get(timeout=timeout)
            except queue.Empty:
                break

            event_type, data = item

            # agent_progress / agent_step 事件直接转发
            if event_type in {"agent_progress", "agent_step"}:
                yield (event_type, data)
                continue

            # 正常的题目结果（event_type 是 int index）
            idx = int(event_type)
            if idx not in pending_idxs:
                continue
            if preserve_order:
                buffered_results[idx] = data
                for event in _drain_ordered():
                    _tighten_after_first_result()
                    yield event
            else:
                pending_idxs.remove(idx)
                event = _handle_question_result(idx, data)
                _tighten_after_first_result()
                yield event

    max_workers = min(
        len(extracted_list),
        max(1, FAST_BATCH_MAX_WORKERS if fast_batch else 4),
    )
    pending_idxs = set(range(len(extracted_list)))

    if fast_batch:
        limiter = threading.Semaphore(max_workers)

        def _daemon_worker(ext: dict, idx: int) -> None:
            with limiter:
                _worker(ext, idx)

        for i, ext in enumerate(extracted_list):
            threading.Thread(target=_daemon_worker, args=(ext, i), daemon=True).start()

        deadline = time.monotonic() + max(0.1, FAST_BATCH_QUESTION_TIMEOUT_SECONDS)
        yield from _consume_question_results(
            pending_idxs,
            deadline=deadline,
            after_first_result_seconds=FAST_BATCH_AFTER_FIRST_QUESTION_TIMEOUT_SECONDS,
        )
        if pending_idxs:
            emitted_count = len(extracted_list) - len(pending_idxs)
            timeout_seconds = (
                FAST_BATCH_AFTER_FIRST_QUESTION_TIMEOUT_SECONDS
                if emitted_count > 0
                else FAST_BATCH_QUESTION_TIMEOUT_SECONDS
            )
            _log.warning(
                "fast_batch timed out %d/%d questions after %.1fs",
                len(pending_idxs),
                len(extracted_list),
                timeout_seconds,
            )
            for idx in sorted(pending_idxs):
                fallback = _build_fast_batch_timeout_result(
                    extracted_list[idx],
                    timeout_seconds,
                )
                yield _handle_question_result(idx, fallback)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for i, ext in enumerate(extracted_list):
                pool.submit(_worker, ext, i)
            yield from _consume_question_results(pending_idxs, preserve_order=True)

    # --- 并行生成解题思路（不阻塞题目结果的发送）---
    if solution_tasks and (solution_client is not None or aggregator_client is not None):
        import time as _time_sol
        _t_sol_start = _time_sol.monotonic()
        _log.info("开始并行生成 %d 道题的解题思路...", len(solution_tasks))

        def _gen_solution(task_info):
            idx, q, g = task_info
            sol = None
            # 优先 aggregator（5-8s，复用 5 agent 素材）
            if aggregator_client is not None and getattr(g, "_agent_deliberations", None):
                sol = generate_solution_from_deliberations(q, g, aggregator_client)
            # Fallback：从零生成
            if sol is None and solution_client is not None:
                sol = generate_solution(q, g, solution_client)
            return idx, q.question_number, sol

        # idx → qnum 预先映射，超时时也能找回题号 yield null solution
        idx_to_qnum = {t[0]: t[1].question_number for t in solution_tasks}
        with ThreadPoolExecutor(max_workers=min(len(solution_tasks), 4)) as sol_pool:
            future_map = {sol_pool.submit(_gen_solution, t): t[0] for t in solution_tasks}
            for future in as_completed(future_map):
                orig_idx = future_map[future]
                try:
                    # 放宽到 90s：aggregator 通常 5-10s，fallback reasoner 可能 30-60s，留余量
                    idx, qnum, sol = future.result(timeout=90)
                    if questions_out[idx] is not None:
                        questions_out[idx]["solution_text"] = sol
                    yield ("solution", {"question_number": qnum, "solution_text": sol})
                    _log.info("解题思路 Q%s: %s (%.1fs)", qnum, "ok" if sol else "failed",
                              _time_sol.monotonic() - _t_sol_start)
                except Exception as e:
                    # 超时/失败也 yield null solution_text，前端拿到 null 就不会再触发
                    # /explain-question 的级联降级调用，避免把后端打爆成 502
                    qnum = idx_to_qnum.get(orig_idx, "?")
                    _log.warning("解题思路 Q%s 生成失败/超时: %s", qnum, e)
                    if questions_out[orig_idx] is not None:
                        questions_out[orig_idx]["solution_text"] = None
                    yield ("solution", {"question_number": qnum, "solution_text": None})

    if grade and all_grades:
        if fast_batch:
            _log.info("生成整页快评汇总(流式)...")
            yield ("summary", _build_fast_page_summary(all_grades))
        else:
            _log.info("生成整页汇总(流式)...")
            feedbacks = [
                q["feedback"] for q in questions_out if q is not None and "feedback" in q
            ]
            summary = build_summary(
                grades=all_grades,
                feedbacks=feedbacks,
                client=base_client,
            )
            yield ("summary", summary.model_dump())
    else:
        yield ("summary", {})

    yield ("done", {})
