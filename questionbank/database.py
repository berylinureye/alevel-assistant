"""
SQLite 题库数据库操作层

提供同步接口（用于 CLI 脚本和 PDF 解析入库）。
API 层通过 run_in_threadpool 调用这些方法。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from questionbank.models import QuestionBankItem, TopicStats, QuestionBankStats

DB_PATH = Path("data/questions.db")


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> None:
    """初始化数据库表结构"""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code TEXT NOT NULL,
            year        INTEGER NOT NULL,
            session     TEXT NOT NULL,
            paper_num   INTEGER NOT NULL,
            variant     INTEGER DEFAULT 1,
            pdf_path    TEXT,
            ms_pdf_path TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subject_code, year, session, paper_num, variant)
        );

        CREATE TABLE IF NOT EXISTS questions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id        INTEGER REFERENCES papers(id),
            question_number TEXT NOT NULL,
            parent_number   TEXT,
            question_text   TEXT NOT NULL,
            marks           INTEGER DEFAULT 0,
            topic           TEXT DEFAULT 'unknown',
            subtopic        TEXT,
            difficulty      INTEGER DEFAULT 3,
            has_diagram     BOOLEAN DEFAULT 0,
            diagram_description TEXT,
            correct_answer  TEXT,
            marking_points  TEXT,
            common_errors   TEXT,
            source_page     INTEGER,
            parse_confidence REAL DEFAULT 0.0,
            verified        BOOLEAN DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS question_tags (
            question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
            tag         TEXT NOT NULL,
            PRIMARY KEY (question_id, tag)
        );

        CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);
        CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
        CREATE INDEX IF NOT EXISTS idx_questions_paper ON questions(paper_id);
        CREATE INDEX IF NOT EXISTS idx_tags_tag ON question_tags(tag);
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Papers CRUD
# ---------------------------------------------------------------------------

def upsert_paper(
    conn: sqlite3.Connection,
    subject_code: str,
    year: int,
    session: str,
    paper_num: int,
    variant: int = 1,
    pdf_path: str | None = None,
    ms_pdf_path: str | None = None,
) -> int:
    """插入或更新试卷记录，返回 paper_id"""
    cursor = conn.execute(
        """INSERT INTO papers (subject_code, year, session, paper_num, variant, pdf_path, ms_pdf_path)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(subject_code, year, session, paper_num, variant)
           DO UPDATE SET
               pdf_path = COALESCE(excluded.pdf_path, papers.pdf_path),
               ms_pdf_path = COALESCE(excluded.ms_pdf_path, papers.ms_pdf_path)
           RETURNING id""",
        (subject_code, year, session, paper_num, variant, pdf_path, ms_pdf_path),
    )
    row = cursor.fetchone()
    if row:
        return row["id"]
    # 如果 RETURNING 不支持 (旧版 SQLite)，查一下
    cursor = conn.execute(
        "SELECT id FROM papers WHERE subject_code=? AND year=? AND session=? AND paper_num=? AND variant=?",
        (subject_code, year, session, paper_num, variant),
    )
    return cursor.fetchone()["id"]


# ---------------------------------------------------------------------------
# Questions CRUD
# ---------------------------------------------------------------------------

def insert_question(conn: sqlite3.Connection, item: QuestionBankItem) -> int:
    """插入一道题目，返回 question_id"""
    cursor = conn.execute(
        """INSERT INTO questions
           (paper_id, question_number, parent_number, question_text, marks,
            topic, subtopic, difficulty, has_diagram, diagram_description,
            correct_answer, marking_points, common_errors,
            source_page, parse_confidence, verified)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item.paper_id,
            item.question_number,
            item.parent_number,
            item.question_text,
            item.marks,
            item.topic,
            item.subtopic,
            item.difficulty,
            item.has_diagram,
            item.diagram_description,
            item.correct_answer,
            json.dumps(item.marking_points) if item.marking_points else None,
            json.dumps(item.common_errors) if item.common_errors else None,
            item.source_page,
            item.parse_confidence,
            item.verified,
        ),
    )
    qid = cursor.lastrowid

    # 插入标签
    if item.tags:
        conn.executemany(
            "INSERT OR IGNORE INTO question_tags (question_id, tag) VALUES (?, ?)",
            [(qid, tag) for tag in item.tags],
        )

    return qid


