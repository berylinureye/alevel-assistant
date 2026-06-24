"""
路由层：薄适配器，只做收发、校验、调用 pipeline、组装响应。
业务逻辑全部在 pipeline/ grader/ formatter/ 中。
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import queue as stdlib_queue
import tempfile
import threading
from pathlib import Path

_log = logging.getLogger("api.routes")

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from PIL import Image, ImageDraw

from utils.image_utils import _register_optional_image_openers, load_image

from api import upload_cache
from api.feedback import log_ai_event
from api.paper_resolver import (
    build_resolution_steps,
    build_user_hint_with_resolution,
    resolve_paper_context,
)
from api.large_pdf import prepare_large_pdf
import time as _time
from pipeline.segmenter import segment_and_extract
from api.schemas import (
    ChatQuestionRequest,
    ChatQuestionResponse,
    DebugArtifactsResponse,
    DebugSegmentResponse,
    ExplainQuestionRequest,
    ExplainQuestionResponse,
    FeedbackMode,
    GradeQuestionRequest,
    GradeQuestionResponse,
    GradeResultResponse,
    HomeworkResponse,
    OverrideQuestionRequest,
    OverrideQuestionResponse,
    PageSummaryResponse,
    QuestionResponse,
    ReviewMode,
    ReviewQuestionRequest,
    ReviewQuestionResponse,
    RoutingInfoResponse,
)
from formatter.solution import generate_solution_explanation
from grader.grader import grade_question as do_grade
from grader.solution_explainer import generate_solution as _generate_numbered_solution
from models.schemas import GradeResult, QuestionData
from pipeline.pipeline import run_pipeline, run_pipeline_streaming
from router.models import ModelRequest, ModelRole, TaskType, build_registry

router = APIRouter()

# ---------------------------------------------------------------------------
# 常量 & 并发控制
# ---------------------------------------------------------------------------
MAX_FILE_BYTES  = 20 * 1024 * 1024          # 20 MB per uploaded image
# Max pages per /analyze-homework{,-stream} request. Must be kept in sync with
# MAX_FILES in frontend/src/components/UploadForm.tsx — the frontend enforces
# this before upload, the server enforces it as a hard guard.
MAX_PAGES_PER_REQUEST = 24
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "HEIC", "HEIF"}
_pipeline_semaphore = asyncio.Semaphore(2)  # max 2 concurrent pipeline executions
_prepare_semaphore = asyncio.Semaphore(4)   # upload-time extraction is lighter than full pipeline

_register_optional_image_openers()


def _get_registry(request: Request):
    """Get the singleton model registry from app.state, or build a new one."""
    registry = getattr(request.app.state, "registry", None)
    if registry is None:
        registry = build_registry()
    return registry


# ---------------------------------------------------------------------------
# 图像校验（后缀 + 内容双校验）
# ---------------------------------------------------------------------------

async def _validate_image(file: UploadFile) -> bytes:
    data = await file.read()

    if not data:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_IMAGE", "message": "Uploaded file is empty."},
        )
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "FILE_TOO_LARGE", "message": "Max allowed size is 20 MB."},
        )

    suffix = Path(file.filename or "").suffix.lower()

    # 内容校验：PIL 能打开并完整 load；移动端文件名可能没有扩展名，内容识别优先。
    try:
        img = Image.open(io.BytesIO(data))
        detected_format = (img.format or "").upper()
        img.load()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_IMAGE", "message": "File cannot be opened as an image."},
        )

    if suffix not in ALLOWED_SUFFIXES and detected_format not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "UNSUPPORTED_FORMAT",
                "message": f"Unsupported format '{suffix or detected_format or 'unknown'}'. Accepted: jpg, jpeg, png, webp, heic, heif.",
            },
        )

    return data


# ---------------------------------------------------------------------------
# 临时文件管理
# ---------------------------------------------------------------------------

def _write_tempfile(data: bytes, filename: str) -> Path:
    suffix = Path(filename or "upload.jpg").suffix.lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# 适配层：pipeline dict → API schema
# ---------------------------------------------------------------------------

def _flatten_question(q: dict, feedback_mode: FeedbackMode) -> QuestionResponse:
    grading  = q.get("grading", {})
    feedback = q.get("feedback", {})

    routing_info = RoutingInfoResponse(
        used_model         = grading.get("used_model", "unknown"),
        escalated          = bool(grading.get("escalation_reasons", [])),
        escalation_reasons = grading.get("escalation_reasons", []),
    )

    student_fb: str | None = feedback.get("student_feedback")
    teacher_fb: str | None = feedback.get("teacher_feedback")

    if feedback_mode == FeedbackMode.student:
        teacher_fb = None
    elif feedback_mode == FeedbackMode.teacher:
        student_fb = None

    # Keep LaTeX in all fields — frontend KaTeX renderer handles $...$
    return QuestionResponse(
        question_number    = q.get("question_number", ""),
        bbox               = q.get("bbox", []),
        question_text      = q.get("question_text", ""),
        parent_stem        = q.get("parent_stem") or None,
        student_answer     = q.get("student_answer", ""),
        working_steps      = q.get("working_steps", []),
        image_quality      = q.get("image_quality", ""),
        confidence         = float(q.get("confidence", 0.0)),
        is_correct         = bool(grading.get("is_correct", False)),
        grading_confidence = float(grading.get("grading_confidence", 0.0)),
        score              = float(grading.get("score", 0.0)),
        full_score         = float(grading.get("full_score", 0.0)),
        error_type         = grading.get("error_type"),
        knowledge_tags     = grading.get("knowledge_tags", []),
        needs_review       = bool(grading.get("needs_review", False)),
        short_feedback     = grading.get("short_feedback", ""),
        escalation_reasons = grading.get("escalation_reasons", []),
        syllabus_topics    = grading.get("syllabus_topics", []),
        relevant_formulas  = grading.get("relevant_formulas", []),
        correct_answer     = grading.get("correct_answer"),
        unanswered         = bool(grading.get("unanswered", False)),
        detail_deductions  = grading.get("detail_deductions", []) or [],
        solution_text      = q.get("solution_text"),
        grading_route      = q.get("grading_route"),
        mark_scheme_confidence = q.get("mark_scheme_confidence"),
        mark_scheme_context_error = q.get("mark_scheme_context_error"),
        questionbank_question_id = q.get("questionbank_question_id"),
        questionbank_match_confidence = q.get("questionbank_match_confidence"),
        student_feedback   = student_fb,
        teacher_feedback   = teacher_fb,
        routing_info       = routing_info,
    )


def _fallback_page_summary(questions: list[QuestionResponse]) -> PageSummaryResponse:
    total = len(questions)
    correct = sum(1 for q in questions if q.is_correct)
    unanswered = sum(1 for q in questions if q.unanswered)
    review = sum(1 for q in questions if q.needs_review)
    incorrect = total - correct - unanswered

    score_total = sum(float(q.score or 0.0) for q in questions)
    full_score_total = sum(float(q.full_score or 0.0) for q in questions)

    error_types: list[str] = []
    knowledge_counts: dict[str, int] = {}
    for q in questions:
        if not q.is_correct and q.error_type:
            error_types.append(q.error_type)
        for tag in (q.knowledge_tags or []):
            knowledge_counts[tag] = knowledge_counts.get(tag, 0) + 1

    return PageSummaryResponse(
        total_questions=total,
        correct_count=correct,
        incorrect_count=incorrect,
        unanswered_count=unanswered,
        review_count=review,
        score_total=score_total,
        full_score_total=full_score_total,
        common_error_types=error_types,
        knowledge_tags_summary=knowledge_counts,
        overall_teacher_comment="",
        estimated_review_minutes=0,
        priority_topics=[],
    )

# ---------------------------------------------------------------------------
# Debug artifacts（失败只降级，不影响主响应）
# ---------------------------------------------------------------------------

def _build_debug_artifacts(
    image_data: bytes,
    raw: dict,
) -> DebugArtifactsResponse | None:
    segments = [
        DebugSegmentResponse(
            question_number = q.get("question_number", ""),
            bbox            = q.get("bbox", []),
        )
        for q in raw.get("questions", [])
    ]

    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        draw = ImageDraw.Draw(img)
        for seg in segments:
            if len(seg.bbox) == 4:
                draw.rectangle(seg.bbox, outline="red", width=3)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        annotated: str | None = b64
    except Exception:
        # annotation 失败：降级，不阻断响应
        annotated = None

    try:
        img_meta = Image.open(io.BytesIO(image_data))
        size = [img_meta.width, img_meta.height]
    except Exception:
        size = [0, 0]

    return DebugArtifactsResponse(
        image_size          = size,
        segments            = segments,
        annotated_image_b64 = annotated,
    )


def _to_grade_response(r: GradeResult) -> GradeResultResponse:
    return GradeResultResponse(
        question_number=r.question_number,
        question_type=r.question_type.value,
        is_correct=r.is_correct,
        score=r.score,
        full_score=r.full_score,
        error_type=r.error_type,
        knowledge_tags=r.knowledge_tags,
        needs_review=r.needs_review,
        short_feedback=r.short_feedback,
        grading_confidence=r.grading_confidence,
    )


# ---------------------------------------------------------------------------
# 上传时预提取（减少点击"开始批改"后的等待时间）
# ---------------------------------------------------------------------------

def _do_prepare_extract(path: str, user_hint: str, registry) -> dict:
    img = load_image(path)
    vision_client = registry.get(ModelRole.vision) or registry[ModelRole.base]
    ocr_client = registry.get(ModelRole.ocr)
    extracted = segment_and_extract(
        [img], vision_client, user_hint=user_hint, ocr_client=ocr_client,
    )
    # Probe page header (same OCR pass used by group_pages_by_continuity)
    # so that _resolve_prepared can later decide whether this uploaded image
    # is a fresh-question page or a pure answer-continuation page. Single-
    # image segment_and_extract doesn't have cross-image context, so we
    # stash the "header starts with a numbered question" signal here.
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
    return {"extracted": extracted, "starts_with_qnum": starts_with_qnum}


@router.post("/prepare-upload", tags=["homework"])
async def prepare_upload(
    request: Request,
    image: UploadFile = File(..., description="Single image to pre-extract at upload time"),
    user_hint: str = Form("", description="Optional hint for question location"),
) -> dict:
    data = await _validate_image(image)
    tmp = _write_tempfile(data, image.filename or "upload.jpg")
    registry = _get_registry(request)
    try:
        async with _prepare_semaphore:
            probe = await run_in_threadpool(
                _do_prepare_extract, str(tmp), user_hint.strip(), registry,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error_code": "PREPARE_ERROR", "message": str(exc)},
        )
    finally:
        tmp.unlink(missing_ok=True)

    extracted = probe["extracted"]
    upload_id = upload_cache.store(
        extracted,
        user_hint=user_hint.strip(),
        starts_with_qnum=probe.get("starts_with_qnum"),
    )
    return {
        "status": "ready",
        "upload_id": upload_id,
        "question_count": len(extracted),
    }


@router.post("/large-pdf/prepare", tags=["large-pdf"])
async def prepare_large_pdf_upload(
    pdf: UploadFile = File(..., description="Full or partial Past Paper PDF"),
    upload_intent: str = Form("full_past_paper_pdf"),
    paper_code: str = Form(""),
    question_numbers: str = Form(""),
) -> dict:
    data = await pdf.read()
    if not data:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_PDF", "message": "Uploaded PDF is empty."},
        )

    tmp = _write_tempfile(data, pdf.filename or "upload.pdf")
    try:
        return prepare_large_pdf(
            tmp,
            filename=pdf.filename or "upload.pdf",
            upload_intent=upload_intent,
            paper_code=paper_code,
            question_numbers=question_numbers,
            delete_on_remove=True,
        )
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _resolve_prepared(upload_ids_raw: str) -> list[dict] | None:
    """Parse comma-separated upload_ids and concatenate cached extractions.
    Returns None if any id is missing/expired (caller falls back to full pipeline).

    Each cached extraction was produced from a single image and its items carry
    ``page=1`` (page-local). When we stitch N uploads back together, we overwrite
    ``page`` with the global 1-based index that matches the client's upload
    order — otherwise every question from every image ends up tagged page=1 and
    the frontend labels them all "图片 1-X" (losing the original image order and
    breaking the 点击查看原始图片 link).

    Also runs cross-image ``_attach_parent_stems`` on the merged list so:
      (1) orphan sub-questions on page N+1 ("(c)" with no stem) inherit the
          parent stem from the Q on page N that printed the setup;
      (2) answer-only pages (student's handwriting spilling onto the next page
          with no printed question text) get merged into the preceding question's
          ``student_answer``/``working_steps`` instead of surfacing as a phantom
          "图片 N-1 错误 0/0 识别 0%" card.
    This is critical because each image went through segmenter in isolation via
    /prepare-upload, so no cross-image context exists until here.
    """
    if not upload_ids_raw.strip():
        return None
    ids = [x.strip() for x in upload_ids_raw.split(",") if x.strip()]
    merged: list[dict] = []
    for idx, uid in enumerate(ids):
        entry = upload_cache.pop(uid)
        if not entry:
            return None
        global_page = idx + 1
        # An image uploaded *after* the first one whose OCR'd header did NOT
        # start with a numbered question is a pure answer-continuation page.
        # Tag its items so _merge_cross_page_answers can recognise them via
        # its `_continuation_page` priority-3 path. The first image (idx=0)
        # is never a continuation regardless of its header.
        starts_with_qnum = entry.get("starts_with_qnum")
        is_continuation = (idx > 0) and (starts_with_qnum is False)
        for item in entry["extracted"]:
            item["page"] = global_page
            if is_continuation:
                item["_continuation_page"] = True
        merged.extend(entry["extracted"])

    # Cross-image post-processing — otherwise answer-only / label-only orphan
    # pages never get their context.
    try:
        from pipeline.segmenter import _attach_parent_stems
        _attach_parent_stems(merged)
    except Exception as exc:
        import logging
        logging.getLogger("api.routes").warning(
            "cross-image _attach_parent_stems failed, using raw merged: %s", exc
        )

    return merged


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@router.post(
    "/analyze-homework",
    response_model=HomeworkResponse,
    responses={
        400: {"model": None, "description": "INVALID_IMAGE / UNSUPPORTED_FORMAT / FILE_TOO_LARGE"},
        422: {"description": "VALIDATION_ERROR (FastAPI auto)"},
        500: {"model": None, "description": "PIPELINE_ERROR"},
    },
)
async def analyze_homework(
    request:         Request,
    image:           list[UploadFile] = File(...,          description="Homework page image(s), 1-5 files for multi-page (jpg/png/webp/heic/heif, ≤20 MB each)"),
    feedback_mode:   FeedbackMode = Form(FeedbackMode.both, description="student | teacher | both"),
    review_mode:    ReviewMode    = Form(ReviewMode.auto,  description="auto | force | off"),
    debug_visualize: bool         = Form(False,        description="Return annotated debug image"),
    user_hint: str = Form("", description="Optional hint for the AI, e.g. 'Grade the questions circled in red pen, my answers are written in pencil next to them'"),
    upload_ids: str = Form("", description="Optional comma-separated upload_ids from /prepare-upload; skips re-extraction"),
    upload_intent: str = Form("unknown", description="unknown | past_paper | custom_homework | answer_pages_only"),
    paper_code: str = Form("", description="Optional CAIE paper code, e.g. 9709/12/M/J/16"),
    question_numbers: str = Form("", description="Optional comma-separated question numbers to prioritise"),
) -> HomeworkResponse:

    files = image if isinstance(image, list) else [image]
    if not files:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_IMAGE", "message": "No image uploaded."},
        )
    if len(files) > MAX_PAGES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "TOO_MANY_FILES",
                "message": f"Max {MAX_PAGES_PER_REQUEST} pages per request.",
            },
        )

    registry = _get_registry(request)

    tmps: list[Path] = []
    first_image_data: bytes = b""
    total_bytes = 0
    for i, f in enumerate(files):
        data = await _validate_image(f)
        total_bytes += len(data)
        if i == 0:
            first_image_data = data
        tmps.append(_write_tempfile(data, f.filename or "upload.jpg"))

    prepared = _resolve_prepared(upload_ids)
    paper_resolution = resolve_paper_context(
        upload_intent=upload_intent,
        paper_code=paper_code,
        question_numbers=question_numbers,
        page_count=len(files),
    )
    paper_pipeline_context = paper_resolution.pipeline_context()
    effective_user_hint = build_user_hint_with_resolution(user_hint, paper_resolution)

    log_ai_event("upload_received", 0, {
        "pages": len(files),
        "total_bytes": total_bytes,
        "review_mode": review_mode.value,
        "has_hint": bool(user_hint.strip()),
        "prepared": bool(prepared),
        "stream": False,
        "paper_resolution": paper_resolution.event_detail(),
    })

    _t_session = _time.perf_counter()
    try:
        async with _pipeline_semaphore:
            raw: dict = await run_in_threadpool(
                run_pipeline,
                [str(t) for t in tmps],
                True,
                review_mode.value,
                effective_user_hint,
                registry,
                prepared,
                paper_pipeline_context,
            )
    except Exception as exc:
        log_ai_event("pipeline_error", int((_time.perf_counter() - _t_session) * 1000), {
            "message": str(exc)[:500],
            "pages": len(files),
        })
        raise HTTPException(
            status_code=500,
            detail={"error_code": "PIPELINE_ERROR", "message": str(exc)},
        )
    finally:
        for t in tmps:
            t.unlink(missing_ok=True)

    questions = [
        _flatten_question(q, feedback_mode)
        for q in raw.get("questions", [])
    ]

    # 批改事件：每题一条（便于计算正确率、错误类型分布）
    try:
        for q in raw.get("questions", []):
            grade = q.get("grade_result") or {}
            is_correct = grade.get("is_correct")
            is_unanswered = bool(q.get("is_unanswered") or grade.get("is_unanswered"))
            if is_unanswered:
                log_ai_event("question_unanswered", 0, {
                    "question_type": q.get("question_type"),
                })
                continue
            log_ai_event("question_graded", 0, {
                "is_correct": is_correct,
                "score": grade.get("score"),
                "error_type": grade.get("error_type"),
                "question_type": q.get("question_type"),
                "escalated": bool(q.get("escalated") or grade.get("escalated")),
                "model": (q.get("routing_info") or {}).get("model"),
            })
            if q.get("solution_text"):
                log_ai_event("solution_inline_done", 0, {
                    "question_type": q.get("question_type"),
                    "is_correct": is_correct,
                })
        log_ai_event("session_done", int((_time.perf_counter() - _t_session) * 1000), {
            "questions": len(raw.get("questions", [])),
            "pages": len(files),
            "stream": False,
        })
    except Exception as _exc:
        _log.warning("telemetry emit failed: %s", _exc)

    # page_summary 最低契约：即使 pipeline 没产出，也保证 API 响应全字段可用
    page_summary_payload = raw.get("page_summary") or {}
    try:
        page_summary = PageSummaryResponse(**page_summary_payload)
    except Exception:
        page_summary = _fallback_page_summary(questions)

    debug: DebugArtifactsResponse | None = None
    if debug_visualize:
        # Debug artifacts use first page only
        debug = await run_in_threadpool(_build_debug_artifacts, first_image_data, raw)

    return HomeworkResponse(
        status          = "success",
        questions       = questions,
        page_summary    = page_summary,
        debug_artifacts = debug,
    )


@router.post(
    "/analyze-homework-stream",
    tags=["homework"],
    responses={
        400: {"description": "INVALID_IMAGE / UNSUPPORTED_FORMAT / FILE_TOO_LARGE"},
        200: {"description": "text/event-stream (SSE): segmentation | question | summary | done | error"},
    },
)
async def analyze_homework_stream(
    request: Request,
    image: list[UploadFile] = File(..., description="Homework page image(s), 1-5 files for multi-page (jpg/png/webp/heic/heif, ≤20 MB each)"),
    feedback_mode: FeedbackMode = Form(FeedbackMode.both, description="student | teacher | both"),
    review_mode: ReviewMode = Form(ReviewMode.auto, description="auto | force | off"),
    user_hint: str = Form("", description="Optional hint for locating questions/answers on the page"),
    upload_ids: str = Form("", description="Optional comma-separated upload_ids from /prepare-upload; skips re-extraction"),
    upload_intent: str = Form("unknown", description="unknown | past_paper | custom_homework | answer_pages_only"),
    paper_code: str = Form("", description="Optional CAIE paper code, e.g. 9709/12/M/J/16"),
    question_numbers: str = Form("", description="Optional comma-separated question numbers to prioritise"),
) -> StreamingResponse:
    files = image if isinstance(image, list) else [image]
    if not files:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_IMAGE", "message": "No image uploaded."},
        )
    if len(files) > MAX_PAGES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "TOO_MANY_FILES",
                "message": f"Max {MAX_PAGES_PER_REQUEST} pages per request.",
            },
        )
    registry = _get_registry(request)
    tmps: list[Path] = []
    total_bytes = 0
    for f in files:
        data = await _validate_image(f)
        total_bytes += len(data)
        tmps.append(_write_tempfile(data, f.filename or "upload.jpg"))

    prepared = _resolve_prepared(upload_ids)
    paper_resolution = resolve_paper_context(
        upload_intent=upload_intent,
        paper_code=paper_code,
        question_numbers=question_numbers,
        page_count=len(files),
    )
    paper_pipeline_context = paper_resolution.pipeline_context()
    effective_user_hint = build_user_hint_with_resolution(user_hint, paper_resolution)

    log_ai_event("upload_received", 0, {
        "pages": len(files),
        "total_bytes": total_bytes,
        "review_mode": review_mode.value,
        "has_hint": bool(user_hint.strip()),
        "prepared": bool(prepared),
        "stream": True,
        "paper_resolution": paper_resolution.event_detail(),
    })
    _t_session = _time.perf_counter()

    async def event_generator():
        """后台线程跑 pipeline，经 queue 逐事件推到 SSE（真流式，非 list 缓冲）。"""
        for step in build_resolution_steps(paper_resolution):
            yield (
                "event: agent_step\ndata: "
                f"{json.dumps(step, ensure_ascii=False)}\n\n"
            )

        q: stdlib_queue.Queue[
            tuple[str, dict] | None
        ] = stdlib_queue.Queue()

        def _run_pipeline() -> None:
            try:
                for event_type, data in run_pipeline_streaming(
                    [str(t) for t in tmps],
                    True,
                    review_mode.value,
                    effective_user_hint,
                    feedback_mode.value,
                    registry=registry,
                    prepared_extracted=prepared,
                    paper_context=paper_pipeline_context,
                ):
                    q.put((event_type, data))
            except Exception as exc:
                q.put(("error", {"message": str(exc)}))
            finally:
                q.put(None)
                for t in tmps:
                    t.unlink(missing_ok=True)

        threading.Thread(target=_run_pipeline, daemon=True).start()

        nonlocal_qc = {"n": 0}
        try:
            while True:
                item = await asyncio.to_thread(q.get)
                if item is None:
                    break
                event_type, data = item
                # 埋点：按事件类型分发
                try:
                    if event_type == "question":
                        nonlocal_qc["n"] += 1
                        grade = (data or {}).get("grade_result") or {}
                        if (data or {}).get("is_unanswered") or grade.get("is_unanswered"):
                            log_ai_event("question_unanswered", 0, {
                                "question_type": (data or {}).get("question_type"),
                            })
                        else:
                            log_ai_event("question_graded", 0, {
                                "is_correct": grade.get("is_correct"),
                                "score": grade.get("score"),
                                "error_type": grade.get("error_type"),
                                "question_type": (data or {}).get("question_type"),
                                "escalated": bool((data or {}).get("escalated") or grade.get("escalated")),
                                "model": ((data or {}).get("routing_info") or {}).get("model"),
                            })
                            if (data or {}).get("solution_text"):
                                log_ai_event("solution_inline_done", 0, {
                                    "question_type": (data or {}).get("question_type"),
                                    "is_correct": grade.get("is_correct"),
                                })
                    elif event_type == "segmentation":
                        log_ai_event("segment_done", 0, {
                            "questions": len((data or {}).get("questions", [])) if isinstance(data, dict) else 0,
                        })
                    elif event_type == "error":
                        log_ai_event("pipeline_error", int((_time.perf_counter() - _t_session) * 1000), {
                            "message": str((data or {}).get("message", ""))[:500],
                        })
                except Exception as _texc:
                    _log.warning("telemetry emit failed (stream): %s", _texc)

                yield (
                    f"event: {event_type}\ndata: "
                    f"{json.dumps(data, ensure_ascii=False)}\n\n"
                )
            log_ai_event("session_done", int((_time.perf_counter() - _t_session) * 1000), {
                "questions": nonlocal_qc["n"],
                "pages": len(files),
                "stream": True,
            })
        except Exception as exc:
            log_ai_event("pipeline_error", int((_time.perf_counter() - _t_session) * 1000), {
                "message": str(exc)[:500],
            })
            yield (
                "event: error\ndata: "
                f"{json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/grade-question",
    response_model=GradeQuestionResponse,
    tags=["single-question"],
    responses={500: {"description": "GRADING_ERROR"}},
)
async def grade_single_question(body: GradeQuestionRequest, request: Request) -> GradeQuestionResponse:
    registry = _get_registry(request)
    base_client = registry[ModelRole.base]

    question_data = QuestionData(
        question_number=body.question_number,
        bbox=[],
        question_text=body.question_text,
        student_answer=body.student_answer,
        working_steps=body.working_steps,
        image_quality=body.image_quality,
        confidence=body.confidence,
    )

    try:
        result = await run_in_threadpool(do_grade, question_data, base_client, TaskType.grade)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error_code": "GRADING_ERROR", "message": str(exc)})

    return GradeQuestionResponse(
        grade_result=_to_grade_response(result),
        used_model=base_client.model_id,
    )


@router.post(
    "/review-question",
    response_model=ReviewQuestionResponse,
    tags=["single-question"],
    responses={500: {"description": "REVIEW_ERROR"}},
)
async def review_single_question(body: ReviewQuestionRequest, request: Request) -> ReviewQuestionResponse:
    registry = _get_registry(request)
    base_client = registry[ModelRole.base]
    review_client = registry[ModelRole.review]

    question_data = QuestionData(
        question_number=body.question_number,
        bbox=[],
        question_text=body.question_text,
        student_answer=body.student_answer,
        working_steps=body.working_steps,
        image_quality=body.image_quality,
        confidence=body.confidence,
    )

    try:
        base_resp = None
        if body.include_base:
            base_result = await run_in_threadpool(do_grade, question_data, base_client, TaskType.grade)
            base_resp = _to_grade_response(base_result)

        review_result = await run_in_threadpool(do_grade, question_data, review_client, TaskType.review)
        review_resp = _to_grade_response(review_result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error_code": "REVIEW_ERROR", "message": str(exc)})

    notes: list[str] = []
    if base_resp:
        if base_resp.is_correct != review_resp.is_correct:
            notes.append(f"correctness_changed: {base_resp.is_correct} -> {review_resp.is_correct}")
        if abs(base_resp.score - review_resp.score) > 0.01:
            notes.append(f"score_changed: {base_resp.score} -> {review_resp.score}")
        if base_resp.error_type != review_resp.error_type:
            notes.append(f"error_type_changed: {base_resp.error_type} -> {review_resp.error_type}")

    return ReviewQuestionResponse(
        base_result=base_resp,
        review_result=review_resp,
        final_result=review_resp,
        review_notes=notes,
    )


@router.post(
    "/override-question-result",
    response_model=OverrideQuestionResponse,
    tags=["preview"],
)
async def override_question_result(body: OverrideQuestionRequest) -> OverrideQuestionResponse:
    override_fields = ["is_correct", "score", "full_score", "error_type",
                       "student_feedback", "teacher_feedback", "teacher_note"]

    overridden: list[str] = []
    result: dict = {"question_number": body.question_number}

    for field in override_fields:
        value = getattr(body, field)
        if value is not None:
            overridden.append(field)
            result[field] = value

    return OverrideQuestionResponse(
        question_number=body.question_number,
        overridden_fields=overridden,
        result=result,
    )


_CHAT_SYSTEM_CONTEXT = """\
你是一位耐心的 A-Level 数学老师，正在帮 16-18 岁学生就一道题做**定点追问**。

