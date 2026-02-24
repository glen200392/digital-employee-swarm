"""
Session Store 模組
使用 SQLite 持久化 Agent Session 記錄，並透過 UNIQUE 約束保證冪等性。
"""

import os
import sqlite3
import datetime
from typing import Any, Dict, List, Optional


class SessionStore:
    """
    SQLite-backed 的 Session 儲存層。
    對 (agent_name, task_id) 施加 UNIQUE 約束，確保同一任務不會重複記錄。
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base, "data", "sessions.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """建立資料表（若不存在），並確保 UNIQUE 約束"""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name  TEXT    NOT NULL,
                    task_id     TEXT    NOT NULL,
                    status      TEXT    NOT NULL,
                    eval_score  REAL    NOT NULL DEFAULT 0.0,
                    risk_level  TEXT    NOT NULL DEFAULT 'LOW',
                    output      TEXT    NOT NULL DEFAULT '',
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL,
                    UNIQUE (agent_name, task_id)
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def save_session(self, agent_name: str, task_id: str, status: str,
                     eval_score: float = 0.0, risk_level: str = "LOW",
                     output: str = "",
                     _now: Optional[str] = None) -> None:
        """
        儲存或更新一筆 Session 記錄。
        若相同 (agent_name, task_id) 已存在，則執行 UPDATE（冪等性保護）。
        _now 參數供測試使用，預設為目前時間。
        """
        now = _now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                    (agent_name, task_id, status, eval_score, risk_level,
                     output, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_name, task_id)
                DO UPDATE SET
                    status     = excluded.status,
                    eval_score = excluded.eval_score,
                    risk_level = excluded.risk_level,
                    output     = excluded.output,
                    updated_at = excluded.updated_at
                """,
                (agent_name, task_id, status, eval_score, risk_level,
                 output, now, now),
            )

    def get_session(self, agent_name: str,
                    task_id: str) -> Optional[Dict[str, Any]]:
        """取得指定 Session 記錄"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM sessions WHERE agent_name = ? AND task_id = ?",
                (agent_name, task_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_sessions(self, agent_name: Optional[str] = None,
                      limit: int = 50) -> List[Dict[str, Any]]:
        """列出 Session 記錄（可依 agent_name 過濾）"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if agent_name:
                cur = conn.execute(
                    "SELECT * FROM sessions WHERE agent_name = ? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (agent_name, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]
