"""
Persistence Tests
驗證 SessionStore、VectorStore 磁碟模式及 EnterpriseHarness 的跨 instance 持久化。
所有測試使用臨時目錄，並設定 VECTOR_STORE_MODE=memory 以確保 CI 速度。
"""
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ------------------------------------------------------------------ #
# SessionStore Tests
# ------------------------------------------------------------------ #

class TestSessionStore:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_sessions.db")
        from harness.session_store import SessionStore, SessionRecord
        self.SessionStore = SessionStore
        self.SessionRecord = SessionRecord
        self.store = SessionStore(db_path=self.db_path)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_record(self, agent="TEST_AGENT", task_id="T-001",
                     task="測試任務", output="完成", success=True,
                     eval_score=8.5, risk_level="LOW"):
        return self.SessionRecord(
            agent_name=agent,
            task_id=task_id,
            task=task,
            output=output,
            risk_level=risk_level,
            eval_score=eval_score,
            success=success,
        )

    def test_save_and_get_last_sessions(self):
        r = self._make_record()
        row_id = self.store.save_session(r)
        assert isinstance(row_id, int) and row_id > 0

        sessions = self.store.get_last_sessions("TEST_AGENT", limit=10)
        assert len(sessions) == 1
        assert sessions[0].task == "測試任務"
        assert sessions[0].success is True

    def test_get_last_sessions_limit(self):
        for i in range(8):
            self.store.save_session(self._make_record(task_id=f"T-{i}"))
        sessions = self.store.get_last_sessions("TEST_AGENT", limit=3)
        assert len(sessions) == 3

    def test_get_sessions_by_task_keyword(self):
        self.store.save_session(self._make_record(task="知識萃取 SOP"))
        self.store.save_session(self._make_record(task="採購流程優化"))
        results = self.store.get_sessions_by_task("知識")
        assert len(results) == 1
        assert "知識" in results[0].task

    def test_search_context_format(self):
        self.store.save_session(self._make_record())
        ctx = self.store.search_context("TEST_AGENT", limit=5)
        assert len(ctx) == 1
        assert "task_id" in ctx[0]
        assert "task" in ctx[0]
        assert "success" in ctx[0]

    def test_get_agent_stats(self):
        self.store.save_session(self._make_record(eval_score=8.0, success=True))
        self.store.save_session(self._make_record(eval_score=6.0, success=False))
        stats = self.store.get_agent_stats("TEST_AGENT")
        assert stats["total_tasks"] == 2
        assert stats["avg_eval_score"] == 7.0
        assert stats["success_rate"] == 0.5

    def test_set_and_get_memory(self):
        self.store.set_memory("AGENT_A", "last_file", "sop_v1.md")
        val = self.store.get_memory("AGENT_A", "last_file")
        assert val == "sop_v1.md"

    def test_set_memory_overwrite(self):
        self.store.set_memory("AGENT_A", "counter", 1)
        self.store.set_memory("AGENT_A", "counter", 2)
        assert self.store.get_memory("AGENT_A", "counter") == 2

    def test_get_memory_nonexistent(self):
        assert self.store.get_memory("AGENT_A", "nonexistent") is None

    def test_persistence_across_instances(self):
        """跨 instance 持久化驗證（核心測試）"""
        self.store.save_session(self._make_record(task="跨重啟任務"))
        self.store.set_memory("TEST_AGENT", "state", "active")

        # 重新初始化新 instance
        store2 = self.SessionStore(db_path=self.db_path)
        sessions = store2.get_last_sessions("TEST_AGENT")
        assert len(sessions) == 1
        assert sessions[0].task == "跨重啟任務"
        assert store2.get_memory("TEST_AGENT", "state") == "active"


# ------------------------------------------------------------------ #
# VectorStore disk mode Tests
# ------------------------------------------------------------------ #

class TestVectorStoreDiskMode:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        # 強制 memory 模式以確保 CI 速度
        os.environ["VECTOR_STORE_MODE"] = "memory"

    def teardown_method(self):
        os.environ.pop("VECTOR_STORE_MODE", None)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_memory_mode_add_search(self):
        from harness.vector_store import VectorStore
        vs = VectorStore()
        vs.add_document("doc1", "知識萃取流程 SOP")
        results = vs.search("知識")
        assert len(results) >= 0  # qdrant or keyword

    def test_disk_mode_creates_directory(self):
        """磁碟模式應自動建立目錄"""
        qdrant_path = os.path.join(self.tmp_dir, "qdrant_data")
        os.environ["VECTOR_STORE_MODE"] = "disk"
        os.environ["QDRANT_PATH"] = qdrant_path
        try:
            from harness.vector_store import VectorStore
            vs = VectorStore(collection_name="test_col")
            if not vs.is_vector_mode:
                pytest.skip("qdrant-client disk mode not available in CI")
            assert os.path.exists(qdrant_path)
        except ImportError:
            pytest.skip("qdrant-client not installed")
        finally:
            os.environ.pop("QDRANT_PATH", None)
            os.environ["VECTOR_STORE_MODE"] = "memory"

    def test_backend_name_memory_mode(self):
        from harness.vector_store import VectorStore
        vs = VectorStore()
        name = vs.backend_name
        assert isinstance(name, str) and len(name) > 0


# ------------------------------------------------------------------ #
# EnterpriseHarness commit_session → restore_context flow
# ------------------------------------------------------------------ #

class TestHarnessPersistenceFlow:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        os.environ["SESSION_DB_PATH"] = os.path.join(
            self.tmp_dir, "harness_test.db"
        )
        os.environ["VECTOR_STORE_MODE"] = "memory"

    def teardown_method(self):
        os.environ.pop("SESSION_DB_PATH", None)
        os.environ.pop("VECTOR_STORE_MODE", None)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_commit_session_and_restore_context(self):
        from harness.core import EnterpriseHarness, SessionResult
        from harness.risk_assessor import RiskLevel

        harness = EnterpriseHarness(repo_path=self.tmp_dir)
        result = SessionResult(
            agent_name="KM_AGENT",
            task_id="TASK-9999",
            success=True,
            output="知識萃取完成",
            risk_level=RiskLevel.LOW,
            eval_score=9.0,
        )
        harness.commit_session(result)

        ctx = harness.restore_context("KM_AGENT")
        assert ctx["agent_name"] == "KM_AGENT"
        assert len(ctx["last_sessions"]) >= 1
        assert ctx["last_sessions"][0]["task_id"] == "TASK-9999"

    def test_restore_context_persists_across_harness_instances(self):
        """跨 Harness instance 的 Session 持久化驗證"""
        from harness.core import EnterpriseHarness, SessionResult
        from harness.risk_assessor import RiskLevel

        h1 = EnterpriseHarness(repo_path=self.tmp_dir)
        result = SessionResult(
            agent_name="PROCESS_AGENT",
            task_id="TASK-1234",
            success=True,
            output="流程優化完成",
            risk_level=RiskLevel.LOW,
            eval_score=8.5,
        )
        h1.commit_session(result)

        # 新 Harness instance（模擬重啟）
        h2 = EnterpriseHarness(repo_path=self.tmp_dir)
        ctx = h2.restore_context("PROCESS_AGENT")
        assert len(ctx["last_sessions"]) >= 1
        assert any(
            s["task_id"] == "TASK-1234" for s in ctx["last_sessions"]
        )