题目背景：
  题目：{question_text}
  学生答案：{student_answer}
  错误类型：{error_type}

{solution_section}

【铁律 — 所有回复都必须遵守（违反即重写）】
- 只回答学生追问的**那一个点**，答完就停
- 绝不主动延伸到后续解题步骤，也不要顺手把整道题重做一遍
- 专业术语后紧跟"也就是说 ……"用一句大白话翻译
- 所有数学符号 / 变量 / 希腊字母 / 公式都用 LaTeX 写在 $...$ 里
  （例：$\\frac{{dy}}{{dx}}$、$x^2$、$\\alpha$、$\\int f(x)\\,dx$）
- 不使用 Markdown 语法（不要 **、##、``` 之类）
- 中文回答；正文 ≤ 200 字（公式不算字数）
- **结尾必须**以一句话确认学生是否跟上（如"这一步看懂了吗？"、"到这里 OK 吗？"）
  —— 前端会依赖这个问句来显示"听懂了 / 换个方式"按钮，缺失就算违规

【A-Level 大纲方法优先】
- 只用 A-Level（16-18 岁高中）大纲内的公式和方法讲解，不要退回 GCSE / 初中方法
- 有等价多解时，优先走"标准公式"一步到位，不要绕弯子用更基础的工具拼装
- 典型偏好：
  * 三角形面积 → $\\frac{{1}}{{2}}ab\\sin C$（等边三角形取 $C=60°$、$a=b=$ 边长，
    直接得 $\\frac{{\\sqrt{{3}}}}{{4}}a^2$）；**不要**先用勾股定理求高再 $\\frac{{1}}{{2}}\\times$ 底 $\\times$ 高
  * 正弦 / 余弦定理 优于几何辅助线
  * 求导用 链式 / 乘法 / 商法则，不用 first principles 极限
  * 期望 / 方差用 $E[X]$、$\\text{{Var}}(X)$ 公式，不手动逐项展开
  * 两点距离用距离公式；两向量夹角用点积公式

