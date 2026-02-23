"""Orchestrator 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.intent_classifier import IntentClassifier
from orchestrator.router import MasterOrchestrator


class TestIntentClassifier:
    def setup_method(self):
        self.classifier = IntentClassifier()

    def test_km_agent_intent(self):
        agent, _ = self.classifier.classify("請幫我萃取採購SOP")
        assert agent == "KM_AGENT"

    def test_process_agent_intent(self):
        agent, _ = self.classifier.classify("優化出貨流程")
        assert agent == "PROCESS_AGENT"

    def test_talent_agent_intent(self):
        agent, _ = self.classifier.classify("評估新人能力")
        assert agent == "TALENT_AGENT"

    def test_decision_agent_intent(self):
        agent, _ = self.classifier.classify("分析投資風險")
        assert agent == "DECISION_AGENT"

    def test_unknown_intent(self):
        agent, _ = self.classifier.classify("今天天氣如何")
        assert agent == "UNKNOWN"

    def test_confidence_score(self):
        _, confidence = self.classifier.classify("萃取知識文件整理SOP")
        assert confidence > 0.5


class TestMasterOrchestrator:
    def setup_method(self):
        self.orch = MasterOrchestrator()

    def test_has_all_agents(self):
        assert len(self.orch.agents) == 4
        assert "KM_AGENT" in self.orch.agents
        assert "PROCESS_AGENT" in self.orch.agents
        assert "TALENT_AGENT" in self.orch.agents
        assert "DECISION_AGENT" in self.orch.agents

    def test_has_a2a(self):
        """A2A 應自動註冊所有 Agent"""
        assert len(self.orch.a2a.registry) == 4

    def test_a2a_agents_have_executors(self):
        """A2A Agent 應綁定真實的 run()"""
        for card in self.orch.a2a.registry.values():
            assert card.executor is not None

    def test_has_mcp(self):
        health = self.orch.mcp.health_check()
        assert "知識庫" in health

    def test_has_llm(self):
        assert self.orch.llm is not None
        assert self.orch.llm.provider_name == "offline"

    def test_has_skills(self):
        skills = self.orch.skill_registry.list_all()
        assert len(skills) >= 5

    def test_dispatch_km(self):
        result = self.orch.dispatch("萃取採購SOP")
        assert "知識卡片已建立" in result

    def test_dispatch_process(self):
        result = self.orch.dispatch("優化出貨流程")
        assert "流程分析報告已建立" in result

    def test_dispatch_talent(self):
        result = self.orch.dispatch("評估新人能力")
        assert "人才分析報告已建立" in result

    def test_dispatch_decision(self):
        result = self.orch.dispatch("分析市場風險")
        assert "決策分析報告已建立" in result

    def test_dispatch_unknown(self):
        result = self.orch.dispatch("今天天氣如何")
        assert "不確定" in result or "關鍵字" in result

    def test_get_status(self):
        status = self.orch.get_status()
        assert "Agent Fleet" in status
        assert "LLM Provider" in status

    def test_dispatch_log(self):
        self.orch.dispatch("萃取SOP")
        assert len(self.orch.dispatch_log) >= 1
        assert self.orch.dispatch_log[-1]["agent"] == "KM_AGENT"
