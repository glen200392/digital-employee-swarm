"""Process / Talent / Decision Agent 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.process_agent import ProcessAgent
from agents.talent_agent import TalentAgent
from agents.decision_agent import DecisionAgent
from agents.base_agent import BaseAgent
from harness.llm_provider import LLMProvider
from harness.skill_registry import SkillRegistry


def _init():
    BaseAgent.init_shared_resources(LLMProvider(), SkillRegistry())


class TestProcessAgent:
    def setup_method(self):
        _init()
        self.agent = ProcessAgent()

    def test_properties(self):
        assert self.agent.name == "PROCESS_AGENT"
        assert self.agent.role == "流程優化顧問"

    def test_matches_intent(self):
        assert self.agent.matches_intent("優化出貨流程")
        assert not self.agent.matches_intent("今天天氣如何")

    def test_run(self):
        result = self.agent.run("優化採購流程")
        assert "流程分析報告已建立" in result

    def test_status_after_run(self):
        self.agent.run("分析瓶頸")
        assert self.agent.status == "IDLE"
        assert self.agent._task_count == 1


class TestTalentAgent:
    def setup_method(self):
        _init()
        self.agent = TalentAgent()

    def test_properties(self):
        assert self.agent.name == "TALENT_AGENT"
        assert self.agent.role == "人才發展顧問"

    def test_matches_intent(self):
        assert self.agent.matches_intent("評估新人能力")
        assert not self.agent.matches_intent("今天天氣如何")

    def test_run(self):
        result = self.agent.run("評估業務團隊能力")
        assert "人才分析報告已建立" in result

    def test_status_after_run(self):
        self.agent.run("培訓規劃")
        assert self.agent.status == "IDLE"
        assert self.agent._task_count == 1


class TestDecisionAgent:
    def setup_method(self):
        _init()
        self.agent = DecisionAgent()

    def test_properties(self):
        assert self.agent.name == "DECISION_AGENT"
        assert self.agent.role == "決策支援分析師"

    def test_matches_intent(self):
        assert self.agent.matches_intent("分析投資風險")
        assert not self.agent.matches_intent("今天天氣如何")

    def test_run(self):
        result = self.agent.run("分析市場風險")
        assert "決策分析報告已建立" in result

    def test_status_after_run(self):
        self.agent.run("比較方案")
        assert self.agent.status == "IDLE"
        assert self.agent._task_count == 1
