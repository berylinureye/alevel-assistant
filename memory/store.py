"""SQLite-backed User Memory store.

跨 session 持久化 4 类 fact：weakness / preference / progress / goal。
Conflict Resolution：旧 fact 不直接覆盖，confidence × 0.5 decay。
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator


class FactType(str, Enum):
    weakness = "weakness"      # 反复栽的薄弱知识点
    preference = "preference"  # 解题偏好 / 学习风格
    progress = "progress"      # 已掌握的章节进度
    goal = "goal"              # 目标分数 / 长期 goal


@dataclass
class StudentFact:
    student_id: str
    fact_type: FactType
    fact_text: str
    topic: str | None = None
    confidence: float = 1.0
    source_session_id: str | None = None
    updated_at: float = field(default_factory=time.time)
    rowid: int | None = None  # SQLite rowid，查询后填

    def to_row(self) -> tuple:
        return (
            self.student_id,
            self.fact_type.value,
            self.fact_text,
            self.topic,
            self.confidence,
            self.source_session_id,
            self.updated_at,
        )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS student_facts (
    rowid             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        TEXT    NOT NULL,
    fact_type         TEXT    NOT NULL,
    fact_text         TEXT    NOT NULL,
    topic             TEXT,
    confidence        REAL    NOT NULL DEFAULT 1.0,
    source_session_id TEXT,
    updated_at        REAL    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_facts_student
    ON student_facts (student_id, fact_type);

CREATE INDEX IF NOT EXISTS idx_facts_topic
    ON student_facts (student_id, topic);
"""


class MemoryStore:
    """SQLite store · 单进程线程安全（每次 get_facts/save_fact 自开连接）"""

    def __init__(self, db_path: str | Path = "data/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ──────────────────────────────────────────────────────
    # 写
    # ──────────────────────────────────────────────────────
    def save_fact(self, fact: StudentFact) -> int:
        """新 fact 不覆盖已有，调用方应先 conflict-resolve。返回 rowid。"""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO student_facts
                    (student_id, fact_type, fact_text, topic, confidence,
                     source_session_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                fact.to_row(),
            )
            return cur.lastrowid

    def save_facts_with_conflict_resolve(
        self,
        student_id: str,
        new_facts: list[StudentFact],
    ) -> dict:
        """新一批 fact 入库前先检测冲突（同 student + 同 topic + 同 fact_type）。

        冲突策略：
        - 旧 fact confidence × 0.5（不直接删除）
        - 新 fact 也存入（保留历史）
        - 一旦旧 fact confidence < 0.05 → 删除（实际"遗忘"）

        Returns
        -------
        dict: {"saved": N, "decayed": N, "forgotten": N}
        """
        saved = decayed = forgotten = 0
        with self._connect() as conn:
            for fact in new_facts:
                # 找冲突
                conflicts = conn.execute(
                    """
                    SELECT rowid, confidence FROM student_facts
                    WHERE student_id = ? AND fact_type = ?
                      AND (topic = ? OR (topic IS NULL AND ? IS NULL))
                    """,
                    (student_id, fact.fact_type.value, fact.topic, fact.topic),
                ).fetchall()

                for rowid, old_conf in conflicts:
                    new_conf = old_conf * 0.5
                    if new_conf < 0.05:
                        conn.execute("DELETE FROM student_facts WHERE rowid = ?", (rowid,))
                        forgotten += 1
                    else:
                        conn.execute(
                            "UPDATE student_facts SET confidence = ? WHERE rowid = ?",
                            (new_conf, rowid),
                        )
                        decayed += 1

                # 新 fact 入库
                conn.execute(
                    """
                    INSERT INTO student_facts
                        (student_id, fact_type, fact_text, topic, confidence,
                         source_session_id, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    fact.to_row(),
                )
                saved += 1

        return {"saved": saved, "decayed": decayed, "forgotten": forgotten}

    # ──────────────────────────────────────────────────────
    # 读
    # ──────────────────────────────────────────────────────
    def get_facts(
        self,
        student_id: str,
        fact_type: FactType | None = None,
        topic: str | None = None,
        min_confidence: float = 0.1,
    ) -> list[StudentFact]:
        """查询学生的 fact，按 confidence 倒序 + updated_at 倒序"""
        where = ["student_id = ?", "confidence >= ?"]
        params: list = [student_id, min_confidence]

        if fact_type is not None:
            where.append("fact_type = ?")
            params.append(fact_type.value)

        if topic is not None:
            where.append("topic = ?")
            params.append(topic)

        sql = f"""
            SELECT rowid, student_id, fact_type, fact_text, topic, confidence,
                   source_session_id, updated_at
            FROM student_facts
            WHERE {' AND '.join(where)}
            ORDER BY confidence DESC, updated_at DESC
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            StudentFact(
                rowid=row[0],
                student_id=row[1],
                fact_type=FactType(row[2]),
                fact_text=row[3],
                topic=row[4],
                confidence=row[5],
                source_session_id=row[6],
                updated_at=row[7],
            )
            for row in rows
        ]

    def get_memory_prompt(self, student_id: str, max_facts: int = 10) -> str:
        """打包学生 fact 成 prompt 段落，injection 进 grader / formatter"""
        facts = self.get_facts(student_id, min_confidence=0.3)[:max_facts]
        if not facts:
            return ""

        lines = ["## 这位学生的已知背景（按 confidence 排序）"]
        for f in facts:
            tag = {
                FactType.weakness:   "⚠️ 薄弱点",
                FactType.preference: "💡 偏好",
                FactType.progress:   "✅ 进度",
                FactType.goal:       "🎯 目标",
            }[f.fact_type]
            topic_str = f" [{f.topic}]" if f.topic else ""
            lines.append(f"- {tag}{topic_str} ({f.confidence:.2f}): {f.fact_text}")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────
    # 用户权利（GDPR）
    # ──────────────────────────────────────────────────────
    def export_all(self, student_id: str) -> list[dict]:
        """导出学生所有 fact 为 JSON-serializable list"""
        facts = self.get_facts(student_id, min_confidence=0.0)
        return [asdict(f) for f in facts]

    def delete_all(self, student_id: str) -> int:
        """删除学生所有 fact，返回删除数"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM student_facts WHERE student_id = ?", (student_id,))
            return cur.rowcount

    def delete_fact(self, rowid: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM student_facts WHERE rowid = ?", (rowid,))
            return cur.rowcount > 0