【本轮讲解策略（第 {level_name}）】
{level_rules}
"""

# Layer 1：默认。拆细步骤 + 代入具体数字
_LEVEL_1_RULES = """\
把学生问的那个点拆成 2-3 个最小动作，每步只做一件事：
- 每一步都**代入具体数字**演示中间过程，不要只写抽象字母
- 不要跳步，所有中间等式都写出来
- 如果学生的点本身已经很小，就把过程写得更细、更慢
"""

# Layer 2：学生点了"换个方式" 1 次
_LEVEL_2_RULES = """\
学生说上一版没懂，这次必须换一种**明显不同**的讲法，从下列任选 1-2 种组合：
  A) 换更简单的数字（如把 $3x^2+5xy$ 换成 $x^2+y$）重新举例
  B) 换切入角度：上次从定义讲，这次从几何意义 / 实际意义讲
  C) 倒着讲：先给出最终结果，再反推每一步怎么得到
  D) "做了 vs 没做"对比，凸显这一步的作用
  E) 把上次 3 步的推导再拆成 5 步，每步更小
禁止原文复述上一版；仍然要代入具体数字，不要只写字母。
"""

# Layer 3：学生点了"换个方式" 2 次及以上
_LEVEL_3_RULES = """\
学生连续两次没懂，很可能**前置知识**缺失。不要继续正面硬讲原题那个点。
1) 先判断：要理解这个点，学生需要先懂哪 1-2 个前置概念？
2) 用提问方式确认，例如："我想先确认一下，你知道 $\\text{{XX}}$ 是什么意思吗？"
3) 如果能推测他大概率卡在哪个前置，就**直接从那个基础概念讲起**：
   - 用最简单的数字举例
   - 一步只做一件事
   - 从这个基础概念慢慢搭回原来问的那个点
