"""Tests for KM Agent"""

import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.km_agent import KMAgent


class TestKMAgent:
    def setup_method(self):
        self.agent = KMAgent()

    def test_agent_properties(self):
        """KMAgent 應有正確的名稱與角色"""
        assert self.agent.name == "KM_AGENT"
        assert "知識" in self.agent.role
        assert self.agent.status == "IDLE"

    def test_matches_intent(self):
        """KMAgent 應匹配知識萃取相關關鍵字"""
        assert self.agent.matches_intent("請幫我萃取SOP") is True
        assert self.agent.matches_intent("整理這份文件") is True
        assert self.agent.matches_intent("extract knowledge") is True
        assert self.agent.matches_intent("優化流程") is False

    def test_run_produces_output(self):
        """run 應產出非空結果"""
        result = self.agent.run("萃取採購SOP知識")
        assert result is not None
        assert len(result) > 0
        assert "知識卡片" in result

    def test_run_creates_file(self):
        """run 應建立知識卡片文件"""
        result = self.agent.run("萃取測試文件")
        assert "docs/sops/" in result

    def test_get_status(self):
        """get_status 應回傳正確狀態"""
        status = self.agent.get_status()
        assert status["name"] == "KM_AGENT"
        assert status["status"] == "IDLE"

    def test_status_resets_after_run(self):
        """run 完成後 status 應回到 IDLE"""
        self.agent.run("test")
        assert self.agent.status == "IDLE"

    def test_task_count_increments(self):
        """每次 run 後 task_count 應遞增"""
        self.agent.run("task 1")
        self.agent.run("task 2")
        assert self.agent.get_status()["tasks_completed"] == 2

    def test_extract_topic(self):
        """_extract_topic 應去除指令性前綴"""
        assert self.agent._extract_topic("請幫我萃取採購流程") == "採購流程"
        assert self.agent._extract_topic("整理SOP文件") == "SOP文件"