def get_random_questions(
    conn: sqlite3.Connection,
    topics: list[str] | None = None,
    difficulty_min: int = 1,
    difficulty_max: int = 5,
    count: int = 5,
    year_from: int | None = None,
    year_to: int | None = None,
    paper_nums: list[int] | None = None,
    exclude_ids: list[int] | None = None,
    verified_only: bool = False,
) -> tuple[list[QuestionBankItem], int]:
    """随机抽题。返回 (题目列表, 总可用数量)。"""

    where_clauses = ["1=1"]
    params: list = []

    if topics:
        placeholders = ",".join("?" for _ in topics)
        where_clauses.append(
            f"""(
                q.topic IN ({placeholders})
                OR q.subtopic IN ({placeholders})
                OR EXISTS (
                    SELECT 1 FROM question_tags qt_filter
                    WHERE qt_filter.question_id = q.id
                      AND qt_filter.tag IN ({placeholders})
                )
            )"""
        )
        params.extend(topics)
        params.extend(topics)
        params.extend(topics)

    where_clauses.append("q.difficulty >= ? AND q.difficulty <= ?")
    params.extend([difficulty_min, difficulty_max])

    if year_from:
        where_clauses.append("p.year >= ?")
        params.append(year_from)

    if year_to:
        where_clauses.append("p.year <= ?")
        params.append(year_to)

    if paper_nums:
        placeholders = ",".join("?" for _ in paper_nums)
        where_clauses.append(f"p.paper_num IN ({placeholders})")
        params.extend(paper_nums)

    if exclude_ids:
        placeholders = ",".join("?" for _ in exclude_ids)
        where_clauses.append(f"q.id NOT IN ({placeholders})")
        params.extend(exclude_ids)

    if verified_only:
        where_clauses.append("q.verified = 1")

    where = " AND ".join(where_clauses)

    # 获取总数
    count_row = conn.execute(
        f"""SELECT COUNT(*) as cnt
            FROM questions q
            LEFT JOIN papers p ON q.paper_id = p.id
            WHERE {where}""",
        params,
    ).fetchone()
    total = count_row["cnt"]

    # 随机抽取
    rows = conn.execute(
        f"""SELECT q.*, p.subject_code, p.year, p.session, p.paper_num, p.variant
            FROM questions q
            LEFT JOIN papers p ON q.paper_id = p.id
            WHERE {where}
            ORDER BY RANDOM()
            LIMIT ?""",
        params + [count],
    ).fetchall()

    questions = []
    for row in rows:
        item = QuestionBankItem(
            id=row["id"],
            paper_id=row["paper_id"],
            question_number=row["question_number"],
            parent_number=row["parent_number"],
            question_text=row["question_text"],
            marks=row["marks"],
            topic=row["topic"] or "unknown",
            subtopic=row["subtopic"],
            difficulty=row["difficulty"],
            has_diagram=bool(row["has_diagram"]),
            diagram_description=row["diagram_description"],
            correct_answer=row["correct_answer"],
            marking_points=json.loads(row["marking_points"]) if row["marking_points"] else None,
            common_errors=json.loads(row["common_errors"]) if row["common_errors"] else None,
            subject_code=row["subject_code"],
            year=row["year"],
            session=row["session"],
            paper_num=row["paper_num"],
            variant=row["variant"],
            source_page=row["source_page"],
            parse_confidence=row["parse_confidence"],
            verified=bool(row["verified"]),
        )

        # 加载标签
        tag_rows = conn.execute(
            "SELECT tag FROM question_tags WHERE question_id = ?", (row["id"],)
        ).fetchall()
        item.tags = [r["tag"] for r in tag_rows]

        questions.append(item)

    return questions, total


def get_question_by_id(conn: sqlite3.Connection, question_id: int) -> QuestionBankItem | None:
    """根据 ID 获取单题"""
    row = conn.execute(
        """SELECT q.*, p.subject_code, p.year, p.session, p.paper_num, p.variant
           FROM questions q
           LEFT JOIN papers p ON q.paper_id = p.id
           WHERE q.id = ?""",
        (question_id,),
    ).fetchone()

    if not row:
        return None

    item = QuestionBankItem(
        id=row["id"],
        paper_id=row["paper_id"],
        question_number=row["question_number"],
        parent_number=row["parent_number"],
        question_text=row["question_text"],
        marks=row["marks"],
        topic=row["topic"] or "unknown",
        subtopic=row["subtopic"],
        difficulty=row["difficulty"],
        has_diagram=bool(row["has_diagram"]),
        correct_answer=row["correct_answer"],
        marking_points=json.loads(row["marking_points"]) if row["marking_points"] else None,
        common_errors=json.loads(row["common_errors"]) if row["common_errors"] else None,
        subject_code=row["subject_code"],
        year=row["year"],
        session=row["session"],
        paper_num=row["paper_num"],
        variant=row["variant"],
        parse_confidence=row["parse_confidence"],
        verified=bool(row["verified"]),
    )

    tag_rows = conn.execute(
        "SELECT tag FROM question_tags WHERE question_id = ?", (question_id,)
    ).fetchall()
    item.tags = [r["tag"] for r in tag_rows]

    return item


def get_all_topics(conn: sqlite3.Connection) -> list[TopicStats]:
    """获取所有知识点及统计"""
    rows = conn.execute("""
        SELECT q.topic,
               COUNT(*) as cnt,
               AVG(q.difficulty) as avg_diff,
               MIN(p.year) as min_year,
               MAX(p.year) as max_year
        FROM questions q
        LEFT JOIN papers p ON q.paper_id = p.id
        WHERE q.topic != 'unknown'
        GROUP BY q.topic
        ORDER BY cnt DESC
    """).fetchall()

    return [
        TopicStats(
            topic=row["topic"],
            count=row["cnt"],
            avg_difficulty=round(row["avg_diff"], 1),
            year_range=f"{row['min_year']}-{row['max_year']}",
        )
        for row in rows
    ]


def get_stats(conn: sqlite3.Connection) -> QuestionBankStats:
    """获取题库总体统计"""
    q_count = conn.execute("SELECT COUNT(*) as cnt FROM questions").fetchone()["cnt"]
    p_count = conn.execute("SELECT COUNT(*) as cnt FROM papers").fetchone()["cnt"]

    year_row = conn.execute("SELECT MIN(year) as y1, MAX(year) as y2 FROM papers").fetchone()
    year_range = f"{year_row['y1'] or '?'}-{year_row['y2'] or '?'}"

    verified = conn.execute("SELECT COUNT(*) as cnt FROM questions WHERE verified=1").fetchone()["cnt"]
    unverified = q_count - verified

    topics = get_all_topics(conn)

    return QuestionBankStats(
        total_questions=q_count,
        total_papers=p_count,
        year_range=year_range,
        topics=topics,
        verified_count=verified,
        unverified_count=unverified,
    )


# ---------------------------------------------------------------------------
# 初始化入口
# ---------------------------------------------------------------------------

def ensure_db() -> sqlite3.Connection:
    """确保数据库已初始化，返回连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    init_db(DB_PATH)
    return get_connection(DB_PATH)
