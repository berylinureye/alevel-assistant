"""
题库 API 路由

提供随机出题、答案提交、题库统计、知识点分类、试卷下载等接口。
"""
from __future__ import annotations

from pathlib import Path
import math
import re
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from api.feedback import log_ai_event
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


def _dedupe_strings(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _normalise_answer_text(value: str | None) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\\(", "").replace("\\)", "").replace("$", "")
    text = re.sub(r"\\(?:mathrm|text|operatorname)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("−", "-").replace("–", "-")
    text = re.sub(r"\s+", "", text)
    return text


def _numeric_tokens(value: str | None) -> list[float]:
    text = str(value or "").replace(",", "")
    out: list[float] = []
    for frac in re.finditer(r"(?<![\w.])(-?\d+)\s*/\s*(-?\d+)(?![\w.])", text):
        den = float(frac.group(2))
        if den != 0:
            out.append(float(frac.group(1)) / den)
    for token in re.finditer(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", text):
        try:
            out.append(float(token.group(0)))
        except ValueError:
            continue
    return out


def _answers_match(student_answer: str, reference_answer: str | None) -> bool:
    if not student_answer.strip() or not str(reference_answer or "").strip():
        return False

    student_norm = _normalise_answer_text(student_answer)
    reference_norm = _normalise_answer_text(reference_answer)
    if student_norm and reference_norm and student_norm == reference_norm:
        return True

    student_nums = _numeric_tokens(student_answer)
    reference_nums = _numeric_tokens(reference_answer)
    if not student_nums or not reference_nums:
        return False
    return any(abs(s - r) <= max(1e-9, abs(r) * 1e-6) for s in student_nums for r in reference_nums)


def _derive_normal_expected_count(question: QuestionBankItem) -> str | None:
    text = f"{question.parent_stem or ''}\n{question.question_text or ''}"
    low = text.lower()
    if "standard deviation" not in low or "expect" not in low:
        return None

    count_match = (
        re.search(r"\bbuys\s+(\d+)\b", low)
        or re.search(r"\b(\d+)\s+of\s+these\b", low)
        or re.search(r"\b(\d+)\s+(?:bags|items|objects|people|students)\b", low)
    )
    z_match = re.search(
        r"more\s+than\s+([0-9]+(?:\.[0-9]+)?)\s+standard\s+deviations?\s+above",
        low,
    )
    if not count_match or not z_match:
        return None

    count = int(count_match.group(1))
    z = float(z_match.group(1))
    upper_tail = 0.5 * math.erfc(z / math.sqrt(2))
    expected = count * upper_tail
    return str(int(round(expected)))


def _practice_reference_answer(question: QuestionBankItem) -> str | None:
    explicit = str(question.correct_answer or "").strip()
    if explicit:
        return explicit
    if question.topic == "normal_distribution" or question.subtopic == "expected_value":
        return _derive_normal_expected_count(question)
    return None


def _local_practice_grade(question: QuestionBankItem, body: SubmitAnswerRequest) -> dict:
    full_score = float(question.marks or (len(question.marking_points or []) or 1))
    reference = _practice_reference_answer(question)
    tags = _dedupe_strings([question.topic, question.subtopic, *(question.tags or [])])

    if not body.student_answer.strip():
        return {
            "is_correct": False,
            "score": 0.0,
            "full_score": full_score,
            "error_type": "unanswered",
            "short_feedback": "还没有看到你的最终答案，请先补完整再提交。",
            "knowledge_tags": tags,
            "student_feedback": "先写出最终答案；有过程的话也可以把关键步骤填在下面。",
        }

    if reference and _answers_match(body.student_answer, reference):
        return {
            "is_correct": True,
            "score": full_score,
            "full_score": full_score,
            "error_type": "correct",
            "short_feedback": "答案正确。",
            "knowledge_tags": tags,
            "student_feedback": "答案正确。继续保持这种题型的节奏。",
        }

    if reference:
        return {
            "is_correct": False,
            "score": 0.0,
            "full_score": full_score,
            "error_type": "incorrect_answer",
            "short_feedback": f"答案还不对。参考答案是 {reference}。",
            "knowledge_tags": tags,
            "student_feedback": "先对照参考答案检查标准化、查表或代入步骤；如果只是四舍五入差异，请保留更多有效数字再提交。",
        }

    return {
        "is_correct": False,
        "score": 0.0,
        "full_score": full_score,
        "error_type": "missing_reference_answer",
        "short_feedback": "这道题暂时缺少题库参考答案，无法自动判定，需要人工复核。",
        "knowledge_tags": tags,
        "student_feedback": "题库缺少参考答案；你可以先查看 marking points 或换一道同主题题继续练。",
    }


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
    练习题来自题库，优先用题库参考答案/marking points 做快速判分，避免
    用户提交答案后因为模型长调用一直停在“批改中”。
    """
    started_at = time.perf_counter()

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

    grade_result = _local_practice_grade(question, body)

    log_ai_event(
        "practice_answer_graded",
        int((time.perf_counter() - started_at) * 1000),
        {
            "status": "success",
            "question_id": body.question_id,
            "is_correct": grade_result["is_correct"],
            "score": grade_result["score"],
            "full_score": grade_result["full_score"],
            "error_type": grade_result["error_type"],
            "knowledge_tags": grade_result["knowledge_tags"],
            "paper_num": question.paper_num,
            "difficulty": question.difficulty,
            "grading_path": "local_reference_answer",
        },
    )

    return {
        "status": "success",
        "question_id": body.question_id,
        "grade_result": grade_result,
        "reference_answer": _practice_reference_answer(question),
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
