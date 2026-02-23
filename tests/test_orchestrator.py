"""Tests for Orchestrator"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.router import MasterOrchestrator
from orchestrator.intent_classifier import IntentClassifier


class TestIntentClassifier:
    def setup_method(self):
        self.classifier = IntentClassifier()

    def test_km_agent_intent(self):
        """知識相關指令應分類到 KM_AGENT"""
        agent, _ = self.classifier.classify("請幫我萃取SOP")
        assert agent == "KM_AGENT"

    def test_process_agent_intent(self):
        """流程相關指令應分類到 PROCESS_AGENT"""
        agent, _ = self.classifier.classify("優化出貨流程")
        assert agent == "PROCESS_AGENT"

    def test_talent_agent_intent(self):
        """人才相關指令應分類到 TALENT_AGENT"""
        agent, _ = self.classifier.classify("評估新人能力")
        assert agent == "TALENT_AGENT"

    def test_decision_agent_intent(self):
        """決策相關指令應分類到 DECISION_AGENT"""
        agent, _ = self.classifier.classify("分析風險")
        assert agent == "DECISION_AGENT"

    def test_unknown_intent(self):
        """無法識別的指令應回傳 UNKNOWN"""
        agent, confidence = self.classifier.classify("今天天氣如何")
        assert agent == "UNKNOWN"
        assert confidence == 0.0

    def test_confidence_score(self):
        """分類結果應包含信心度分數"""
        _, confidence = self.classifier.classify("萃取知識文件整理")
        assert 0.0 < confidence <= 1.0


class TestMasterOrchestrator:
    def setup_method(self):
        self.orchestrator = MasterOrchestrator()

    def test_has_all_agents(self):
        """Orchestrator 應載入 4 個 Domain Agent"""
        assert len(self.orchestrator.agents) == 4
        assert "KM_AGENT" in self.orchestrator.agents
        assert "PROCESS_AGENT" in self.orchestrator.agents
        assert "TALENT_AGENT" in self.orchestrator.agents
        assert "DECISION_AGENT" in self.orchestrator.agents

    def test_dispatch_km(self):
        """知識任務應分派給 KM_AGENT"""
        result = self.orchestrator.dispatch("萃取採購SOP")
        assert result is not None
        assert len(result) > 0

    def test_dispatch_process(self):
        """流程任務應分派給 PROCESS_AGENT"""
        result = self.orchestrator.dispatch("優化出貨流程")
        assert "流程分析" in result or "報告" in result

    def test_dispatch_talent(self):
        """人才任務應分派給 TALENT_AGENT"""
        result = self.orchestrator.dispatch("評估新人能力")
        assert "人才分析" in result or "報告" in result

    def test_dispatch_decision(self):
        """決策任務應分派給 DECISION_AGENT"""
        result = self.orchestrator.dispatch("分析風險")
        assert "決策分析" in result or "報告" in result

    def test_dispatch_unknown(self):
        """無法識別的任務應回傳提示"""
        result = self.orchestrator.dispatch("今天天氣如何")
        assert "抱歉" in result or "關鍵字" in result

    def test_get_status(self):
        """get_status 應回傳所有 Agent 狀態"""
        status = self.orchestrator.get_status()
        assert "KM_AGENT" in status
        assert "PROCESS_AGENT" in status

    def test_dispatch_log(self):
        """dispatch 應記錄分派歷史"""
        self.orchestrator.dispatch("萃取知識")
        assert len(self.orchestrator.dispatch_log) == 1
