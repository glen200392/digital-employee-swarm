"""Tests for EvalEngine"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.eval_engine import EvalEngine, LLMJudgeEvalEngine


class TestEvalEngine:
    def setup_method(self):
        self.engine = EvalEngine(pass_score=0.7)

    def test_evaluate_returns_score(self):
        """evaluate 應回傳 0-1 之間的分數"""
        score = self.engine.evaluate("TEST", "task", "output")
        assert 0.0 <= score <= 1.0

    def test_rich_content_scores_higher(self):
        """內容較豐富的輸出應獲得更高分"""
        short = self.engine.evaluate("A", "萃取知識", "OK")
        long_content = "# 知識卡片\n- 項目1\n- 項目2: 詳細說明\n" * 20
        rich = self.engine.evaluate("A", "萃取知識", long_content)
        assert rich > short

    def test_relevance_scoring(self):
        """包含任務關鍵字的輸出應獲得相關性分數"""
        task = "採購流程"
        relevant = "這是關於採購流程的分析，包含完整的流程圖"
        irrelevant = "今天天氣很好"
        score_r = self.engine.evaluate("A", task, relevant)
        score_i = self.engine.evaluate("A", task, irrelevant)
        assert score_r > score_i

    def test_is_passing(self):
        """is_passing 應正確判斷通過門檻"""
        assert self.engine.is_passing(0.8) is True
        assert self.engine.is_passing(0.5) is False

    def test_history_tracked(self):
        """評估歷史應被記錄"""
        self.engine.evaluate("AGENT_A", "task1", "output1")
        self.engine.evaluate("AGENT_A", "task2", "output2")
        assert len(self.engine.history) == 2

    def test_agent_stats(self):
        """get_agent_stats 應回傳正確統計"""
        self.engine.evaluate("AGENT_A", "t1", "short")
        self.engine.evaluate("AGENT_A", "t2", "# Long\n- item\n" * 30)
        stats = self.engine.get_agent_stats("AGENT_A")
        assert stats["count"] == 2
        assert 0.0 <= stats["avg_score"] <= 1.0

    def test_empty_agent_stats(self):
        """無記錄的 Agent 應回傳預設統計"""
        stats = self.engine.get_agent_stats("NONEXISTENT")
        assert stats["count"] == 0

    def test_get_report(self):
        """get_report 應回傳非空報告"""
        self.engine.evaluate("A", "t", "o")
        report = self.engine.get_report()
        assert "Eval Engine Report" in report


class TestLLMJudgeEvalEngine:
    def setup_method(self):
        self.engine = LLMJudgeEvalEngine(pass_score=0.7, llm_provider=None)

    def test_fallback_mode(self):
        """無 LLM 時應 fallback 到關鍵字模式"""
        score = self.engine.evaluate("TEST", "task", "output")
        assert 0.0 <= score <= 1.0
        assert self.engine.history[-1].judge_mode == "keyword"

    def test_score_range(self):
        """分數必須在 0.0~1.0 之間"""
        for output in ["", "x", "# Title\n- item\n" * 10]:
            score = self.engine.evaluate("TEST", "task", output)
            assert 0.0 <= score <= 1.0

    def test_dimensions_present(self):
        """有 LLM 時，EvalRecord 應包含四個維度分數"""
        import json

        class MockLLMProvider:
            is_llm_available = True

            def chat(self, prompt, max_tokens=512):
                return json.dumps({
                    "overall_score": 0.85,
                    "dimensions": {
                        "task_completion": 0.9,
                        "accuracy": 0.8,
                        "clarity": 0.85,
                        "actionability": 0.85,
                    },
                    "feedback": "良好輸出",
                    "pass": True,
                })

        engine = LLMJudgeEvalEngine(pass_score=0.7, llm_provider=MockLLMProvider())
        score = engine.evaluate("A", "task", "some output")
        assert score == 0.85
        record = engine.history[-1]
        assert record.judge_mode == "llm"
        assert set(record.dimensions.keys()) == {
            "task_completion", "accuracy", "clarity", "actionability"
        }

    def test_json_parse_failure_fallback(self):
        """JSON 解析失敗時應正常 fallback，不拋出例外"""
        class BadLLMProvider:
            is_llm_available = True

            def chat(self, prompt, max_tokens=512):
                return "not valid json {{{"

        engine = LLMJudgeEvalEngine(pass_score=0.7, llm_provider=BadLLMProvider())
        score = engine.evaluate("A", "task", "output")
        assert 0.0 <= score <= 1.0
        assert engine.history[-1].judge_mode == "keyword"

    def test_high_quality_output_scores_higher(self):
        """結構完整、內容豐富的輸出應獲得比空輸出更高的分數"""
        empty_score = self.engine.evaluate("A", "萃取知識", "")
        rich_output = "# 知識卡片\n- 項目1\n- 項目2: 詳細說明\n萃取知識相關內容\n" * 20
        rich_score = self.engine.evaluate("A", "萃取知識", rich_output)
        assert rich_score > empty_score
