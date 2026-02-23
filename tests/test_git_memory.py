"""Tests for GitMemory"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.git_memory import GitMemory


class TestGitMemory:
    def setup_method(self):
        self.test_dir = tempfile.mkdtemp()
        self.memory = GitMemory(repo_path=self.test_dir)

    def teardown_method(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_creates_dirs(self):
        """GitMemory 應自動建立 docs/ 目錄"""
        assert os.path.exists(os.path.join(self.test_dir, "docs"))
        assert os.path.exists(os.path.join(self.test_dir, "docs", "sops"))

    def test_commit_progress_writes_log(self):
        """commit_progress 應寫入 progress.log"""
        self.memory.commit_progress("TEST_AGENT", "TASK-001", "測試訊息")
        assert os.path.exists(self.memory.log_file)
        with open(self.memory.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[TEST_AGENT]" in content
        assert "TASK-001" in content
        assert "測試訊息" in content

    def test_commit_progress_updates_progress_md(self):
        """commit_progress 應更新 PROGRESS.md"""
        self.memory.commit_progress("TEST_AGENT", "TASK-002", "進度更新")
        assert os.path.exists(self.memory.progress_md)
        with open(self.memory.progress_md, "r", encoding="utf-8") as f:
            content = f.read()
        assert "TEST_AGENT" in content
        assert "TASK-002" in content

    def test_get_last_context_empty(self):
        """無記錄時應回傳空列表"""
        result = self.memory.get_last_context("NONEXISTENT")
        assert result == []

    def test_get_last_context_filters_by_agent(self):
        """get_last_context 應只回傳指定 Agent 的記錄"""
        self.memory.commit_progress("AGENT_A", "T1", "A 的第一筆")
        self.memory.commit_progress("AGENT_B", "T2", "B 的第一筆")
        self.memory.commit_progress("AGENT_A", "T3", "A 的第二筆")

        context_a = self.memory.get_last_context("AGENT_A")
        assert len(context_a) == 2
        assert all("[AGENT_A]" in c for c in context_a)

        context_b = self.memory.get_last_context("AGENT_B")
        assert len(context_b) == 1

    def test_get_last_context_max_entries(self):
        """get_last_context 應限制回傳數量"""
        for i in range(10):
            self.memory.commit_progress("AGENT_X", f"T-{i}", f"記錄 {i}")

        context = self.memory.get_last_context("AGENT_X", max_entries=3)
        assert len(context) == 3

    def test_get_all_progress(self):
        """get_all_progress 應回傳所有記錄"""
        self.memory.commit_progress("A", "T1", "m1")
        self.memory.commit_progress("B", "T2", "m2")
        all_progress = self.memory.get_all_progress()
        assert len(all_progress) == 2
