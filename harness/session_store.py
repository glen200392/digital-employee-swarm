"""
Session Store — SQLite 持久化
儲存 Agent 的任務歷史、Session 結果、評估分數。
取代 git_memory 的 progress.log，提供結構化查詢能力。
"""
import sqlite3
import json
import datetime
import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

DB_PATH = os.getenv("SESSION_DB_PATH", "./data/sessions.db")


@dataclass
class SessionRecord:
    agent_name: str
    task_id: str
    task: str
    output: str
    risk_level: str
    eval_score: float
    success: bool
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None


class SessionStore:
    """
    SQLite-backed Session Store。
    提供：
    - save_session()：儲存一次 Agent Session 結果
    - get_last_sessions(agent_name, limit)：取得最近 N 次 Session
    - get_sessions_by_task(keyword)：關鍵字搜尋歷史任務
    - get_agent_stats(agent_name)：取得 Agent 統計（任務數、平均分、成功率）
    - search_context(agent_name, limit)：恢復 Agent 上下文（取代 git_memory.get_last_context）
    - set_memory / get_memory：持久化 key-value 記憶
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path) if os.path.dirname(db_path) else "."
        os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """建立資料表（若不存在）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT    NOT NULL,
                    task_id    TEXT    NOT NULL,
                    task       TEXT    NOT NULL,
                    output     TEXT    NOT NULL,
                    risk_level TEXT    NOT NULL DEFAULT 'LOW',
                    eval_score REAL    NOT NULL DEFAULT 0.0,
                    success    INTEGER NOT NULL DEFAULT 1,
                    timestamp  TEXT    NOT NULL,
                    metadata   TEXT    NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT    NOT NULL,
                    key        TEXT    NOT NULL,
                    value      TEXT    NOT NULL,
                    updated_at TEXT    NOT NULL,
                    UNIQUE(agent_name, key)
                )
            """)
            conn.commit()

    def save_session(self, record: SessionRecord) -> int:
        """儲存 Session，回傳 row id"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO sessions
                    (agent_name, task_id, task, output, risk_level,
                     eval_score, success, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.agent_name,
                    record.task_id,
                    record.task,
                    record.output,
                    record.risk_level,
                    record.eval_score,
                    1 if record.success else 0,
                    record.timestamp,
                    json.dumps(record.metadata, ensure_ascii=False),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_last_sessions(self, agent_name: str, limit: int = 10) -> List[SessionRecord]:
        """取得指定 Agent 的最近 N 次 Session"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE agent_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (agent_name, limit),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_sessions_by_task(self, keyword: str) -> List[SessionRecord]:
        """關鍵字搜尋歷史任務（task 欄位）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE task LIKE ?
                ORDER BY id DESC
                """,
                (f"%{keyword}%",),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def search_context(self, agent_name: str, limit: int = 5) -> List[Dict]:
        """
        恢復 Agent 上下文（供 BaseAgent 的 EPCC restore_context 使用）。
        回傳格式與原本 git_memory.get_last_context() 相容（字串列表形式）。
        """
        sessions = self.get_last_sessions(agent_name, limit)
        return [
            {
                "task_id": s.task_id,
                "task": s.task,
                "output": s.output,
                "success": s.success,
                "eval_score": s.eval_score,
                "timestamp": s.timestamp,
            }
            for s in sessions
        ]

    def get_agent_stats(self, agent_name: str) -> Dict:
        """回傳 Agent 的統計資料"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)        AS total,
                    AVG(eval_score) AS avg_score,
                    SUM(success)    AS successes
                FROM sessions
                WHERE agent_name = ?
                """,
                (agent_name,),
            ).fetchone()
        total, avg_score, successes = row
        total = total or 0
        successes = successes or 0
        return {
            "agent_name": agent_name,
            "total_tasks": total,
            "avg_eval_score": round(avg_score or 0.0, 2),
            "success_rate": round(successes / total, 2) if total > 0 else 0.0,
        }

    def set_memory(self, agent_name: str, key: str, value: Any):
        """設定 Agent 的持久化 key-value 記憶"""
        updated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO agent_memory (agent_name, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(agent_name, key)
                DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (agent_name, key, json.dumps(value, ensure_ascii=False), updated_at),
            )
            conn.commit()

    def get_memory(self, agent_name: str, key: str) -> Optional[Any]:
        """取得 Agent 的持久化記憶"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM agent_memory WHERE agent_name = ? AND key = ?",
                (agent_name, key),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    # ------------------------------------------------------------------ #
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            agent_name=row["agent_name"],
            task_id=row["task_id"],
            task=row["task"],
            output=row["output"],
            risk_level=row["risk_level"],
            eval_score=row["eval_score"],
            success=bool(row["success"]),
            timestamp=row["timestamp"],
            metadata=json.loads(row["metadata"]),
        )
