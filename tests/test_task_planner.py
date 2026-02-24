"""TaskPlanner 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock
from orchestrator.task_planner import TaskPlanner, ExecutionPlan, SubTask
from orchestrator.result_aggregator import ResultAggregator
from orchestrator.router import MasterOrchestrator


class TestTaskPlanner:
    def test_single_task_detection(self):
        """簡單指令應識別為 single"""
        planner = TaskPlanner()
        plan = planner.plan("幫我萃取採購 SOP")
        assert plan.plan_type == "single"

    def test_multi_keyword_detection(self):
        """多個 Domain 關鍵字應識別為 multi-agent"""
        planner = TaskPlanner()
        plan = planner.plan("分析採購流程並評估相關人員的能力缺口")
        assert plan.plan_type in ("sequential", "parallel")
        assert len(plan.steps) >= 2

    def test_original_prompt_stored(self):
        """執行計畫應記錄原始 prompt"""
        planner = TaskPlanner()
        plan = planner.plan("幫我萃取採購 SOP")
        assert plan.original_prompt == "幫我萃取採購 SOP"

    def test_sequential_execution(self):
        """Sequential 模式：結果應包含多個 Agent 的輸出"""
        orch = MasterOrchestrator()
        result = orch.dispatch("分析採購流程並評估相關人員的能力缺口")
        # 應包含至少一個 agent 標頭或有輸出內容
        assert result is not None
        assert len(result) > 0

    def test_parallel_execution(self):
        """Parallel 模式：結果應包含合併後的報告"""
        orch = MasterOrchestrator()
        # 強制建立 parallel 計畫並執行
        plan = ExecutionPlan(
            plan_type="parallel",
            steps=[
                SubTask(agent_name="KM_AGENT", task="萃取採購SOP"),
                SubTask(agent_name="PROCESS_AGENT", task="優化採購流程"),
            ],
            merge_instruction="請整合以上兩個報告",
        )
        result = orch._dispatch_parallel(plan)
        assert result is not None
        assert len(result) > 0

    def test_fallback_without_llm(self):
        """無 LLM 時應 fallback 到關鍵字規劃模式"""
        planner = TaskPlanner(llm_provider=None)
        plan = planner.plan("分析採購流程並評估相關人員的能力缺口")
        assert plan.plan_type in ("sequential", "parallel")
        assert len(plan.steps) >= 2

    def test_unknown_prompt_returns_single(self):
        """完全不相關指令應返回 single 計畫"""
        planner = TaskPlanner(llm_provider=None)
        plan = planner.plan("今天天氣如何")
        # 無法匹配任何 agent，返回 single + UNKNOWN
        assert plan.plan_type == "single"

    def test_llm_plan_parsed_correctly(self):
        """LLM 回傳 JSON 應正確解析為 ExecutionPlan"""
        mock_llm = MagicMock()
        mock_llm.is_llm_available = True
        mock_llm.chat.return_value = (
            '{"type": "parallel", "steps": ['
            '{"agent": "KM_AGENT", "task": "萃取知識"}, '
            '{"agent": "PROCESS_AGENT", "task": "分析流程"}], '
            '"merge_instruction": "整合報告"}'
        )
        planner = TaskPlanner(llm_provider=mock_llm)
        plan = planner.plan("some complex prompt")
        assert plan.plan_type == "parallel"
        assert len(plan.steps) == 2
        assert plan.steps[0].agent_name == "KM_AGENT"
        assert plan.steps[1].agent_name == "PROCESS_AGENT"
        assert plan.merge_instruction == "整合報告"

    def test_llm_returns_invalid_json_falls_back(self):
        """LLM 回傳無效 JSON 應 fallback 到關鍵字模式"""
        mock_llm = MagicMock()
        mock_llm.is_llm_available = True
        mock_llm.chat.return_value = "not valid json"
        planner = TaskPlanner(llm_provider=mock_llm)
        plan = planner.plan("分析採購流程並評估相關人員的能力缺口")
        # fallback to keywords → still detects multi-agent
        assert plan.plan_type in ("sequential", "parallel")

    def test_dispatch_log_updated_for_sequential(self):
        """Sequential 執行後 dispatch_log 應記錄各步驟"""
        orch = MasterOrchestrator()
        initial_len = len(orch.dispatch_log)
        plan = ExecutionPlan(
            plan_type="sequential",
            steps=[
                SubTask(agent_name="KM_AGENT", task="萃取採購SOP"),
                SubTask(agent_name="PROCESS_AGENT", task="優化採購流程"),
            ],
        )
        orch._dispatch_sequential(plan)
        assert len(orch.dispatch_log) >= initial_len + 2


class TestResultAggregator:
    def test_simple_aggregate(self):
        """無 LLM 時應按順序拼接結果"""
        agg = ResultAggregator()
        results = [
            {"agent": "KM_AGENT", "result": "知識卡片"},
            {"agent": "PROCESS_AGENT", "result": "流程報告"},
        ]
        output = agg.aggregate(results)
        assert "KM_AGENT" in output
        assert "PROCESS_AGENT" in output
        assert "知識卡片" in output
        assert "流程報告" in output

    def test_empty_results(self):
        """空結果應回傳空字串"""
        agg = ResultAggregator()
        assert agg.aggregate([]) == ""

    def test_llm_aggregate(self):
        """有 LLM 且有 merge_instruction 時應使用 LLM 合併"""
        mock_llm = MagicMock()
        mock_llm.is_llm_available = True
        mock_llm.chat.return_value = "整合後的完整報告"
        agg = ResultAggregator()
        results = [
            {"agent": "KM_AGENT", "result": "知識卡片"},
            {"agent": "PROCESS_AGENT", "result": "流程報告"},
        ]
        output = agg.aggregate(results, "請整合", mock_llm)
        assert output == "整合後的完整報告"

    def test_llm_aggregate_fallback_on_failure(self):
        """LLM 合併失敗時應 fallback 到簡單拼接"""
        mock_llm = MagicMock()
        mock_llm.is_llm_available = True
        mock_llm.chat.side_effect = Exception("LLM error")
        agg = ResultAggregator()
        results = [
            {"agent": "KM_AGENT", "result": "知識卡片"},
        ]
        output = agg.aggregate(results, "整合", mock_llm)
        assert "KM_AGENT" in output
        assert "知識卡片" in output
