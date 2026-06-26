"""
用户反馈：SQLite/MySQL 双后端存储 + 提交/查看接口。
- 匿名 user_id 由前端 localStorage 生成并随请求带上，无需账号。
- 管理员通过 ADMIN_TOKEN 环境变量查看全部反馈。
- 设置 MYSQL_HOST 走 MySQL（生产），否则走本地 SQLite（开发）。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from api.effectiveness import compute_upload_corpus_effectiveness, latest_run_records_from_ai_events


_DB_PATH = Path(os.environ.get("FEEDBACK_DB_PATH", "data/feedback.db"))
_USE_MYSQL = bool(os.environ.get("MYSQL_HOST"))


class _ConnWrapper:
    """统一 SQLite / MySQL 的最小接口：execute/commit/close + cursor.fetchone/fetchall/lastrowid。

    SQLite 用 `?` 占位符并返回 sqlite3.Row（可按列名访问）；
    MySQL 用 `%s` 占位符并通过 DictCursor 返回 dict。
    本封装在 execute 层把 `?` 替换成 `%s`，对外统一按 dict 风格访问列。
    """

    def __init__(self, conn: Any, is_mysql: bool):
        self._conn = conn
        self._is_mysql = is_mysql

    def execute(self, sql: str, params: tuple = ()) -> Any:
        if self._is_mysql:
            sql = sql.replace("?", "%s")
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return cur
        return self._conn.execute(sql, params)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


_SCHEMAS_SQLITE = [
    """
    CREATE TABLE IF NOT EXISTS feedback (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     TEXT    NOT NULL,
        session_id  TEXT,
        scope       TEXT    NOT NULL,
        rating      INTEGER,
        comment     TEXT,
        tags        TEXT,
        context     TEXT,
        created_at  INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type  TEXT    NOT NULL,
        duration_ms INTEGER NOT NULL,
        meta        TEXT,
        created_at  INTEGER NOT NULL
    )
    """,
]

_SCHEMAS_MYSQL = [
    """
    CREATE TABLE IF NOT EXISTS feedback (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        user_id     VARCHAR(128) NOT NULL,
        session_id  VARCHAR(128),
        scope       VARCHAR(32)  NOT NULL,
        rating      INT,
        comment     TEXT,
        tags        TEXT,
        context     TEXT,
        created_at  BIGINT       NOT NULL,
        INDEX idx_created_at (created_at),
        INDEX idx_user_id (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_events (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        event_type  VARCHAR(64)  NOT NULL,
        duration_ms INT          NOT NULL,
        meta        TEXT,
        created_at  BIGINT       NOT NULL,
        INDEX idx_event_type (event_type),
        INDEX idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


def _get_conn() -> _ConnWrapper:
    if _USE_MYSQL:
        import pymysql
        from pymysql.cursors import DictCursor
        raw = pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ.get("MYSQL_USER", "root"),
            password=os.environ.get("MYSQL_PASSWORD", ""),
            database=os.environ.get("MYSQL_DATABASE", "feedback"),
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=10,
        )
        wrapper = _ConnWrapper(raw, is_mysql=True)
        for ddl in _SCHEMAS_MYSQL:
            wrapper.execute(ddl)
        raw.commit()
        return wrapper

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(str(_DB_PATH))
    raw.row_factory = sqlite3.Row
    for ddl in _SCHEMAS_SQLITE:
        raw.execute(ddl)
    return _ConnWrapper(raw, is_mysql=False)


def log_ai_event(event_type: str, duration_ms: int, meta: Optional[Dict[str, Any]] = None) -> None:
    """后端 AI 调用埋点：记录时长。失败只打印，不抛异常。"""
    try:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO ai_events (event_type, duration_ms, meta, created_at) VALUES (?, ?, ?, ?)",
                (event_type, int(duration_ms), json.dumps(meta or {}, ensure_ascii=False), int(time.time())),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        print(f"[ai_events] log failed: {exc}")


def _safe_meta(raw: object) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw or "{}"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _rate(numerator: int | float, denominator: int | float) -> Optional[float]:
    if not denominator:
        return None
    return round(float(numerator) / float(denominator), 3)


def _pct_from_values(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    i = min(len(s) - 1, int(len(s) * p))
    return s[i]


def _quality_issue_tags(meta: Dict[str, Any]) -> list[str]:
    tags = meta.get("issue_tags") or meta.get("issues") or []
    if isinstance(tags, str):
        return [tags]
    if isinstance(tags, list):
        return [str(t) for t in tags if str(t).strip()]
    return []


def _quality_pass(value: object, threshold: float, pass_labels: set[str]) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in pass_labels:
            return True
        try:
            return float(normalized) >= threshold
        except Exception:
            return False
    try:
        return float(value or 0) >= threshold
    except Exception:
        return False


def compute_product_metrics(
    events: list[Dict[str, Any]],
    feedback_items: list[Dict[str, Any]],
    feedback_total: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the full learning-loop metrics used by the admin dashboard.

    The input shape intentionally matches rows projected from ai_events/feedback
    so this stays easy to unit test without a database.
    """
    by_type: Dict[str, list[Dict[str, Any]]] = {}
    for event in events:
        by_type.setdefault(str(event.get("event_type") or ""), []).append(event)

    def count(event_type: str) -> int:
        return len(by_type.get(event_type, []))

    def metas(event_type: str) -> list[Dict[str, Any]]:
        return [_safe_meta(e.get("meta")) for e in by_type.get(event_type, [])]

    def durations(event_type: str) -> list[int]:
        return [int(e.get("duration_ms") or 0) for e in by_type.get(event_type, [])]

    page_views = count("ui_page_view")
    file_selected = count("ui_file_selected")
    upload_submits = count("ui_upload_submit") + count("ui_large_pdf_submit")
    upload_received = count("upload_received")
    prepare_done = count("prepare_upload_done")
    segment_done = count("segment_done")
    question_graded = count("question_graded")
    result_seen = count("ui_result_seen")
    question_expanded = count("ui_question_expanded") + count("ui_solution_expand")
    practice_seen = count("ui_practice_recommendation_seen")
    practice_started = count("ui_practice_started")
    practice_submitted = count("ui_practice_answer_submitted")
    feedback_submitted = feedback_total if feedback_total is not None else len(feedback_items)
    next_actions = question_expanded + practice_seen + practice_started + practice_submitted + feedback_submitted

    prepare_metas = metas("prepare_upload_done")
    prepare_success = sum(1 for m in prepare_metas if m.get("status") in {None, "ready", "success"})
    prepare_timeout = sum(1 for m in prepare_metas if m.get("ocr_status") == "timeout" or m.get("status") == "timeout")
    large_pdf_metas = metas("large_pdf_prepare_done") + metas("ui_large_pdf_prepare")
    large_pdf_success = sum(1 for m in large_pdf_metas if m.get("status") in {None, "ready", "success"} and not m.get("error_code"))
    large_pdf_adjusted = sum(1 for m in metas("ui_large_pdf_submit") if m.get("default_selected_count") and m.get("selected_count") != m.get("default_selected_count"))

    paper_metas = metas("paper_resolution_done")
    high_matches = [m for m in paper_metas if m.get("confidence") == "high" or m.get("match_confidence") == "high"]
    high_auto_mark_scheme = sum(1 for m in high_matches if m.get("route") == "past_paper_mark_scheme" or m.get("grading_route") == "past_paper_mark_scheme")
    medium_confirm = sum(1 for m in paper_metas if (m.get("confidence") == "medium" or m.get("match_confidence") == "medium") and m.get("needs_confirmation"))
    low_open = sum(1 for m in paper_metas if (m.get("confidence") == "low" or m.get("match_confidence") == "low") and (m.get("route") == "open_ai_grading" or m.get("grading_route") == "open_ai_grading"))

    segment_metas = metas("segment_done")
    segment_questions = sum(int(m.get("question_count") or m.get("questions") or 0) for m in segment_metas)
    empty_answers = sum(int(m.get("empty_count") or 0) for m in segment_metas)
    parent_missing = sum(int(m.get("parent_stem_missing_count") or 0) for m in segment_metas)

    graded_metas = metas("question_graded")
    correct_cnt = sum(1 for m in graded_metas if m.get("is_correct") is True)
    incorrect_cnt = sum(1 for m in graded_metas if m.get("is_correct") is False)
    needs_review_cnt = sum(1 for m in graded_metas if m.get("needs_review") is True or m.get("escalated") is True)
    low_conf_review_cnt = sum(
        1 for m in graded_metas
        if (m.get("grading_confidence") is not None and float(m.get("grading_confidence") or 0) < 0.65 and (m.get("needs_review") or m.get("escalated")))
    )
    low_conf_cnt = sum(1 for m in graded_metas if m.get("grading_confidence") is not None and float(m.get("grading_confidence") or 0) < 0.65)
    high_conf_wrong_cnt = sum(
        1 for m in graded_metas
        if m.get("is_correct") is False and m.get("grading_confidence") is not None and float(m.get("grading_confidence") or 0) >= 0.85
    )
    mark_scheme_cnt = sum(1 for m in graded_metas if m.get("grading_route") == "past_paper_mark_scheme")
    open_ai_cnt = sum(1 for m in graded_metas if m.get("grading_route") == "open_ai_grading")
    verifier_adjusted_cnt = sum(1 for m in graded_metas if m.get("verifier_adjusted"))

    quality_metas = metas("feedback_quality_sampled")
    quality_count = len(quality_metas)
    score_accuracy_pass = sum(
        1 for m in quality_metas
        if _quality_pass(m.get("score_accuracy"), 0.88, {"pass", "accurate"})
    )
    explanation_pass = sum(
        1 for m in quality_metas
        if _quality_pass(m.get("explanation_quality"), 0.9, {"pass", "specific"})
    )
    high_conf_errors = sum(1 for m in quality_metas if m.get("high_confidence_error") is True)
    issue_counts: Dict[str, int] = {}
    for m in quality_metas:
        for tag in _quality_issue_tags(m):
            issue_counts[tag] = issue_counts.get(tag, 0) + 1

    practice_submit_metas = metas("ui_practice_answer_submitted")
    practice_correct = sum(1 for m in practice_submit_metas if (m.get("is_correct") is True))
    practice_next = count("ui_practice_next_adjusted")
    recommendation_served_metas = metas("practice_recommendation_served")
    real_recommendation_cnt = sum(int(m.get("real_question_count") or 0) for m in recommendation_served_metas)
    recommendation_cnt = sum(int(m.get("recommendation_count") or 0) for m in recommendation_served_metas)

    pipeline_errors = count("pipeline_error")
    sessions_done = count("session_done")
    sse_cancelled = count("ui_analysis_cancelled")

    north_star = {
        "name": "有效学习闭环完成率",
        "value": _rate(min(upload_received, result_seen, next_actions), upload_received),
        "numerator": min(upload_received, result_seen, next_actions),
        "denominator": upload_received,
        "target": 0.45,
        "alert": 0.30,
    }

    funnel = [
        {"key": "ui_page_view", "label": "访问", "count": page_views, "rate_from_previous": None},
        {"key": "ui_file_selected", "label": "选择文件", "count": file_selected, "rate_from_previous": _rate(file_selected, page_views)},
        {"key": "ui_upload_submit", "label": "提交上传", "count": upload_submits, "rate_from_previous": _rate(upload_submits, file_selected or page_views)},
        {"key": "prepare_upload_done", "label": "预处理成功", "count": prepare_success, "rate_from_previous": _rate(prepare_success, prepare_done)},
        {"key": "segment_done", "label": "切题成功", "count": segment_done, "rate_from_previous": _rate(segment_done, upload_received)},
        {"key": "question_graded", "label": "至少一题批改", "count": question_graded, "rate_from_previous": _rate(question_graded, segment_done)},
        {"key": "ui_result_seen", "label": "看到结果", "count": result_seen, "rate_from_previous": _rate(result_seen, upload_received)},
        {"key": "ui_question_expanded", "label": "查看讲解", "count": question_expanded, "rate_from_previous": _rate(question_expanded, result_seen)},
        {"key": "ui_practice_started", "label": "开始练习", "count": practice_started, "rate_from_previous": _rate(practice_started, result_seen)},
    ]

    node_metrics = [
        {"node": "首屏/上传入口", "metric": "上传转化率", "value": _rate(upload_submits, page_views), "target": 0.45, "alert": 0.30},
        {"node": "上传文件选择", "metric": "文件选择成功率", "value": _rate(file_selected, page_views), "target": 0.95, "alert": 0.90},
        {"node": "上传预处理", "metric": "预识别成功率", "value": _rate(prepare_success, prepare_done), "target": 0.95, "alert": 0.90},
        {"node": "上传预处理", "metric": "预识别 P95 耗时", "value": _pct_from_values(durations("prepare_upload_done"), 0.95), "unit": "ms", "target": 20000, "alert": 30000},
        {"node": "上传预处理", "metric": "超时率", "value": _rate(prepare_timeout, prepare_done), "target": 0.05, "alert": 0.10, "lower_is_better": True},
        {"node": "Large PDF 准备", "metric": "缩略图/会话成功率", "value": _rate(large_pdf_success, len(large_pdf_metas)), "target": 0.95, "alert": 0.90},
        {"node": "Large PDF 准备", "metric": "用户手动改选率", "value": _rate(large_pdf_adjusted, count("ui_large_pdf_submit")), "target": None, "alert": None},
        {"node": "Past Paper 匹配", "metric": "high-confidence 自动规则批改率", "value": _rate(high_auto_mark_scheme, len(high_matches)), "target": 0.95, "alert": 0.90},
        {"node": "Past Paper 匹配", "metric": "medium 确认触发数", "value": medium_confirm, "unit": "count", "target": None, "alert": None},
        {"node": "Past Paper 匹配", "metric": "low 合理降级数", "value": low_open, "unit": "count", "target": None, "alert": None},
        {"node": "OCR/切题", "metric": "题目识别数", "value": segment_questions, "unit": "count", "target": None, "alert": None},
        {"node": "OCR/切题", "metric": "空答案识别率", "value": _rate(empty_answers, segment_questions), "target": None, "alert": None},
        {"node": "父题上下文继承", "metric": "parent_stem 缺失率", "value": _rate(parent_missing, segment_questions), "target": 0.03, "alert": 0.08, "lower_is_better": True},
        {"node": "初步判分", "metric": "自动判分正确题占比", "value": _rate(correct_cnt, correct_cnt + incorrect_cnt), "target": 0.88, "alert": 0.80},
        {"node": "Mark Scheme 批改", "metric": "规则批改题量", "value": mark_scheme_cnt, "unit": "count", "target": None, "alert": None},
        {"node": "Open AI 批改", "metric": "开放批改题量", "value": open_ai_cnt, "unit": "count", "target": None, "alert": None},
        {"node": "确定性校验", "metric": "verifier 修正率", "value": _rate(verifier_adjusted_cnt, question_graded), "target": None, "alert": None},
        {"node": "批改置信度", "metric": "低置信触发复核率", "value": _rate(low_conf_review_cnt, low_conf_cnt), "target": 1.0, "alert": 0.9},
        {"node": "批改置信度", "metric": "错误高置信率", "value": _rate(high_conf_wrong_cnt + high_conf_errors, question_graded + quality_count), "target": 0.03, "alert": 0.06, "lower_is_better": True},
        {"node": "反馈讲解", "metric": "人工抽检讲解通过率", "value": _rate(explanation_pass, quality_count), "target": 0.90, "alert": 0.80},
        {"node": "结果页", "metric": "首题可见 P95 耗时", "value": _pct_from_values(durations("ui_result_seen"), 0.95), "unit": "ms", "target": 35000, "alert": 50000},
        {"node": "推荐练习", "metric": "真实题推荐占比", "value": _rate(real_recommendation_cnt, recommendation_cnt), "target": 0.85, "alert": 0.75},
        {"node": "练习提交", "metric": "练习提交成功率", "value": _rate(practice_submitted, practice_started), "target": 0.95, "alert": 0.90},
        {"node": "练习提交", "metric": "练习正确率", "value": _rate(practice_correct, practice_submitted), "target": None, "alert": None},
        {"node": "练习提交", "metric": "下一题继续率", "value": _rate(practice_next, practice_submitted), "target": 0.30, "alert": 0.15},
        {"node": "用户反馈", "metric": "反馈提交率", "value": _rate(feedback_submitted, result_seen), "target": 0.05, "alert": 0.02},
        {"node": "系统稳定性", "metric": "上传到完成率", "value": _rate(sessions_done, upload_received), "target": 0.95, "alert": 0.90},
        {"node": "系统稳定性", "metric": "pipeline_error 率", "value": _rate(pipeline_errors, upload_received), "target": 0.05, "alert": 0.10, "lower_is_better": True},
        {"node": "系统稳定性", "metric": "前端取消数", "value": sse_cancelled, "unit": "count", "target": None, "alert": None},
    ]

    return {
        "north_star": north_star,
        "learning_loop_funnel": funnel,
        "node_metrics": node_metrics,
        "quality_review": {
            "sample_count": quality_count,
            "score_accuracy_rate": _rate(score_accuracy_pass, quality_count),
            "explanation_quality_rate": _rate(explanation_pass, quality_count),
            "high_confidence_errors": high_conf_errors,
            "top_issue_tags": sorted(issue_counts.items(), key=lambda x: -x[1])[:10],
        },
        "route_mix": {
            "past_paper_mark_scheme": mark_scheme_cnt,
            "open_ai_grading": open_ai_cnt,
            "needs_review": needs_review_cnt,
        },
    }


class TrackEvent(BaseModel):
    """前端埋点事件：event_type 必须以 'ui_' 前缀以和后端事件区分，避免客户端伪造后端指标。"""
    event_type: str = Field(..., min_length=3, max_length=64)
    duration_ms: int = Field(0, ge=0, le=3_600_000)
    meta: Dict[str, Any] = Field(default_factory=dict)


class FeedbackSubmit(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    session_id: Optional[str] = Field(None, max_length=128)
    scope: str = Field("session", description="session | question")
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=2000)
    tags: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)


class FeedbackSubmitResponse(BaseModel):
    status: str = "ok"
    id: int


feedback_router = APIRouter(prefix="/feedback", tags=["feedback"])


@feedback_router.post("/track")
async def track_event(body: TrackEvent) -> dict:
    """
    前端埋点接收端。公共接口（无 token）；但强制 event_type 以 'ui_' 开头，
    避免客户端伪造后端指标（如 explain_question / pipeline_*）。
    写入同一张 ai_events 表，看板侧按前缀分类展示。
    """
    et = body.event_type.strip()
    if not et.startswith("ui_"):
        raise HTTPException(
            status_code=400,
            detail={"error_code": "INVALID_EVENT", "message": "event_type 必须以 ui_ 前缀"},
        )
    # 限制 meta 大小（防止滥用写入超大 JSON）
    try:
        meta_json = json.dumps(body.meta, ensure_ascii=False)
    except Exception:
        meta_json = "{}"
    if len(meta_json) > 4096:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "META_TOO_LARGE", "message": "meta 超过 4KB"},
        )
    log_ai_event(et, body.duration_ms, body.meta)
    return {"status": "ok"}


@feedback_router.post("", response_model=FeedbackSubmitResponse)
async def submit_feedback(body: FeedbackSubmit) -> FeedbackSubmitResponse:
    if body.rating is None and not (body.comment and body.comment.strip()) and not body.tags:
        raise HTTPException(status_code=400, detail={"error_code": "EMPTY_FEEDBACK", "message": "至少填写评分、标签或文字中的一项"})

    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO feedback (user_id, session_id, scope, rating, comment, tags, context, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                body.user_id,
                body.session_id,
                body.scope,
                body.rating,
                (body.comment or "").strip() or None,
                json.dumps(body.tags, ensure_ascii=False),
                json.dumps(body.context, ensure_ascii=False),
                int(time.time()),
            ),
        )
        conn.commit()
        return FeedbackSubmitResponse(id=cur.lastrowid or 0)
    finally:
        conn.close()


@feedback_router.get("/list")
async def list_feedback(
    token: str = Query(..., description="管理员 token，匹配 ADMIN_TOKEN 环境变量"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "invalid admin token"})

    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, user_id, session_id, scope, rating, comment, tags, context, created_at "
            "FROM feedback ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM feedback").fetchone()["c"]
    finally:
        conn.close()

    def _row(r: sqlite3.Row) -> dict:
        return {
            "id": r["id"],
            "user_id": r["user_id"],
            "session_id": r["session_id"],
            "scope": r["scope"],
            "rating": r["rating"],
            "comment": r["comment"],
            "tags": json.loads(r["tags"] or "[]"),
            "context": json.loads(r["context"] or "{}"),
            "created_at": r["created_at"],
        }

    return {"total": total, "items": [_row(r) for r in rows]}


@feedback_router.get("/ai-events")
async def list_ai_events(
    token: str = Query(..., description="管理员 token"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "invalid admin token"})

    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, event_type, duration_ms, meta, created_at FROM ai_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        stats = conn.execute(
            "SELECT event_type, COUNT(*) AS n, AVG(duration_ms) AS avg_ms, MAX(duration_ms) AS max_ms "
            "FROM ai_events GROUP BY event_type"
        ).fetchall()
    finally:
        conn.close()

    return {
        "stats": [dict(r) for r in stats],
        "items": [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "duration_ms": r["duration_ms"],
                "meta": json.loads(r["meta"] or "{}"),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }


def _compute_stats(now_ts: int) -> Dict[str, Any]:
    conn = _get_conn()
    try:
        seven_days_ago = now_ts - 7 * 86400
        fb_total = conn.execute("SELECT COUNT(*) c FROM feedback").fetchone()["c"]
        fb_recent = conn.execute(
            "SELECT COUNT(*) c FROM feedback WHERE created_at >= ?", (seven_days_ago,),
        ).fetchone()["c"]
        avg_rating_row = conn.execute(
            "SELECT AVG(rating) avg FROM feedback WHERE rating IS NOT NULL"
        ).fetchone()
        avg_rating = avg_rating_row["avg"]
        low_rating_count = conn.execute(
            "SELECT COUNT(*) c FROM feedback WHERE rating IS NOT NULL AND rating <= 3"
        ).fetchone()["c"]
        rated_count = conn.execute(
            "SELECT COUNT(*) c FROM feedback WHERE rating IS NOT NULL"
        ).fetchone()["c"]

        rating_hist_rows = conn.execute(
            "SELECT rating, COUNT(*) c FROM feedback WHERE rating IS NOT NULL GROUP BY rating"
        ).fetchall()
        rating_hist = {int(r["rating"]): r["c"] for r in rating_hist_rows}

        recent_feedback = conn.execute(
            "SELECT id, user_id, rating, comment, tags, context, created_at "
            "FROM feedback ORDER BY id DESC LIMIT 50"
        ).fetchall()

        ai_rows = conn.execute(
            "SELECT event_type, duration_ms, meta FROM ai_events ORDER BY id DESC"
        ).fetchall()
        # 近 7 天事件计数（看趋势）
        ai_recent_rows = conn.execute(
            "SELECT event_type, COUNT(*) AS c FROM ai_events WHERE created_at >= ? GROUP BY event_type",
            (seven_days_ago,),
        ).fetchall()
        # 最近 100 条原始事件（供"事件流"面板）
        recent_events = conn.execute(
            "SELECT event_type, duration_ms, meta, created_at FROM ai_events ORDER BY id DESC LIMIT 100"
        ).fetchall()
        effectiveness_rows = conn.execute(
            "SELECT event_type, duration_ms, meta, created_at FROM ai_events "
            "WHERE created_at >= ? AND event_type IN (?, ?) ORDER BY id DESC",
            (seven_days_ago, "ui_upload_corpus_asset_result", "upload_corpus_asset_result"),
        ).fetchall()
    finally:
        conn.close()

    # 标签统计
    tag_counts: Dict[str, int] = {}
    for r in recent_feedback:
        for t in json.loads(r["tags"] or "[]"):
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:10]

    # AI 时长分位
    by_type: Dict[str, List[int]] = {}
    for r in ai_rows:
        by_type.setdefault(r["event_type"], []).append(int(r["duration_ms"]))

    recent_counts = {r["event_type"]: r["c"] for r in ai_recent_rows}
    ai_stats = [
        {
            "event_type": et,
            "count": len(xs),
            "recent_7d": recent_counts.get(et, 0),
            "avg_ms": int(sum(xs) / len(xs)) if xs else 0,
            "p50_ms": _pct_from_values(xs, 0.50),
            "p95_ms": _pct_from_values(xs, 0.95),
            "max_ms": max(xs) if xs else 0,
        }
        for et, xs in sorted(by_type.items())
    ]

    # ---- 业务聚合 ----
    # Pipeline 漏斗（按事件类型计数）
    def _count(et: str) -> int:
        return len(by_type.get(et, []))

    uploads = _count("upload_received")
    sessions_done = _count("session_done")
    questions_graded = _count("question_graded")
    questions_unanswered = _count("question_unanswered")
    solutions_done = _count("solution_inline_done")

    # 批改正误率（从 question_graded 的 meta 里聚合）
    graded_meta = []
    for r in ai_rows:
        if r["event_type"] == "question_graded":
            graded_meta.append(_safe_meta(r["meta"]))
    correct_cnt = sum(1 for m in graded_meta if m.get("is_correct") is True)
    incorrect_cnt = sum(1 for m in graded_meta if m.get("is_correct") is False)
    escalated_cnt = sum(1 for m in graded_meta if m.get("escalated") is True)
    error_types: Dict[str, int] = {}
    for m in graded_meta:
        t = m.get("error_type")
        if t:
            error_types[t] = error_types.get(t, 0) + 1
    top_error_types = sorted(error_types.items(), key=lambda x: -x[1])[:10]

    # 聊天层级升级（UI）
    chat_reexplain_levels: Dict[str, int] = {}
    chat_gotit = 0
    ui_errors = 0
    for r in ai_rows:
        et = r["event_type"]
        if not et.startswith("ui_"):
            continue
        m = _safe_meta(r["meta"])
        if et == "ui_chat_reexplain":
            key = f"L{m.get('from_level','?')}→L{m.get('to_level','?')}"
            chat_reexplain_levels[key] = chat_reexplain_levels.get(key, 0) + 1
        elif et == "ui_chat_got_it":
            chat_gotit += 1
        elif et == "ui_error":
            ui_errors += 1

    pipeline_funnel = {
        "upload_received": uploads,
        "session_done": sessions_done,
        "question_graded": questions_graded,
        "question_unanswered": questions_unanswered,
        "solution_inline_done": solutions_done,
    }

    grading_summary = {
        "correct": correct_cnt,
        "incorrect": incorrect_cnt,
        "escalated": escalated_cnt,
        "accuracy": round(correct_cnt / (correct_cnt + incorrect_cnt), 3) if (correct_cnt + incorrect_cnt) else None,
        "top_error_types": top_error_types,
    }

    chat_summary = {
        "got_it": chat_gotit,
        "reexplain_transitions": sorted(chat_reexplain_levels.items()),
        "ui_errors": ui_errors,
    }

    recent_events_out = [
        {
            "event_type": r["event_type"],
            "duration_ms": r["duration_ms"],
            "meta": _safe_meta(r["meta"]),
            "created_at": r["created_at"],
        }
        for r in recent_events
    ]
    effectiveness_events = [
        {
            "event_type": r["event_type"],
            "duration_ms": r["duration_ms"],
            "meta": _safe_meta(r["meta"]),
            "created_at": r["created_at"],
        }
        for r in effectiveness_rows
    ]
    effectiveness = compute_upload_corpus_effectiveness(latest_run_records_from_ai_events(effectiveness_events))
    product_metrics = compute_product_metrics(
        [
            {
                "event_type": r["event_type"],
                "duration_ms": r["duration_ms"],
                "meta": r["meta"],
                "created_at": r.get("created_at") if hasattr(r, "get") else None,
            }
            for r in ai_rows
        ],
        [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "rating": r["rating"],
                "comment": r["comment"],
                "tags": json.loads(r["tags"] or "[]"),
                "context": _safe_meta(r["context"]),
                "created_at": r["created_at"],
            }
            for r in recent_feedback
        ],
        feedback_total=fb_total,
    )

    return {
        "feedback_total": fb_total,
        "feedback_recent_7d": fb_recent,
        "avg_rating": round(avg_rating, 2) if avg_rating is not None else None,
        "low_rating_count": low_rating_count,
        "low_rating_ratio": round(low_rating_count / rated_count, 3) if rated_count else None,
        "rating_hist": rating_hist,
        "top_tags": top_tags,
        "ai_stats": ai_stats,
        "pipeline_funnel": pipeline_funnel,
        "grading_summary": grading_summary,
        "chat_summary": chat_summary,
        "effectiveness": effectiveness,
        "product_metrics": product_metrics,
        "recent_events": recent_events_out,
        "recent_feedback": [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "rating": r["rating"],
                "comment": r["comment"],
                "tags": json.loads(r["tags"] or "[]"),
                "context": _safe_meta(r["context"]),
                "created_at": r["created_at"],
            }
            for r in recent_feedback
        ],
    }


def _check_token(token: str) -> None:
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        raise HTTPException(status_code=403, detail={"error_code": "FORBIDDEN", "message": "invalid admin token"})


@feedback_router.get("/stats")
async def feedback_stats(token: str = Query(...)) -> dict:
    _check_token(token)
    return _compute_stats(int(time.time()))


@feedback_router.get("/effectiveness")
async def feedback_effectiveness(
    token: str = Query(...),
    days: int = Query(7, ge=1, le=90),
) -> dict:
    _check_token(token)
    now_ts = int(time.time())
    since = now_ts - days * 86400
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT event_type, duration_ms, meta, created_at FROM ai_events "
            "WHERE created_at >= ? AND event_type IN (?, ?) ORDER BY id DESC",
            (since, "ui_upload_corpus_asset_result", "upload_corpus_asset_result"),
        ).fetchall()
    finally:
        conn.close()

    events = [
        {
            "event_type": r["event_type"],
            "duration_ms": r["duration_ms"],
            "meta": json.loads(r["meta"] or "{}"),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    records = latest_run_records_from_ai_events(events)
    report = compute_upload_corpus_effectiveness(records)
    return {
        "days": days,
        "event_count": len(events),
        "records": records,
        "effectiveness": report,
    }


_DASHBOARD_HTML = """<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>反馈看板</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; background: #f5f6f8; color: #1f2937; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 20px; }
  h1 { font-size: 20px; margin: 0 0 16px; }
  h2 { font-size: 15px; margin: 24px 0 10px; color: #374151; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
  .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px; }
  .card .label { font-size: 12px; color: #6b7280; }
  .card .value { font-size: 22px; font-weight: 600; margin-top: 4px; color: #111827; }
  .card .sub { font-size: 11px; color: #9ca3af; margin-top: 2px; }
  table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; font-size: 13px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
  th { background: #f9fafb; font-weight: 600; color: #374151; font-size: 12px; }
  tr:last-child td { border-bottom: none; }
  .bar { height: 14px; background: linear-gradient(90deg,#60a5fa,#3b82f6); border-radius: 3px; display: inline-block; vertical-align: middle; }
  .muted { color: #9ca3af; }
  .tag { display: inline-block; background: #eef2ff; color: #4338ca; border-radius: 10px; padding: 1px 8px; margin: 1px 2px; font-size: 11px; }
  .rating { color: #f59e0b; font-weight: 600; }
  .rating-low { color: #ef4444; }
  .empty { text-align: center; padding: 40px; color: #9ca3af; }
  .err { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 14px; border-radius: 10px; }
  code { background: #f3f4f6; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
  .refresh { float: right; font-size: 12px; color: #6b7280; }
  .refresh a { color: #3b82f6; text-decoration: none; }
</style>
</head>
<body>
<div class="wrap">
  <h1>反馈看板 <span class="refresh"><a href="javascript:location.reload()">刷新</a></span></h1>
  <div id="root"><div class="muted">加载中...</div></div>
</div>
<script>
  const params = new URLSearchParams(location.search);
  const token = params.get('token') || '';

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
  }
  function fmtTime(ts) {
    const d = new Date(ts * 1000);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
  function fmtMs(ms) {
    if (ms == null) return '-';
    if (ms < 1000) return ms + ' ms';
    return (ms/1000).toFixed(2) + ' s';
  }
  function fmtMetricValue(m) {
    if (m == null || m.value == null) return '—';
    if (m.unit === 'ms') return fmtMs(m.value);
    if (m.unit === 'count') return m.value;
    return (m.value * 100).toFixed(1) + '%';
  }
  function metricStatus(m) {
    if (!m || m.value == null || m.alert == null) return 'neutral';
    const lower = !!m.lower_is_better;
    if (lower) return m.value > m.alert ? 'alert' : 'ok';
    return m.value < m.alert ? 'alert' : 'ok';
  }
  function statusColor(status) {
    if (status === 'alert') return '#ef4444';
    if (status === 'ok') return '#10b981';
    return '#6b7280';
  }

  function render(data) {
    const root = document.getElementById('root');
    const rh = data.rating_hist || {};
    const maxRH = Math.max(1, ...Object.values(rh));
    const pm = data.product_metrics || {};
    const ns = pm.north_star || {};

    const nsHtml = `
      <div class="cards">
        <div class="card"><div class="label">北极星</div><div class="value">${ns.value != null ? (ns.value * 100).toFixed(1) + '%' : '—'}</div><div class="sub">${escapeHtml(ns.name || '有效学习闭环完成率')} · ${ns.numerator || 0}/${ns.denominator || 0}</div></div>
        <div class="card"><div class="label">上传到结果成功率</div><div class="value">${(() => {
          const m = (pm.node_metrics || []).find(x => x.node === '系统稳定性' && x.metric === '上传到完成率');
          return fmtMetricValue(m);
        })()}</div></div>
        <div class="card"><div class="label">首题可见 P95</div><div class="value">${(() => {
          const m = (pm.node_metrics || []).find(x => x.node === '结果页' && x.metric === '首题可见 P95 耗时');
          return fmtMetricValue(m);
        })()}</div></div>
        <div class="card"><div class="label">人工抽检分数一致</div><div class="value">${pm.quality_review?.score_accuracy_rate != null ? (pm.quality_review.score_accuracy_rate * 100).toFixed(1) + '%' : '—'}</div><div class="sub">样本 ${pm.quality_review?.sample_count || 0}</div></div>
      </div>
    `;

    const loopFunnelHtml = (pm.learning_loop_funnel || []).length
      ? '<table><thead><tr><th>节点</th><th>事件</th><th>次数</th><th>上一步转化</th></tr></thead><tbody>'
        + pm.learning_loop_funnel.map(row => {
            const max = Math.max(1, ...pm.learning_loop_funnel.map(x => x.count || 0));
            const w = Math.max(3, Math.round((row.count || 0) / max * 100));
            return `<tr><td>${escapeHtml(row.label)}</td><td><code>${escapeHtml(row.key)}</code></td><td><span class="bar" style="width:${w}%"></span> ${row.count || 0}</td><td>${row.rate_from_previous == null ? '—' : (row.rate_from_previous * 100).toFixed(1) + '%'}</td></tr>`;
          }).join('')
        + '</tbody></table>'
      : '<div class="empty">暂无全链路漏斗数据</div>';

    const nodeMetricsHtml = (pm.node_metrics || []).length
      ? '<table><thead><tr><th>节点</th><th>指标</th><th>当前值</th><th>目标</th><th>告警线</th><th>状态</th></tr></thead><tbody>'
        + pm.node_metrics.map(m => {
            const st = metricStatus(m);
            const target = m.target == null ? '—' : (m.unit === 'ms' ? fmtMs(m.target) : m.unit === 'count' ? m.target : (m.target * 100).toFixed(0) + '%');
            const alert = m.alert == null ? '—' : (m.unit === 'ms' ? fmtMs(m.alert) : m.unit === 'count' ? m.alert : (m.alert * 100).toFixed(0) + '%');
            return `<tr><td>${escapeHtml(m.node)}</td><td>${escapeHtml(m.metric)}</td><td>${fmtMetricValue(m)}</td><td>${target}</td><td>${alert}</td><td style="color:${statusColor(st)};font-weight:600">${st === 'alert' ? '告警' : st === 'ok' ? '正常' : '观察'}</td></tr>`;
          }).join('')
        + '</tbody></table>'
      : '<div class="empty">暂无节点指标</div>';

    const qualityHtml = `
      <div class="cards">
        <div class="card"><div class="label">抽检样本</div><div class="value">${pm.quality_review?.sample_count || 0}</div></div>
        <div class="card"><div class="label">判分一致率</div><div class="value">${pm.quality_review?.score_accuracy_rate != null ? (pm.quality_review.score_accuracy_rate * 100).toFixed(1) + '%' : '—'}</div></div>
        <div class="card"><div class="label">讲解具体率</div><div class="value">${pm.quality_review?.explanation_quality_rate != null ? (pm.quality_review.explanation_quality_rate * 100).toFixed(1) + '%' : '—'}</div></div>
        <div class="card"><div class="label">错误高置信样本</div><div class="value" style="color:#ef4444">${pm.quality_review?.high_confidence_errors || 0}</div></div>
      </div>
      ${(pm.quality_review?.top_issue_tags || []).length ? '<table style="margin-top:10px"><thead><tr><th>抽检问题标签</th><th>次数</th></tr></thead><tbody>'
        + pm.quality_review.top_issue_tags.map(([t,n]) => `<tr><td>${escapeHtml(t)}</td><td>${n}</td></tr>`).join('')
        + '</tbody></table>' : ''}
    `;

    const tagsHtml = (data.top_tags || []).length
      ? '<table><thead><tr><th>标签</th><th style="width:60%">出现</th></tr></thead><tbody>'
        + data.top_tags.map(([t, n]) => {
            const w = Math.round(n/data.top_tags[0][1]*100);
            return `<tr><td>${escapeHtml(t)}</td><td><span class="bar" style="width:${w}%"></span> ${n}</td></tr>`;
          }).join('')
        + '</tbody></table>'
      : '<div class="empty">暂无标签数据</div>';

    // 按前缀分组事件：后端 AI / 后端 pipeline / 前端 UI
    const _classify = (et) => {
      if (et.startsWith('ui_')) return 'ui';
      if (et.startsWith('pipeline_') || et === 'upload_received' || et === 'segment_done' ||
          et === 'question_graded' || et === 'question_unanswered' ||
          et === 'solution_inline_done' || et === 'session_done' || et === 'multi_agent_consensus') return 'pipeline';
      return 'ai';
    };
    const _statsTable = (stats) => stats.length
      ? '<table><thead><tr><th>事件</th><th>次数</th><th>近7天</th><th>平均</th><th>P50</th><th>P95</th><th>最大</th></tr></thead><tbody>'
        + stats.map(s =>
            `<tr><td><code>${escapeHtml(s.event_type)}</code></td><td>${s.count}</td><td>${s.recent_7d||0}</td><td>${fmtMs(s.avg_ms)}</td><td>${fmtMs(s.p50_ms)}</td><td>${fmtMs(s.p95_ms)}</td><td>${fmtMs(s.max_ms)}</td></tr>`
          ).join('')
        + '</tbody></table>'
      : '<div class="empty">暂无数据</div>';
    const allStats = data.ai_stats || [];
    const aiStats = allStats.filter(s => _classify(s.event_type) === 'ai');
    const pipelineStats = allStats.filter(s => _classify(s.event_type) === 'pipeline');
    const uiStats = allStats.filter(s => _classify(s.event_type) === 'ui');
    const aiHtml = _statsTable(aiStats);
    const pipelineStatsHtml = _statsTable(pipelineStats);
    const uiStatsHtml = _statsTable(uiStats);

    // Pipeline 漏斗
    const funnel = data.pipeline_funnel || {};
    const funnelRows = [
      ['upload_received', '上传'],
      ['session_done', '整轮完成'],
      ['question_graded', '单题批改'],
      ['question_unanswered', '未作答题目'],
      ['solution_inline_done', '解题思路生成'],
    ];
    const funnelMax = Math.max(1, ...funnelRows.map(([k]) => funnel[k] || 0));
    const funnelHtml = '<table><tbody>' + funnelRows.map(([k, label]) => {
      const n = funnel[k] || 0;
      const w = Math.round(n / funnelMax * 100);
      return `<tr><td style="width:140px">${label}<br><code style="font-size:10px">${k}</code></td><td><span class="bar" style="width:${w}%"></span> ${n}</td></tr>`;
    }).join('') + '</tbody></table>';

    // 批改汇总
    const gs = data.grading_summary || {};
    const gradingHtml = `
      <div class="cards">
        <div class="card"><div class="label">正确题目</div><div class="value" style="color:#10b981">${gs.correct||0}</div></div>
        <div class="card"><div class="label">错误题目</div><div class="value" style="color:#ef4444">${gs.incorrect||0}</div></div>
        <div class="card"><div class="label">正确率</div><div class="value">${gs.accuracy!=null?(gs.accuracy*100).toFixed(1)+'%':'—'}</div></div>
        <div class="card"><div class="label">升级复核</div><div class="value">${gs.escalated||0}</div><div class="sub">触发 review 模型</div></div>
      </div>
      ${(gs.top_error_types||[]).length ? '<table style="margin-top:10px"><thead><tr><th>错误类型</th><th>次数</th></tr></thead><tbody>'
        + gs.top_error_types.map(([t,n]) => `<tr><td>${escapeHtml(t)}</td><td>${n}</td></tr>`).join('')
        + '</tbody></table>' : ''}
    `;

    // 聊天行为
    const cs = data.chat_summary || {};
    const chatHtml = `
      <div class="cards">
        <div class="card"><div class="label">✅ 听懂了</div><div class="value">${cs.got_it||0}</div></div>
        <div class="card"><div class="label">🔄 换个方式</div><div class="value">${(cs.reexplain_transitions||[]).reduce((a,[,n])=>a+n,0)}</div></div>
        <div class="card"><div class="label">前端运行时错误</div><div class="value" style="color:#ef4444">${cs.ui_errors||0}</div></div>
      </div>
      ${(cs.reexplain_transitions||[]).length ? '<table style="margin-top:10px"><thead><tr><th>层级切换</th><th>次数</th></tr></thead><tbody>'
        + cs.reexplain_transitions.map(([k,n]) => `<tr><td><code>${escapeHtml(k)}</code></td><td>${n}</td></tr>`).join('')
        + '</tbody></table>' : ''}
    `;

    // 上传语料库效果评测
    const eff = data.effectiveness || {};
    const effMetrics = eff.metrics || {};
    const effMetricRows = Object.entries(effMetrics);
    const effColor = eff.overall_status === 'pass' ? '#10b981' : eff.overall_status === 'fail' ? '#ef4444' : '#9ca3af';
    const effHtml = `
      <div class="cards">
        <div class="card"><div class="label">综合分</div><div class="value" style="color:${effColor}">${eff.overall_score ?? '—'}</div><div class="sub">${escapeHtml(eff.overall_status || 'insufficient_data')}</div></div>
        <div class="card"><div class="label">记录数</div><div class="value">${eff.summary?.records ?? 0}</div><div class="sub">最近 7 天上传回放</div></div>
        <div class="card"><div class="label">成功记录</div><div class="value">${eff.summary?.successful_records ?? 0}</div></div>
        <div class="card"><div class="label">失败指标</div><div class="value" style="color:#ef4444">${(eff.failures || []).length}</div></div>
      </div>
      ${effMetricRows.length ? '<table style="margin-top:10px"><thead><tr><th>指标</th><th>状态</th><th>当前值</th><th>目标</th><th>样本数</th></tr></thead><tbody>'
        + effMetricRows.map(([key, m]) => {
            const color = m.status === 'pass' ? '#10b981' : m.status === 'fail' ? '#ef4444' : '#9ca3af';
            const value = m.value == null ? '—' : (m.unit === 'ms' ? fmtMs(m.value) : (m.value * 100).toFixed(1) + '%');
            const target = m.target == null ? '—' : (m.unit === 'ms' ? fmtMs(m.target) : (m.target * 100).toFixed(0) + '%');
            return `<tr><td>${escapeHtml(m.label || key)}<br><code>${escapeHtml(key)}</code></td><td style="color:${color};font-weight:600">${escapeHtml(m.status)}</td><td>${value}</td><td>${target}</td><td>${m.sample_size || 0}</td></tr>`;
          }).join('')
        + '</tbody></table>' : '<div class="empty">还没有上传语料库评测数据。运行 <code>python scripts/evaluate_upload_corpus.py --track-events</code> 后会出现在这里。</div>'}
    `;

    // 事件流（最近 100 条）
    const evHtml = (data.recent_events || []).length
      ? '<table><thead><tr><th>时间</th><th>事件</th><th>时长</th><th>meta</th></tr></thead><tbody>'
        + data.recent_events.slice(0, 80).map(e => {
            const metaStr = JSON.stringify(e.meta || {});
            const short = metaStr.length > 140 ? metaStr.slice(0, 140) + '…' : metaStr;
            return `<tr><td class="muted" style="white-space:nowrap">${fmtTime(e.created_at)}</td><td><code>${escapeHtml(e.event_type)}</code></td><td>${e.duration_ms?fmtMs(e.duration_ms):'—'}</td><td style="font-size:11px;color:#6b7280">${escapeHtml(short)}</td></tr>`;
          }).join('')
        + '</tbody></table>'
      : '<div class="empty">暂无事件</div>';

    const fbHtml = (data.recent_feedback || []).length
      ? '<table><thead><tr><th>时间</th><th>用户</th><th>评分</th><th>标签</th><th>文字</th></tr></thead><tbody>'
        + data.recent_feedback.map(f => {
            const ctx = f.context || {};
            const who = ctx.profile_name
              ? `${escapeHtml(ctx.profile_name)} <span class="muted">(${escapeHtml(ctx.profile_phone || '')}${ctx.profile_grade ? ' / ' + escapeHtml(ctx.profile_grade) : ''})</span>`
              : `<span class="muted">${escapeHtml(f.user_id)}</span>`;
            const ratingCls = (f.rating != null && f.rating <= 3) ? 'rating rating-low' : 'rating';
            const ratingHtml = f.rating != null ? `<span class="${ratingCls}">${'★'.repeat(f.rating)}${'☆'.repeat(5-f.rating)}</span>` : '<span class="muted">—</span>';
            const tagHtml = (f.tags || []).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join(' ');
            return `<tr><td class="muted">${fmtTime(f.created_at)}</td><td>${who}</td><td>${ratingHtml}</td><td>${tagHtml}</td><td>${escapeHtml(f.comment || '')}</td></tr>`;
          }).join('')
        + '</tbody></table>'
      : '<div class="empty">暂无反馈</div>';

    const rhHtml = Object.keys(rh).length
      ? [5,4,3,2,1].map(k => {
          const n = rh[k] || 0;
          const w = Math.round(n/maxRH*100);
          return `<tr><td style="width:60px">${'★'.repeat(k)}</td><td><span class="bar" style="width:${w}%"></span> ${n}</td></tr>`;
        }).join('')
      : '';

    root.innerHTML = `
      <div class="cards">
        <div class="card"><div class="label">反馈总数</div><div class="value">${data.feedback_total}</div></div>
        <div class="card"><div class="label">近 7 天反馈</div><div class="value">${data.feedback_recent_7d}</div></div>
        <div class="card"><div class="label">平均评分</div><div class="value">${data.avg_rating != null ? data.avg_rating : '—'}</div><div class="sub">满分 5 星</div></div>
        <div class="card"><div class="label">差评数 (≤3★)</div><div class="value" style="color:#ef4444">${data.low_rating_count}</div><div class="sub">${data.low_rating_ratio != null ? (data.low_rating_ratio*100).toFixed(1)+'%' : '—'}</div></div>
      </div>

      <h2>全链路北极星</h2>
      ${nsHtml}

      <h2>有效学习闭环漏斗</h2>
      ${loopFunnelHtml}

      <h2>节点测试指标</h2>
      ${nodeMetricsHtml}

      <h2>批改讲解质量抽检</h2>
      ${qualityHtml}

      ${rhHtml ? `<h2>评分分布</h2><table><tbody>${rhHtml}</tbody></table>` : ''}

      <h2>标签 TOP</h2>
      ${tagsHtml}

      <h2>Pipeline 漏斗（累计）</h2>
      ${funnelHtml}

      <h2>批改表现</h2>
      ${gradingHtml}

      <h2>聊天追问行为</h2>
      ${chatHtml}

      <h2>上传语料库效果评测</h2>
      ${effHtml}

      <h2>AI 调用时长（后端模型）</h2>
      ${aiHtml}

      <h2>Pipeline 阶段耗时</h2>
      ${pipelineStatsHtml}

      <h2>前端 UI 事件</h2>
      ${uiStatsHtml}

      <h2>最近事件流</h2>
      ${evHtml}

      <h2>最近 50 条反馈</h2>
      ${fbHtml}
    `;
  }

  if (!token) {
    document.getElementById('root').innerHTML = '<div class="err">缺少 token 参数。访问 <code>/feedback/dashboard?token=&lt;ADMIN_TOKEN&gt;</code></div>';
  } else {
    fetch('/feedback/stats?token=' + encodeURIComponent(token))
      .then(r => r.ok ? r.json() : r.json().then(e => { throw new Error(e?.detail?.message || ('HTTP ' + r.status)); }))
      .then(render)
      .catch(e => {
        document.getElementById('root').innerHTML = '<div class="err">加载失败：' + escapeHtml(e.message) + '</div>';
      });
  }
</script>
</body>
</html>
"""


@feedback_router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def feedback_dashboard() -> HTMLResponse:
    # HTML 页本身不校验 token（页面内 JS 自己拿 token 调 /stats）
    return HTMLResponse(_DASHBOARD_HTML)
