"""
冪等性測試
確認連續呼叫 commit_session() 兩次後，PROGRESS.md 仍只有一行相同的記錄。
"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.git_memory import GitMemory
from harness.session_store import SessionStore
from harness.core import EnterpriseHarness, SessionResult
from harness.risk_assessor import RiskLevel


class TestGitMemoryIdempotency:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory = GitMemory(repo_path=self.test_dir)

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _count_task_lines(self, task_id: str) -> int:
        """回傳 PROGRESS.md 中包含指定 task_id 的行數"""
        if not os.path.exists(self.memory.progress_md):
            return 0
        with open(self.memory.progress_md, "r", encoding="utf-8") as f:
            return sum(1 for line in f if task_id in line)

    def test_duplicate_commit_progress_is_skipped(self):
        """連續兩次 commit_progress 使用相同 task_id，PROGRESS.md 應只有一行"""
        self.memory.commit_progress("KM_AGENT", "TASK-9999", "第一次寫入")
        self.memory.commit_progress("KM_AGENT", "TASK-9999", "第二次（應被跳過）")
        assert self._count_task_lines("TASK-9999") == 1

    def test_different_task_ids_both_written(self):
        """不同 task_id 應分別寫入"""
        self.memory.commit_progress("KM_AGENT", "TASK-0001", "任務 A")
        self.memory.commit_progress("KM_AGENT", "TASK-0002", "任務 B")
        assert self._count_task_lines("TASK-0001") == 1
        assert self._count_task_lines("TASK-0002") == 1

    def test_different_agents_same_task_id_both_written(self):
        """不同 Agent 使用相同 task_id，應各自寫入一行"""
        self.memory.commit_progress("KM_AGENT", "TASK-SHARED", "KM 的記錄")
        self.memory.commit_progress("PROCESS_AGENT", "TASK-SHARED", "Process 的記錄")
        assert self._count_task_lines("TASK-SHARED") == 2

    def test_is_duplicate_returns_false_when_file_missing(self):
        """PROGRESS.md 不存在時 _is_duplicate 應回傳 False"""
        assert self.memory._is_duplicate("KM_AGENT", "TASK-X") is False

    def test_is_duplicate_returns_true_after_first_write(self):
        """第一次寫入後 _is_duplicate 應回傳 True"""
        self.memory.commit_progress("KM_AGENT", "TASK-DUP", "初次記錄")
        assert self.memory._is_duplicate("KM_AGENT", "TASK-DUP") is True

    def test_is_duplicate_returns_false_for_new_task(self):
        """不同 task_id 的 _is_duplicate 應回傳 False"""
        self.memory.commit_progress("KM_AGENT", "TASK-A", "記錄 A")
        assert self.memory._is_duplicate("KM_AGENT", "TASK-B") is False


class TestSessionStoreIdempotency:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        db_path = os.path.join(self.test_dir, "sessions.db")
        self.store = SessionStore(db_path=db_path)

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _count_rows(self, agent_name: str, task_id: str) -> int:
        import sqlite3
        with sqlite3.connect(self.store.db_path) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM sessions "
                "WHERE agent_name = ? AND task_id = ?",
                (agent_name, task_id),
            )
            return cur.fetchone()[0]

    def test_save_session_twice_produces_one_row(self):
        """連續呼叫 save_session() 兩次，資料庫應只有一筆記錄"""
        self.store.save_session("KM_AGENT", "TASK-1", "COMPLETED", 0.8, "LOW", "ok")
        self.store.save_session("KM_AGENT", "TASK-1", "COMPLETED", 0.9, "LOW", "retry")
        assert self._count_rows("KM_AGENT", "TASK-1") == 1

    def test_save_session_updates_latest_values(self):
        """第二次 save_session() 應以最新值覆蓋"""
        self.store.save_session("KM_AGENT", "TASK-2", "RUNNING", 0.0, "LOW", "start")
        self.store.save_session("KM_AGENT", "TASK-2", "COMPLETED", 1.0, "LOW", "done")
        row = self.store.get_session("KM_AGENT", "TASK-2")
        assert row is not None
        assert row["status"] == "COMPLETED"
        assert row["eval_score"] == 1.0
        assert row["output"] == "done"

    def test_different_task_ids_are_independent(self):
        """不同 task_id 應各自獨立存在"""
        self.store.save_session("KM_AGENT", "TASK-A", "COMPLETED", 0.5, "LOW", "a")
        self.store.save_session("KM_AGENT", "TASK-B", "COMPLETED", 0.7, "LOW", "b")
        assert self._count_rows("KM_AGENT", "TASK-A") == 1
        assert self._count_rows("KM_AGENT", "TASK-B") == 1

    def test_unique_constraint_on_agent_and_task_id(self):
        """(agent_name, task_id) 組合在資料庫中應具備 UNIQUE 約束"""
        import sqlite3
        with sqlite3.connect(self.store.db_path) as conn:
            cur = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name='sessions'"
            )
            ddl = cur.fetchone()[0]
        assert "UNIQUE" in ddl.upper()


class TestHarnessCommitSessionIdempotency:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        # Patch harness to use temp dir
        self.harness = EnterpriseHarness(repo_path=self.test_dir)

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _count_task_lines(self, task_id: str) -> int:
        md = self.harness.memory.progress_md
        if not os.path.exists(md):
            return 0
        with open(md, "r", encoding="utf-8") as f:
            return sum(1 for line in f if task_id in line)

    def test_commit_session_twice_single_entry(self):
        """EnterpriseHarness.commit_session() 呼叫兩次後 PROGRESS.md 應只有一行"""
        result = SessionResult(
            agent_name="KM_AGENT",
            task_id="TASK-IDEM",
            success=True,
            output="知識卡片已建立",
            risk_level=RiskLevel.LOW,
            eval_score=0.8,
        )
        self.harness.commit_session(result)
        self.harness.commit_session(result)
        assert self._count_task_lines("TASK-IDEM") == 1
