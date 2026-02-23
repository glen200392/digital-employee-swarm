"""Tests for all Domain Agents (Process, Talent, Decision)"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.process_agent import ProcessAgent
from agents.talent_agent import TalentAgent
from agents.decision_agent import DecisionAgent


class TestProcessAgent:
    def setup_method(self):
        self.agent = ProcessAgent()

    def test_properties(self):
        assert self.agent.name == "PROCESS_AGENT"
        assert "流程" in self.agent.role

    def test_matches_intent(self):
        assert self.agent.matches_intent("優化出貨流程") is True
        assert self.agent.matches_intent("萃取知識") is False

    def test_run(self):
        result = self.agent.run("優化採購流程")
        assert "流程分析" in result or "報告" in result

    def test_status_after_run(self):
        self.agent.run("test")
        assert self.agent.status == "IDLE"
        assert self.agent.get_status()["tasks_completed"] == 1


class TestTalentAgent:
    def setup_method(self):
        self.agent = TalentAgent()

    def test_properties(self):
        assert self.agent.name == "TALENT_AGENT"
        assert "人才" in self.agent.role

    def test_matches_intent(self):
        assert self.agent.matches_intent("評估新人能力") is True
        assert self.agent.matches_intent("優化流程") is False

    def test_run(self):
        result = self.agent.run("評估團隊能力")
        assert "人才分析" in result or "報告" in result

    def test_status_after_run(self):
        self.agent.run("test")
        assert self.agent.status == "IDLE"
        assert self.agent.get_status()["tasks_completed"] == 1


class TestDecisionAgent:
    def setup_method(self):
        self.agent = DecisionAgent()

    def test_properties(self):
        assert self.agent.name == "DECISION_AGENT"
        assert "決策" in self.agent.role

    def test_matches_intent(self):
        assert self.agent.matches_intent("分析風險") is True
        assert self.agent.matches_intent("萃取知識") is False

    def test_run(self):
        result = self.agent.run("分析投資風險")
        assert "決策分析" in result or "報告" in result

    def test_status_after_run(self):
        self.agent.run("test")
        assert self.agent.status == "IDLE"
        assert self.agent.get_status()["tasks_completed"] == 1
