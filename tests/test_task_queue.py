"""Tests for the async priority task queue system"""

import os
import sys
import time
import threading
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from harness.task_queue import TaskQueue, TaskPriority, TaskStatus, QueuedTask


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_queue.db")


@pytest.fixture
def queue_no_worker(db_path):
    """Queue without started workers – for unit tests that inspect DB directly."""
    q = TaskQueue(db_path=db_path, num_workers=2, agent_executor=None)
    yield q


@pytest.fixture
def simple_executor():
    """A fast executor that just returns a success string."""
    def _exec(agent_name, instruction):
        return f"OK:{agent_name}:{instruction}"
    return _exec


@pytest.fixture
def queue_with_worker(db_path, simple_executor):
    q = TaskQueue(db_path=db_path, num_workers=2, agent_executor=simple_executor)
    q.start()
    yield q
    q.stop(graceful=True)


# ─────────────────────────────────────────────────────────────
# Basic enqueue / status
# ─────────────────────────────────────────────────────────────

class TestEnqueueAndGetStatus:
    def test_enqueue_returns_task_id(self, queue_no_worker):
        task_id = queue_no_worker.enqueue("KM_AGENT", "test instruction")
        assert task_id is not None
        assert len(task_id) == 36  # UUID4 format

    def test_get_status_returns_task(self, queue_no_worker):
        task_id = queue_no_worker.enqueue("KM_AGENT", "instruction")
        task = queue_no_worker.get_status(task_id)
        assert task is not None
        assert task.task_id == task_id
        assert task.agent_name == "KM_AGENT"
        assert task.instruction == "instruction"
        assert task.status == TaskStatus.PENDING

    def test_get_status_nonexistent(self, queue_no_worker):
        assert queue_no_worker.get_status("nonexistent-id") is None

    def test_default_priority_is_normal(self, queue_no_worker):
        task_id = queue_no_worker.enqueue("KM_AGENT", "instruction")
        task = queue_no_worker.get_status(task_id)
        assert task.priority == TaskPriority.NORMAL

    def test_custom_priority_stored(self, queue_no_worker):
        task_id = queue_no_worker.enqueue(
            "KM_AGENT", "instruction", priority=TaskPriority.HIGH
        )
        task = queue_no_worker.get_status(task_id)
        assert task.priority == TaskPriority.HIGH

    def test_callback_url_stored(self, queue_no_worker):
        task_id = queue_no_worker.enqueue(
            "KM_AGENT", "instruction", callback_url="http://example.com/cb"
        )
        task = queue_no_worker.get_status(task_id)
        assert task.callback_url == "http://example.com/cb"

    def test_metadata_stored(self, queue_no_worker):
        task_id = queue_no_worker.enqueue(
            "KM_AGENT", "instruction", metadata={"key": "value"}
        )
        task = queue_no_worker.get_status(task_id)
        assert task.metadata == {"key": "value"}


# ─────────────────────────────────────────────────────────────
# Priority ordering
# ─────────────────────────────────────────────────────────────

class TestPriorityOrdering:
    def test_priority_ordering(self, db_path):
        """高優先級任務應先被執行"""
        execution_order = []

        def tracking_executor(agent_name, instruction):
            execution_order.append(instruction)
            return "done"

        q = TaskQueue(db_path=db_path, num_workers=1, agent_executor=tracking_executor)

        # Enqueue without starting workers
        q.enqueue("A", "low-task", priority=TaskPriority.LOW)
        q.enqueue("A", "normal-task", priority=TaskPriority.NORMAL)
        q.enqueue("A", "critical-task", priority=TaskPriority.CRITICAL)
        q.enqueue("A", "high-task", priority=TaskPriority.HIGH)

        q.start()
        # Give workers time to process all 4 tasks
        deadline = time.time() + 5
        while len(execution_order) < 4 and time.time() < deadline:
            time.sleep(0.1)
        q.stop(graceful=False)

        assert len(execution_order) == 4
        assert execution_order[0] == "critical-task"
        assert execution_order[1] == "high-task"
        assert execution_order[2] == "normal-task"
        assert execution_order[3] == "low-task"


