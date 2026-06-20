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

    def _pct(xs: List[int], p: float) -> int:
        if not xs:
            return 0
        s = sorted(xs)
        i = min(len(s) - 1, int(len(s) * p))
        return s[i]

    recent_counts = {r["event_type"]: r["c"] for r in ai_recent_rows}
    ai_stats = [
        {
            "event_type": et,
            "count": len(xs),
            "recent_7d": recent_counts.get(et, 0),
            "avg_ms": int(sum(xs) / len(xs)) if xs else 0,
            "p50_ms": _pct(xs, 0.50),
            "p95_ms": _pct(xs, 0.95),
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
            try:
                graded_meta.append(json.loads(r["meta"] or "{}"))
            except Exception:
                pass
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
        try:
            m = json.loads(r["meta"] or "{}")
        except Exception:
            m = {}
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
            "meta": json.loads(r["meta"] or "{}"),
            "created_at": r["created_at"],
        }
        for r in recent_events
    ]

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
        "recent_events": recent_events_out,
        "recent_feedback": [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "rating": r["rating"],
                "comment": r["comment"],
                "tags": json.loads(r["tags"] or "[]"),
                "context": json.loads(r["context"] or "{}"),
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

  function render(data) {
    const root = document.getElementById('root');
    const rh = data.rating_hist || {};
    const maxRH = Math.max(1, ...Object.values(rh));

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

      ${rhHtml ? `<h2>评分分布</h2><table><tbody>${rhHtml}</tbody></table>` : ''}

      <h2>标签 TOP</h2>
      ${tagsHtml}

      <h2>Pipeline 漏斗（累计）</h2>
      ${funnelHtml}

      <h2>批改表现</h2>
      ${gradingHtml}

      <h2>聊天追问行为</h2>
      ${chatHtml}

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
