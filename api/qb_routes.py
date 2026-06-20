"""
题库 API 路由

提供随机出题、答案提交、题库统计、知识点分类、试卷下载等接口。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from questionbank.database import (
    ensure_db,
    get_all_topics,
    get_question_by_id,
    get_random_questions,
    get_stats,
)
from questionbank.models import (
    QuestionBankItem,
    QuestionBankStats,
    RandomQuestionRequest,
    RandomQuestionResponse,
    SubmitAnswerRequest,
    TopicStats,
)
from scraper.taxonomy import (
    DIFFICULTY_LEVELS,
    PAPER_INFO,
    get_all_topics_flat,
    get_topic_tree,
)

qb_router = APIRouter(prefix="/questions", tags=["question-bank"])


# ---------------------------------------------------------------------------
# 随机出题
# ---------------------------------------------------------------------------

@qb_router.post("/random", response_model=RandomQuestionResponse)
async def random_questions(body: RandomQuestionRequest) -> RandomQuestionResponse:
    """根据条件随机抽题"""

    def _query():
        conn = ensure_db()
        try:
            questions, total = get_random_questions(
                conn,
                topics=body.topics,
                difficulty_min=body.difficulty_min,
                difficulty_max=body.difficulty_max,
                count=body.count,
                year_from=body.year_from,
                year_to=body.year_to,
                paper_nums=body.paper_nums,
                exclude_ids=body.exclude_ids,
                verified_only=body.verified_only,
            )
            return questions, total
        finally:
            conn.close()

    questions, total = await run_in_threadpool(_query)

    return RandomQuestionResponse(
        questions=questions,
        total_available=total,
    )


# GET 版本 (方便浏览器测试)
@qb_router.get("/random", response_model=RandomQuestionResponse)
async def random_questions_get(
    topic: Optional[str] = None,
    difficulty_min: int = 1,
    difficulty_max: int = 5,
    count: int = 5,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    verified_only: bool = False,
) -> RandomQuestionResponse:
    """GET 版随机出题 (方便测试)"""
    topics = [topic] if topic else None
    body = RandomQuestionRequest(
        topics=topics,
        difficulty_min=difficulty_min,
        difficulty_max=difficulty_max,
        count=count,
        year_from=year_from,
        year_to=year_to,
        verified_only=verified_only,
    )
    return await random_questions(body)


# ---------------------------------------------------------------------------
# 知识点列表
# ---------------------------------------------------------------------------

@qb_router.get("/meta/topics", response_model=list[TopicStats])
async def list_topics() -> list[TopicStats]:
    """获取所有知识点及统计"""

    def _query():
        conn = ensure_db()
        try:
            return get_all_topics(conn)
        finally:
            conn.close()

    return await run_in_threadpool(_query)


# ---------------------------------------------------------------------------
# 题库统计
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 导出题目 (用于生成 PDF)
# ---------------------------------------------------------------------------

@qb_router.post("/export", response_model=RandomQuestionResponse)
async def export_questions(body: RandomQuestionRequest) -> RandomQuestionResponse:
    """导出筛选后的题目（支持更大数量，用于 PDF 导出）"""

    def _query():
        conn = ensure_db()
        try:
            questions, total = get_random_questions(
                conn,
                topics=body.topics,
                difficulty_min=body.difficulty_min,
                difficulty_max=body.difficulty_max,
                count=body.count,
                year_from=body.year_from,
                year_to=body.year_to,
                paper_nums=body.paper_nums,
                exclude_ids=body.exclude_ids,
                verified_only=body.verified_only,
            )
            return questions, total
        finally:
            conn.close()

    questions, total = await run_in_threadpool(_query)

    return RandomQuestionResponse(
        questions=questions,
        total_available=total,
    )


# ---------------------------------------------------------------------------
# 知识点分类体系 (Taxonomy)
# ---------------------------------------------------------------------------

@qb_router.get("/meta/taxonomy")
async def get_taxonomy(paper_num: Optional[int] = None):
    """获取完整知识点分类树 (按 Paper 分组)"""
    return {
        "status": "success",
        "difficulty_levels": DIFFICULTY_LEVELS,
        "papers": get_topic_tree(paper_num),
    }


@qb_router.get("/meta/taxonomy/flat")
async def get_taxonomy_flat(paper_num: Optional[int] = None):
    """获取扁平化知识点列表 (用于筛选下拉框)"""
    topics = get_all_topics_flat(paper_num)
    return {
        "status": "success",
        "count": len(topics),
        "topics": topics,
    }


# ---------------------------------------------------------------------------
# 试卷列表与下载
# ---------------------------------------------------------------------------

@qb_router.get("/papers")
async def list_papers(
    paper_num: Optional[int] = None,
    year: Optional[int] = None,
    session: Optional[str] = None,
    level: Optional[str] = None,
):
    """获取试卷列表，支持筛选"""

    def _query():
        conn = ensure_db()
        try:
            where = ["1=1"]
            params = []
            if paper_num:
                where.append("paper_num = ?")
                params.append(paper_num)
            if year:
                where.append("year = ?")
                params.append(year)
            if session:
                where.append("session = ?")
                params.append(session)

            rows = conn.execute(
                f"""SELECT id, subject_code, year, session, paper_num, variant,
                           pdf_path, ms_pdf_path
                    FROM papers
                    WHERE {' AND '.join(where)}
                    ORDER BY year DESC, session, paper_num, variant""",
                params,
            ).fetchall()

            results = []
            for r in rows:
                pinfo = PAPER_INFO.get(r["paper_num"], {})
                plevel = pinfo.get("level", "")

                if level and plevel != level:
                    continue

                results.append({
                    "id": r["id"],
                    "subject_code": r["subject_code"],
                    "year": r["year"],
                    "session": r["session"],
                    "paper_num": r["paper_num"],
                    "paper_name": pinfo.get("name", f"Paper {r['paper_num']}"),
                    "level": plevel,
                    "component": pinfo.get("component", ""),
                    "variant": r["variant"],
                    "has_qp": r["pdf_path"] is not None,
                    "has_ms": r["ms_pdf_path"] is not None,
                })
            return results
        finally:
            conn.close()

    papers = await run_in_threadpool(_query)
    return {"status": "success", "count": len(papers), "papers": papers}


@qb_router.get("/papers/{paper_id}/download/{file_type}")
async def download_paper(paper_id: int, file_type: str):
    """下载试卷 PDF (file_type: qp 或 ms)"""
    if file_type not in ("qp", "ms"):
        raise HTTPException(400, "file_type must be 'qp' or 'ms'")

    def _query():
        conn = ensure_db()
        try:
            row = conn.execute(
                "SELECT pdf_path, ms_pdf_path FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
            return row
        finally:
            conn.close()

    row = await run_in_threadpool(_query)
    if not row:
        raise HTTPException(404, "Paper not found")

    path_str = row["pdf_path"] if file_type == "qp" else row["ms_pdf_path"]
    if not path_str:
        raise HTTPException(404, f"No {file_type.upper()} file for this paper")

    pdf_path = Path(path_str)
    if not pdf_path.exists():
        raise HTTPException(404, "PDF file not found on disk")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
    )


@qb_router.get("/meta/stats", response_model=QuestionBankStats)
async def question_bank_stats() -> QuestionBankStats:
    """获取题库总体统计"""

    def _query():
        conn = ensure_db()
        try:
            return get_stats(conn)
        finally:
            conn.close()

    return await run_in_threadpool(_query)


# ---------------------------------------------------------------------------
# 提交答案 (对接现有 grader)
# ---------------------------------------------------------------------------

@qb_router.post("/submit-answer")
async def submit_answer(body: SubmitAnswerRequest, request: Request):
    """
    提交答案并获取批改结果。
    复用现有的 grading pipeline。
    """
    from grader.grader import grade_question as do_grade
    from models.schemas import QuestionData
    from router.models import ModelRole, TaskType

    # 1. 获取题目信息
    def _get_q():
        conn = ensure_db()
        try:
            return get_question_by_id(conn, body.question_id)
        finally:
            conn.close()

    question = await run_in_threadpool(_get_q)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # 2. 构造 QuestionData (复用现有 schema)
    question_data = QuestionData(
        question_number=question.question_number,
        bbox=[],
        question_text=question.question_text,
        student_answer=body.student_answer,
        working_steps=body.working_steps,
        image_quality="good",
        confidence=1.0,
    )

    # 3. 调用 grader
    registry = getattr(request.app.state, "registry", None)
    if registry is None:
        from router.models import build_registry
        registry = build_registry()

    base_client = registry[ModelRole.base]

    try:
        result = await run_in_threadpool(do_grade, question_data, base_client, TaskType.grade)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error_code": "GRADING_ERROR", "message": str(exc)},
        )

    # 4. 附加题库中的标准答案
    return {
        "status": "success",
        "question_id": body.question_id,
        "grade_result": {
            "is_correct": result.is_correct,
            "score": result.score,
            "full_score": result.full_score,
            "error_type": result.error_type,
            "short_feedback": result.short_feedback,
            "knowledge_tags": result.knowledge_tags,
            "student_feedback": result.student_feedback,
        },
        "reference_answer": question.correct_answer,
        "marking_points": question.marking_points,
        "source": {
            "year": question.year,
            "session": question.session,
            "paper": question.paper_num,
            "variant": question.variant,
            "question_number": question.question_number,
        },
    }


# ---------------------------------------------------------------------------
# 单题详情 (放最后：/{question_id} 是 catch-all，必须在所有具体路径之后注册)
# ---------------------------------------------------------------------------

@qb_router.get("/{question_id}", response_model=QuestionBankItem)
async def get_question(question_id: int) -> QuestionBankItem:
    """获取单题详情"""

    def _query():
        conn = ensure_db()
        try:
            return get_question_by_id(conn, question_id)
        finally:
            conn.close()

    item = await run_in_threadpool(_query)
    if not item:
        raise HTTPException(status_code=404, detail="Question not found")
    return item