# ─────────────────────────────────────────────────────────────
# FIFO within same priority
# ─────────────────────────────────────────────────────────────

class TestFifoSamePriority:
    def test_fifo_same_priority(self, db_path):
        execution_order = []

        def tracking_executor(agent_name, instruction):
            execution_order.append(instruction)
            time.sleep(0.01)  # slight pause so ordering is deterministic
            return "done"

        q = TaskQueue(db_path=db_path, num_workers=1, agent_executor=tracking_executor)
        # Enqueue all tasks before starting to guarantee FIFO ordering
        q.enqueue("A", "first", priority=TaskPriority.NORMAL)
        q.enqueue("A", "second", priority=TaskPriority.NORMAL)
        q.enqueue("A", "third", priority=TaskPriority.NORMAL)

        q.start()
        deadline = time.time() + 5
        while len(execution_order) < 3 and time.time() < deadline:
            time.sleep(0.1)
        q.stop(graceful=False)

        assert execution_order == ["first", "second", "third"]


# ─────────────────────────────────────────────────────────────
# Cancel
# ─────────────────────────────────────────────────────────────

class TestCancel:
    def test_cancel_pending_task(self, queue_no_worker):
        task_id = queue_no_worker.enqueue("KM_AGENT", "to cancel")
        result = queue_no_worker.cancel(task_id)
        assert result is True
        task = queue_no_worker.get_status(task_id)
        assert task.status == TaskStatus.CANCELLED

    def test_cannot_cancel_nonexistent_task(self, queue_no_worker):
        result = queue_no_worker.cancel("nonexistent-id")
        assert result is False

    def test_cannot_cancel_running_task(self, db_path):
        """取消執行中任務應失敗（返回 False）"""
        started = threading.Event()
        stay = threading.Event()

        def blocking_executor(agent_name, instruction):
            started.set()
            stay.wait(timeout=5)
            return "done"

        q = TaskQueue(db_path=db_path, num_workers=1, agent_executor=blocking_executor)
        task_id = q.enqueue("A", "blocking task")
        q.start()

        started.wait(timeout=3)
        # Task is now RUNNING
        result = q.cancel(task_id)
        assert result is False
        stay.set()
        q.stop(graceful=True)


# ─────────────────────────────────────────────────────────────
# Retry on failure
# ─────────────────────────────────────────────────────────────

class TestRetryOnFailure:
    def test_retry_on_failure(self, db_path):
        """失敗任務應自動重試，最多 max_retries 次"""
        call_count = [0]

        def failing_executor(agent_name, instruction):
            call_count[0] += 1
            raise RuntimeError("simulated failure")

        q = TaskQueue(db_path=db_path, num_workers=1, agent_executor=failing_executor)
        task_id = q.enqueue("A", "failing task")

        # Patch max_retries = 2 in DB directly
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE tasks SET max_retries=2 WHERE task_id=?", (task_id,))
            conn.commit()

        q.start()
        # Wait for task to be permanently failed (3 attempts: 1 initial + 2 retries)
        deadline = time.time() + 15
        while time.time() < deadline:
            t = q.get_status(task_id)
            if t and t.status == TaskStatus.FAILED:
                break
            time.sleep(0.2)
        q.stop(graceful=False)

        assert call_count[0] == 3  # 1 initial + 2 retries
        final = q.get_status(task_id)
        assert final.status == TaskStatus.FAILED
        assert final.retry_count == 3

    def test_task_completes_after_transient_failure(self, db_path):
        """任務在第一次失敗後第二次成功"""
        call_count = [0]

        def flaky_executor(agent_name, instruction):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("transient failure")
            return "success"

        q = TaskQueue(db_path=db_path, num_workers=1, agent_executor=flaky_executor)
        task_id = q.enqueue("A", "flaky task")
        q.start()

        deadline = time.time() + 10
        while time.time() < deadline:
            t = q.get_status(task_id)
            if t and t.status == TaskStatus.COMPLETED:
                break
            time.sleep(0.2)
        q.stop(graceful=False)

        assert q.get_status(task_id).status == TaskStatus.COMPLETED