语气要让学生放心：不懂很正常，我们退一步从头来。
"""


def _build_chat_system(
    *,
    question_text: str,
    student_answer: str,
    error_type: str,
    solution_section: str,
    explain_level: int,
) -> str:
    level = max(1, min(3, int(explain_level or 1)))
    level_rules = {1: _LEVEL_1_RULES, 2: _LEVEL_2_RULES, 3: _LEVEL_3_RULES}[level]
    level_name = {1: "1 层：拆细步骤", 2: "2 层：换数字 / 换角度",
                  3: "3 层：回退前置知识"}[level]
    return _CHAT_SYSTEM_CONTEXT.format(
        question_text=question_text,
        student_answer=student_answer,
        error_type=error_type,
        solution_section=solution_section,
        level_name=level_name,
        level_rules=level_rules,
    )


@router.post(
    "/explain-question",
    response_model=ExplainQuestionResponse,
    tags=["interactive"],
    responses={500: {"description": "EXPLAIN_ERROR"}},
)
async def explain_question(body: ExplainQuestionRequest, request: Request) -> ExplainQuestionResponse:
    registry = _get_registry(request)
    explain_client = registry[ModelRole.explain]

    _t0 = _time.perf_counter()

    # 新路径：复用 grader.solution_explainer.generate_solution 的 PROMPT_E 编号列表流程
    # （所有数学内容强制 $...$ 包裹 + SymPy 验证 + 结构检查 + 禁止内容拦截）
    # 构造 QuestionData / GradeResult 代理对象喂进去，避开旧 formatter.solution 的
    # "关键思路/第N步/易错提醒" 冗长模板（输出常常漏 $ 导致乱码）
    def _run_numbered() -> str | None:
        from models.schemas import GradeResult, QuestionData, QuestionType
        q = QuestionData(
            question_number="explain",
            bbox=[0, 0, 1, 1],
            question_text=body.question_text or "",
            student_answer=body.student_answer or "",
            working_steps=list(body.working_steps or []),
            image_quality="good",
            confidence=0.9,
        )
        g = GradeResult(
            question_number="explain",
            question_type=QuestionType.unknown,
            is_correct=bool(body.is_correct),
            score=float(body.score or 0.0),
            full_score=float(body.full_score or 1.0),
            error_type=body.error_type or "unknown",
            knowledge_tags=[],
            needs_review=False,
            short_feedback="",
            grading_confidence=0.8,
            correct_answer=body.correct_answer,
            syllabus_topics=[],
            relevant_formulas=[],
        )
        return _generate_numbered_solution(q, g, explain_client, timeout=45)

    explanation: str | None = None
    try:
        explanation = await run_in_threadpool(_run_numbered)
    except Exception as exc:
        _log.warning("numbered solution path failed: %s", exc)
        explanation = None

    # Fallback：只有新路径彻底失败才落到老的 generate_solution_explanation
    if not explanation:
        try:
            explanation = await run_in_threadpool(
                generate_solution_explanation,
                question_text=body.question_text,
                student_answer=body.student_answer,
                working_steps=body.working_steps,
                is_correct=body.is_correct,
                error_type=body.error_type,
                score=body.score,
                full_score=body.full_score,
                correct_answer=body.correct_answer,
                client=explain_client,
            )
        except Exception as exc:
            log_ai_event("explain_question", int((_time.perf_counter() - _t0) * 1000), {"status": "error"})
            raise HTTPException(
                status_code=500,
                detail={"error_code": "EXPLAIN_ERROR", "message": str(exc)},
            )

    log_ai_event(
        "explain_question",
        int((_time.perf_counter() - _t0) * 1000),
        {"status": "ok", "model": explain_client.model_id, "reply_len": len(explanation or "")},
    )
    return ExplainQuestionResponse(solution_explanation=explanation)


@router.post(
    "/chat-question",
    response_model=ChatQuestionResponse,
    tags=["interactive"],
    responses={500: {"description": "CHAT_ERROR"}},
)
async def chat_question(body: ChatQuestionRequest, request: Request) -> ChatQuestionResponse:
    registry = _get_registry(request)
    explain_client = registry[ModelRole.explain]

    solution_section = ""
    if body.solution_context:
        solution_section = f"解题思路参考：\n{body.solution_context}\n"

    system_context = _build_chat_system(
        question_text=body.question_text,
        student_answer=body.student_answer or "(未作答)",
        error_type=body.error_type or "无",
        solution_section=solution_section,
        explain_level=getattr(body, "explain_level", 1) or 1,
    )

    conversation_text = system_context + "\n以下是和学生的对话：\n"
    for msg in body.conversation:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            conversation_text += f"\n学生：{content}"
        else:
            conversation_text += f"\n老师：{content}"

    conversation_text += f"\n学生：{body.new_message}\n老师："

    request = ModelRequest(
        task=TaskType.grade,
        prompt=conversation_text,
        max_tokens=4096,
    )

    _t0 = _time.perf_counter()
    try:
        reply = await run_in_threadpool(explain_client.call, request)
        reply = reply.strip()
        # 走同一套 LaTeX 清洗：去犹豫词 + \(..\) → $..$ + 裸 LaTeX 包裹
        # + 畸形 $ 清理 + 纯数学行重包 + 奇数 $ 兜底
        from grader.solution_verifier import clean_solution_output
        reply = clean_solution_output(reply)
    except Exception as exc:
        log_ai_event("chat_question", int((_time.perf_counter() - _t0) * 1000), {"status": "error"})
        raise HTTPException(
            status_code=500,
            detail={"error_code": "CHAT_ERROR", "message": str(exc)},
        )

    log_ai_event(
        "chat_question",
        int((_time.perf_counter() - _t0) * 1000),
        {
            "status": "ok",
            "model": explain_client.model_id,
            "reply_len": len(reply or ""),
            "turn_count": len(body.conversation) + 1,
            "explain_level": getattr(body, "explain_level", 1) or 1,
        },
    )
    return ChatQuestionResponse(reply=reply)


@router.post(
    "/chat-question/stream",
    tags=["interactive"],
    responses={
        200: {"description": "text/event-stream (SSE): chunk | done | error"},
    },
)
async def chat_question_stream(body: ChatQuestionRequest, request: Request) -> StreamingResponse:
    """
    流式版追问：SSE 推送 chunk 片段，前端边收边渲染，避免用户看"思考中…"转半天。
    事件格式：
      event: chunk  data: {"text": "..."}
      event: done   data: {"final": "..."}   （完整清洗后的回复）
      event: error  data: {"message": "..."}
    """
    registry = _get_registry(request)
    explain_client = registry[ModelRole.explain]

    solution_section = ""
    if body.solution_context:
        solution_section = f"解题思路参考：\n{body.solution_context}\n"

    system_context = _build_chat_system(
        question_text=body.question_text,
        student_answer=body.student_answer or "(未作答)",
        error_type=body.error_type or "无",
        solution_section=solution_section,
        explain_level=getattr(body, "explain_level", 1) or 1,
    )

    conversation_text = system_context + "\n以下是和学生的对话：\n"
    for msg in body.conversation:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            conversation_text += f"\n学生：{content}"
        else:
            conversation_text += f"\n老师：{content}"
    conversation_text += f"\n学生：{body.new_message}\n老师："

    model_req = ModelRequest(
        task=TaskType.grade,
        prompt=conversation_text,
        max_tokens=4096,
    )

    async def event_gen():
        import asyncio as _asyncio
        import json as _json
        from grader.solution_verifier import clean_solution_output as _clean

        _t0 = _time.perf_counter()
        buffer: list[str] = []
        loop = _asyncio.get_event_loop()

        # 把同步 generator 桥到异步：同步线程跑 client.stream，
        # 用 call_soon_threadsafe 把每个 chunk 传回事件循环的 queue
        queue: _asyncio.Queue = _asyncio.Queue()

        def _drain_sync():
            try:
                for piece in explain_client.stream(model_req):
                    loop.call_soon_threadsafe(queue.put_nowait, ("chunk", piece))
            except Exception as exc:  # noqa: BLE001
                loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("__end__", None))

        import threading as _th
        _th.Thread(target=_drain_sync, daemon=True).start()

        try:
            while True:
                kind, payload = await queue.get()
                if kind == "chunk":
                    buffer.append(payload)
                    yield f"event: chunk\ndata: {_json.dumps({'text': payload}, ensure_ascii=False)}\n\n"
                elif kind == "error":
                    log_ai_event(
                        "chat_question_stream",
                        int((_time.perf_counter() - _t0) * 1000),
                        {"status": "error"},
                    )
                    yield f"event: error\ndata: {_json.dumps({'message': payload}, ensure_ascii=False)}\n\n"
                    return
                elif kind == "__end__":
                    break

            raw = "".join(buffer).strip()
            final = _clean(raw) if raw else ""
            yield f"event: done\ndata: {_json.dumps({'final': final}, ensure_ascii=False)}\n\n"
            log_ai_event(
                "chat_question_stream",
                int((_time.perf_counter() - _t0) * 1000),
                {
                    "status": "ok",
                    "model": explain_client.model_id,
                    "reply_len": len(final),
                    "turn_count": len(body.conversation) + 1,
                    "explain_level": getattr(body, "explain_level", 1) or 1,
                },
            )
        except Exception as exc:  # noqa: BLE001
            log_ai_event(
                "chat_question_stream",
                int((_time.perf_counter() - _t0) * 1000),
                {"status": "error"},
            )
            yield f"event: error\ndata: {_json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# 题目翻译
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel

class TranslateQuestionRequest(_BaseModel):
    question_text: str

class TranslateQuestionResponse(_BaseModel):
    status: str = "success"
    translation: str

_TRANSLATE_PROMPT = """\
将下面的 A-Level 数学题目翻译成中文。

规则：
- 完整翻译题目的每一句话，不要遗漏任何信息
- 数学公式保持 LaTeX 格式写在 $...$ 中，例如 $x^2 + 3x - 1$、$\\frac{{dy}}{{dx}}$
- 数学术语翻译成中文后，在括号中附上英文原词，例如"求导（differentiate）"
- 不要添加任何解题内容，只翻译题目本身
- 直接输出翻译文本，不要加引号或前缀

题目：
{question_text}
"""

@router.post(
    "/translate-question",
    response_model=TranslateQuestionResponse,
    tags=["interactive"],
)
async def translate_question(body: TranslateQuestionRequest, request: Request) -> TranslateQuestionResponse:
    registry = _get_registry(request)
    base_client = registry[ModelRole.base]

    prompt = _TRANSLATE_PROMPT.format(question_text=body.question_text)
    req = ModelRequest(task=TaskType.grade, prompt=prompt, max_tokens=1024)

    try:
        translation = await run_in_threadpool(base_client.call, req)
        translation = translation.strip()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error_code": "TRANSLATE_ERROR", "message": str(exc)},
        )

    return TranslateQuestionResponse(translation=translation)
