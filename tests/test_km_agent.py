"""KM Agent 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from agents.km_agent import KMAgent
from agents.base_agent import BaseAgent
from harness.llm_provider import LLMProvider
from harness.skill_registry import SkillRegistry


class TestKMAgent:
    def setup_method(self):
        BaseAgent.init_shared_resources(LLMProvider(), SkillRegistry())
        self.agent = KMAgent()
        # 用 temp 目錄避免污染 docs/
        self.tmpdir = tempfile.mkdtemp()
        self._orig_file = os.path.abspath(__file__)

    def test_agent_properties(self):
        assert self.agent.name == "KM_AGENT"
        assert self.agent.role == "知識萃取專家"

    def test_matches_intent(self):
        assert self.agent.matches_intent("請幫我萃取SOP")
        assert self.agent.matches_intent("整理知識文件")
        assert not self.agent.matches_intent("今天天氣如何")

    def test_run_produces_output(self):
        result = self.agent.run("萃取採購SOP")
        assert "知識卡片已建立" in result

    def test_run_creates_file(self):
        self.agent.run("萃取測試文件")
        sops_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "sops"
        )
        files = [f for f in os.listdir(sops_dir) if f.startswith("knowledge_KM-")]
        assert len(files) >= 1

    def test_get_status(self):
        status = self.agent.get_status()
        assert status["name"] == "KM_AGENT"
        assert status["llm_provider"] == "offline"

    def test_status_resets_after_run(self):
        self.agent.run("萃取SOP")
        assert self.agent.status == "IDLE"

    def test_task_count_increments(self):
        self.agent.run("萃取A")
        self.agent.run("萃取B")
        assert self.agent._task_count == 2

    def test_extract_topic(self):
        assert self.agent._extract_topic("請幫我萃取採購SOP") == "採購SOP"
        assert self.agent._extract_topic("分析市場") == "分析市場"