# ─────────────────────────────────────────────────────────────
# Exponential backoff
# ─────────────────────────────────────────────────────────────

class TestExponentialBackoff:
    def test_exponential_backoff(self, db_path, monkeypatch):
        """重試延遲應為指數退避"""
        delays = []
        original_sleep = time.sleep

        def mock_sleep(seconds):
            delays.append(seconds)
            # Use a tiny real sleep so the loop can proceed quickly
            original_sleep(0.01)

        monkeypatch.setattr(time, "sleep", mock_sleep)

        call_count = [0]

        def failing_executor(agent_name, instruction):
            call_count[0] += 1
            raise RuntimeError("fail")

        q = TaskQueue(db_path=db_path, num_workers=1, agent_executor=failing_executor)
        task_id = q.enqueue("A", "backoff task")

        import sqlite3
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE tasks SET max_retries=2 WHERE task_id=?", (task_id,))
            conn.commit()

        q.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            t = q.get_status(task_id)
            if t and t.status == TaskStatus.FAILED:
                break
            original_sleep(0.05)
        q.stop(graceful=False)

        # Filter out the 0.5s idle sleeps – look only for backoff sleeps (≥1)
        backoff_delays = [d for d in delays if d >= 1]
        assert len(backoff_delays) >= 2
        assert backoff_delays[0] == 1  # 2^(1-1) = 1
        assert backoff_delays[1] == 2  # 2^(2-1) = 2


# ─────────────────────────────────────────────────────────────
# Queue stats
# ─────────────────────────────────────────────────────────────

class TestQueueStats:
    def test_queue_stats(self, queue_no_worker):
        queue_no_worker.enqueue("KM_AGENT", "task1")
        queue_no_worker.enqueue("KM_AGENT", "task2")
        stats = queue_no_worker.get_queue_stats()
        assert stats["pending"] == 2
        assert stats["running"] == 0
        assert stats["worker_count"] == 2
        assert "completed_today" in stats
        assert "failed_today" in stats
        assert "avg_wait_time_sec" in stats

    def test_stats_after_cancel(self, queue_no_worker):
        task_id = queue_no_worker.enqueue("KM_AGENT", "task")
        queue_no_worker.cancel(task_id)
        stats = queue_no_worker.get_queue_stats()
        assert stats["pending"] == 0


# ─────────────────────────────────────────────────────────────
# Graceful stop
# ─────────────────────────────────────────────────────────────

class TestGracefulStop:
    def test_graceful_stop(self, db_path):
        """stop(graceful=True) 應等待當前任務完成"""
        finished = threading.Event()

        def slow_executor(agent_name, instruction):
            time.sleep(0.3)
            finished.set()
            return "done"

        q = TaskQueue(db_path=db_path, num_workers=1, agent_executor=slow_executor)
        task_id = q.enqueue("A", "slow task")
        q.start()
        time.sleep(0.05)  # Let task start
        q.stop(graceful=True)

        task = q.get_status(task_id)
        assert task.status == TaskStatus.COMPLETED
        assert finished.is_set()


# ─────────────────────────────────────────────────────────────
# Persistence across restart
# ─────────────────────────────────────────────────────────────

class TestPersistenceAcrossRestart:
    def test_persistence_across_restart(self, db_path):
        """重啟後 PENDING 任務應仍在佇列中"""
        q1 = TaskQueue(db_path=db_path, num_workers=0, agent_executor=None)
        task_id = q1.enqueue("KM_AGENT", "persistent task")

        # Create a new queue instance pointing to the same DB
        q2 = TaskQueue(db_path=db_path, num_workers=0, agent_executor=None)
        task = q2.get_status(task_id)
        assert task is not None
        assert task.status == TaskStatus.PENDING
        assert task.instruction == "persistent task"


# ─────────────────────────────────────────────────────────────
# Pending tasks list
# ─────────────────────────────────────────────────────────────

