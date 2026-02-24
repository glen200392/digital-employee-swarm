"""
非同步任務佇列系統
SQLite-backed 優先級佇列，讓任務提交與執行解耦。
支援優先級排程、失敗重試、Webhook 回調。
"""

import sqlite3
import json
import uuid
import datetime
import os
import logging
import threading
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    CRITICAL = 0   # 最高優先級（如 HIGH 風險任務需立即處理）
    HIGH = 1
    NORMAL = 2
    LOW = 3


class TaskStatus(Enum):
    PENDING = "pending"                    # 等待執行
    RUNNING = "running"                    # 執行中
    COMPLETED = "completed"               # 成功完成
    FAILED = "failed"                     # 執行失敗
    CANCELLED = "cancelled"               # 已取消
    WAITING_APPROVAL = "waiting_approval" # 等待 HITL 審批


@dataclass
class QueuedTask:
    task_id: str
    agent_name: str
    instruction: str
    priority: TaskPriority
    status: TaskStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    callback_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskQueue:
    """
    SQLite-backed 非同步任務佇列。

    特性：
    - 優先級排程（CRITICAL > HIGH > NORMAL > LOW）
    - 同優先級下先進先出（FIFO）
    - 失敗自動重試（最多 max_retries 次，指數退避）
    - Webhook 回調通知（任務完成/失敗時 POST 到 callback_url）
    - 支援取消待執行的任務
    - Worker 執行緒在背景持續消費任務
    """

    def __init__(
        self,
        db_path: str = "data/task_queue.db",
        num_workers: int = 2,
        agent_executor: Optional[Callable] = None,
    ):
        """
        agent_executor: 呼叫形式為 executor(agent_name, instruction) -> str
        通常是 MasterOrchestrator._execute_for_queue
        """
        self.db_path = db_path
        self.num_workers = num_workers
        self.agent_executor = agent_executor

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._running = False
        self._workers: List[threading.Thread] = []
        self._lock = threading.Lock()

        self._init_db()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        agent_name: str,
        instruction: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        callback_url: Optional[str] = None,
        metadata: Dict = None,
    ) -> str:
        """加入任務，返回 task_id"""
        task_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        meta_json = json.dumps(metadata or {})

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tasks
                    (task_id, agent_name, instruction, priority, status,
                     created_at, retry_count, max_retries, callback_url, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    task_id, agent_name, instruction,
                    priority.value, TaskStatus.PENDING.value,
                    now, 0, 3, callback_url, meta_json,
                ),
            )
            conn.commit()

        logger.info(
            "[TaskQueue] Enqueued task_id=%s agent=%s priority=%s",
            task_id, agent_name, priority.name,
        )
        return task_id

    def cancel(self, task_id: str) -> bool:
        """取消 PENDING 狀態的任務"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE tasks SET status=? WHERE task_id=? AND status=?",
                (TaskStatus.CANCELLED.value, task_id, TaskStatus.PENDING.value),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_status(self, task_id: str) -> Optional[QueuedTask]:
        """查詢任務狀態"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def get_pending_tasks(self, agent_name: Optional[str] = None) -> List[QueuedTask]:
        """查詢待執行任務列表"""
        with sqlite3.connect(self.db_path) as conn:
            if agent_name:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status=? AND agent_name=? ORDER BY priority ASC, created_at ASC",
                    (TaskStatus.PENDING.value, agent_name),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status=? ORDER BY priority ASC, created_at ASC",
                    (TaskStatus.PENDING.value,),
                ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_queue_stats(self) -> Dict:
        """返回佇列統計資訊"""
        today = datetime.datetime.utcnow().date().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            pending = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=?",
                (TaskStatus.PENDING.value,),
            ).fetchone()[0]

            running = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=?",
                (TaskStatus.RUNNING.value,),
            ).fetchone()[0]

            completed_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=? AND completed_at LIKE ?",
                (TaskStatus.COMPLETED.value, f"{today}%"),
            ).fetchone()[0]

            failed_today = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=? AND completed_at LIKE ?",
                (TaskStatus.FAILED.value, f"{today}%"),
            ).fetchone()[0]

            # avg wait time: time from created_at to started_at for completed tasks today
            rows = conn.execute(
                "SELECT created_at, started_at FROM tasks "
                "WHERE started_at IS NOT NULL AND created_at LIKE ?",
                (f"{today}%",),
            ).fetchall()

        wait_times = []
        for created_at, started_at in rows:
            try:
                c = datetime.datetime.fromisoformat(created_at)
                s = datetime.datetime.fromisoformat(started_at)
                wait_times.append((s - c).total_seconds())
            except (ValueError, TypeError):
                pass

        avg_wait = round(sum(wait_times) / len(wait_times), 2) if wait_times else 0.0

        return {
            "pending": pending,
            "running": running,
            "completed_today": completed_today,
            "failed_today": failed_today,
            "avg_wait_time_sec": avg_wait,
            "worker_count": self.num_workers,
        }

    def start(self):
        """啟動背景 Worker 執行緒"""
        if self._running:
            return
        self._running = True
        self._workers = []
        for i in range(self.num_workers):
            t = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True,
                name=f"task-queue-worker-{i}",
            )
            t.start()
            self._workers.append(t)
        logger.info("[TaskQueue] Started %d workers", self.num_workers)

    def stop(self, graceful: bool = True):
        """停止 Worker（graceful=True 會等待當前任務完成）"""
        self._running = False
        if graceful:
            for t in self._workers:
                t.join(timeout=30)
        self._workers = []
        logger.info("[TaskQueue] Stopped workers (graceful=%s)", graceful)

    # ------------------------------------------------------------------
    # Worker internals
    # ------------------------------------------------------------------

    def _worker_loop(self, worker_id: int):
        """Worker 執行緒主迴圈"""
        logger.debug("[TaskQueue] Worker-%d started", worker_id)
        while self._running:
            task = self._dequeue_next()
            if task:
                self._execute_task(task)
            else:
                time.sleep(0.5)
        logger.debug("[TaskQueue] Worker-%d stopped", worker_id)

    def _dequeue_next(self) -> Optional[QueuedTask]:
        """從佇列取出最高優先級的 PENDING 任務（原子操作）"""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT * FROM tasks
                    WHERE status=?
                    ORDER BY priority ASC, created_at ASC
                    LIMIT 1
                    """,
                    (TaskStatus.PENDING.value,),
                ).fetchone()
                if row is None:
                    return None
                task = self._row_to_task(row)
                now = datetime.datetime.utcnow().isoformat()
                conn.execute(
                    "UPDATE tasks SET status=?, started_at=? WHERE task_id=? AND status=?",
                    (TaskStatus.RUNNING.value, now, task.task_id, TaskStatus.PENDING.value),
                )
                conn.commit()
                # verify we actually claimed the task (no race)
                updated = conn.execute(
                    "SELECT status FROM tasks WHERE task_id=?",
                    (task.task_id,),
                ).fetchone()
                if updated and updated[0] == TaskStatus.RUNNING.value:
                    task.status = TaskStatus.RUNNING
                    task.started_at = now
                    return task
                return None

    def _execute_task(self, task: QueuedTask):
        """執行任務，處理重試和 Webhook 通知"""
        logger.info(
            "[TaskQueue] Executing task_id=%s agent=%s", task.task_id, task.agent_name
        )
        try:
            if self.agent_executor is None:
                raise RuntimeError("No agent_executor configured")
            result = self.agent_executor(task.agent_name, task.instruction)
            now = datetime.datetime.utcnow().isoformat()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE tasks SET status=?, completed_at=?, result=? WHERE task_id=?",
                    (TaskStatus.COMPLETED.value, now, str(result), task.task_id),
                )
                conn.commit()
            task.status = TaskStatus.COMPLETED
            task.completed_at = now
            task.result = str(result)
            logger.info("[TaskQueue] Task completed task_id=%s", task.task_id)
            if task.callback_url:
                self._send_webhook(task)
        except Exception as exc:
            logger.warning(
                "[TaskQueue] Task failed task_id=%s error=%s", task.task_id, exc
            )
            task.error = str(exc)
            task.retry_count += 1
            self._update_retry_count(task)
            if task.retry_count <= task.max_retries:
                self._retry_with_backoff(task)
            else:
                now = datetime.datetime.utcnow().isoformat()
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        "UPDATE tasks SET status=?, completed_at=?, error=? WHERE task_id=?",
                        (TaskStatus.FAILED.value, now, task.error, task.task_id),
                    )
                    conn.commit()
                task.status = TaskStatus.FAILED
                task.completed_at = now
                logger.error(
                    "[TaskQueue] Task permanently failed task_id=%s retries=%d",
                    task.task_id, task.retry_count,
                )
                if task.callback_url:
                    self._send_webhook(task)

    def _send_webhook(self, task: QueuedTask):
        """非同步發送 Webhook 通知"""
        def _post():
            payload = {
                "task_id": task.task_id,
                "agent_name": task.agent_name,
                "status": task.status.value,
                "result": task.result,
                "error": task.error,
                "completed_at": task.completed_at,
            }
            try:
                body = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    task.callback_url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status >= 400:
                        logger.warning(
                            "[TaskQueue] Webhook returned %d for task_id=%s",
                            resp.status, task.task_id,
                        )
            except Exception as exc:
                logger.warning(
                    "[TaskQueue] Webhook failed task_id=%s error=%s",
                    task.task_id, exc,
                )

        t = threading.Thread(target=_post, daemon=True)
        t.start()

    def _retry_with_backoff(self, task: QueuedTask):
        """指數退避重試（1s, 2s, 4s, ...）"""
        delay = 2 ** (task.retry_count - 1)  # 1, 2, 4, ...
        logger.info(
            "[TaskQueue] Retrying task_id=%s in %ds (attempt %d/%d)",
            task.task_id, delay, task.retry_count, task.max_retries,
        )
        time.sleep(delay)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE tasks SET status=?, error=? WHERE task_id=?",
                (TaskStatus.PENDING.value, task.error, task.task_id),
            )
            conn.commit()

    def _update_retry_count(self, task: QueuedTask):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE tasks SET retry_count=? WHERE task_id=?",
                (task.retry_count, task.task_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _init_db(self):
        """建立 tasks 資料表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id      TEXT PRIMARY KEY,
                    agent_name   TEXT NOT NULL,
                    instruction  TEXT NOT NULL,
                    priority     INTEGER NOT NULL DEFAULT 2,
                    status       TEXT NOT NULL DEFAULT 'pending',
                    created_at   TEXT NOT NULL,
                    started_at   TEXT,
                    completed_at TEXT,
                    result       TEXT,
                    error        TEXT,
                    retry_count  INTEGER NOT NULL DEFAULT 0,
                    max_retries  INTEGER NOT NULL DEFAULT 3,
                    callback_url TEXT,
                    metadata     TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.commit()

    def _row_to_task(self, row) -> QueuedTask:
        return QueuedTask(
            task_id=row[0],
            agent_name=row[1],
            instruction=row[2],
            priority=TaskPriority(row[3]),
            status=TaskStatus(row[4]),
            created_at=row[5],
            started_at=row[6],
            completed_at=row[7],
            result=row[8],
            error=row[9],
            retry_count=row[10],
            max_retries=row[11],
            callback_url=row[12],
            metadata=json.loads(row[13]) if row[13] else {},
        )