class TestGetPendingTasks:
    def test_get_all_pending(self, queue_no_worker):
        queue_no_worker.enqueue("A", "task1")
        queue_no_worker.enqueue("B", "task2")
        tasks = queue_no_worker.get_pending_tasks()
        assert len(tasks) == 2

    def test_filter_by_agent(self, queue_no_worker):
        queue_no_worker.enqueue("A", "task1")
        queue_no_worker.enqueue("B", "task2")
        tasks = queue_no_worker.get_pending_tasks(agent_name="A")
        assert len(tasks) == 1
        assert tasks[0].agent_name == "A"

    def test_cancelled_not_in_pending(self, queue_no_worker):
        task_id = queue_no_worker.enqueue("A", "task")
        queue_no_worker.cancel(task_id)
        assert queue_no_worker.get_pending_tasks() == []


# ─────────────────────────────────────────────────────────────
# Web API integration
# ─────────────────────────────────────────────────────────────

try:
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi/httpx not installed")
class TestQueueWebAPI:
    def setup_method(self):
        from web.app import app, auth
        self.client = TestClient(app)
        self._admin_token = auth.authenticate("admin", "admin123")
        self._viewer_token = auth.authenticate("viewer", "viewer123")

    def test_submit_task(self):
        res = self.client.post(
            "/api/queue/submit",
            json={
                "agent_name": "KM_AGENT",
                "instruction": "test instruction",
                "priority": "NORMAL",
                "token": self._admin_token,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_submit_invalid_priority(self):
        res = self.client.post(
            "/api/queue/submit",
            json={
                "agent_name": "KM_AGENT",
                "instruction": "test",
                "priority": "INVALID",
                "token": self._admin_token,
            },
        )
        assert res.status_code == 400

    def test_submit_no_auth(self):
        res = self.client.post(
            "/api/queue/submit",
            json={
                "agent_name": "KM_AGENT",
                "instruction": "test",
                "token": "bad-token",
            },
        )
        assert res.status_code == 401

    def test_get_task_status(self):
        # Submit first
        res = self.client.post(
            "/api/queue/submit",
            json={
                "agent_name": "KM_AGENT",
                "instruction": "status test",
                "token": self._admin_token,
            },
        )
        task_id = res.json()["task_id"]
        res2 = self.client.get(f"/api/queue/tasks/{task_id}?token={self._admin_token}")
        assert res2.status_code == 200
        assert res2.json()["task_id"] == task_id

    def test_get_task_not_found(self):
        res = self.client.get(f"/api/queue/tasks/nonexistent?token={self._admin_token}")
        assert res.status_code == 404

    def test_cancel_task(self):
        res = self.client.post(
            "/api/queue/submit",
            json={
                "agent_name": "KM_AGENT",
                "instruction": "cancel me",
                "token": self._admin_token,
            },
        )
        task_id = res.json()["task_id"]
        res2 = self.client.post(
            f"/api/queue/tasks/{task_id}/cancel?token={self._admin_token}"
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "cancelled"

    def test_cancel_nonexistent_returns_400(self):
        res = self.client.post(
            f"/api/queue/tasks/nonexistent/cancel?token={self._admin_token}"
        )
        assert res.status_code == 400

    def test_get_queue_stats(self):
        res = self.client.get(f"/api/queue/stats?token={self._admin_token}")
        assert res.status_code == 200
        data = res.json()
        assert "pending" in data
        assert "running" in data
        assert "worker_count" in data

    def test_get_pending_tasks(self):
        res = self.client.get(f"/api/queue/pending?token={self._admin_token}")
        assert res.status_code == 200
        assert "tasks" in res.json()

    def test_viewer_can_get_stats(self):
        res = self.client.get(f"/api/queue/stats?token={self._viewer_token}")
        # viewer has "status" permission
        assert res.status_code == 200

    def test_viewer_cannot_submit(self):
        res = self.client.post(
            "/api/queue/submit",
            json={
                "agent_name": "KM_AGENT",
                "instruction": "test",
                "token": self._viewer_token,
            },
        )
        assert res.status_code == 403
