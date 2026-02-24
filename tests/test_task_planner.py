"""tests/test_task_planner.py — TaskPlanner 單元測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.task_planner import (
    TaskPlanner,
    ExecutionMode,
    SubTask,
    PlanResult,
)


# ──────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────

def make_executors(result_template="[{agent}] 完成: {task}"):
    """建立模擬 agent_executors，回傳固定字串。"""
    agents = ["KM_AGENT", "PROCESS_AGENT", "TALENT_AGENT", "DECISION_AGENT"]

    def _make_fn(agent_name):
        def _fn(task_input: str) -> str:
            return result_template.format(agent=agent_name, task=task_input[:30])
        return _fn

    return {name: _make_fn(name) for name in agents}


# ──────────────────────────────────────────────
# 1. 簡單任務不被拆解
# ──────────────────────────────────────────────

class TestSimpleTask:
    def setup_method(self):
        self.planner = TaskPlanner()

    def test_simple_task_no_split(self):
        """簡單任務應只產生 1 個子任務，不被拆解。"""
        plan = self.planner.plan("萃取採購SOP")
        assert len(plan.sub_tasks) == 1
        assert plan.sub_tasks[0].task == "萃取採購SOP"

    def test_simple_task_agent_assignment(self):
        """簡單任務的 Agent 應正確指派。"""
        plan = self.planner.plan("優化出貨流程")
        assert plan.sub_tasks[0].agent_name == "PROCESS_AGENT"

    def test_simple_task_km_assignment(self):
        plan = self.planner.plan("萃取文件知識")
        assert plan.sub_tasks[0].agent_name == "KM_AGENT"

    def test_simple_task_talent_assignment(self):
        plan = self.planner.plan("評估員工能力")
        assert plan.sub_tasks[0].agent_name == "TALENT_AGENT"

    def test_simple_task_decision_assignment(self):
        plan = self.planner.plan("分析市場風險")
        assert plan.sub_tasks[0].agent_name == "DECISION_AGENT"


# ──────────────────────────────────────────────
# 2. 複合任務被正確拆解
# ──────────────────────────────────────────────

class TestComplexTask:
    def setup_method(self):
        self.planner = TaskPlanner()

    def test_complex_task_splits(self):
        """含「並且」的任務應被拆解為多個子任務。"""
        plan = self.planner.plan("分析業績並且優化流程並且培訓相關人員")
        assert len(plan.sub_tasks) > 1

    def test_complex_task_subtask_ids_unique(self):
        """子任務 ID 應唯一。"""
        plan = self.planner.plan("萃取SOP並且分析風險")
        ids = [st.sub_task_id for st in plan.sub_tasks]
        assert len(ids) == len(set(ids))

    def test_complex_task_parent_id_consistent(self):
        """所有子任務的 parent_task_id 應與 plan_id 一致。"""
        plan = self.planner.plan("優化流程並且培訓人才")
        for st in plan.sub_tasks:
            assert st.parent_task_id == plan.plan_id

    def test_complex_task_max_five_subtasks(self):
        """拆解子任務數不超過 5 個。"""
        # 連接多個任務
        long_task = "萃取文件，分析風險，優化流程，培訓員工，並且整理知識"
        plan = self.planner.plan(long_task)
        assert len(plan.sub_tasks) <= 5

    def test_compound_keywords_trigger_split(self):
        """各種複合關鍵詞都能觸發拆解。"""
        for task in [
            "萃取SOP，優化流程",
            "分析業績同時培訓員工",
            "先萃取知識然後分析風險",
        ]:
            plan = self.planner.plan(task)
            assert len(plan.sub_tasks) > 1, f"任務應被拆解: {task}"


# ──────────────────────────────────────────────
# 3. SEQUENTIAL 模式：依序執行 + 依賴鏈
# ──────────────────────────────────────────────

class TestSequentialExecution:
    def setup_method(self):
        self.planner = TaskPlanner()
        self.executors = make_executors()

    def test_sequential_dependency(self):
        """SEQUENTIAL 模式下，子任務應有依賴鏈（ST-002 depends_on ST-001 等）。"""
        plan = self.planner.plan("先萃取SOP然後優化流程")
        assert plan.execution_mode == ExecutionMode.SEQUENTIAL
        # ST-002 應依賴 ST-001
        if len(plan.sub_tasks) >= 2:
            assert plan.sub_tasks[1].depends_on == ["ST-001"]

    def test_sequential_execution_order(self):
        """SEQUENTIAL 模式下子任務按順序完成。"""
        order = []
        agents = ["KM_AGENT", "PROCESS_AGENT", "TALENT_AGENT", "DECISION_AGENT"]

        def _make_fn(name):
            def _fn(task_input):
                order.append(name)
                return f"{name} done"
            return _fn

        executors = {n: _make_fn(n) for n in agents}

        plan = self.planner.plan("先萃取知識然後分析風險")
        plan = self.planner.execute(plan, executors)

        # 執行順序應與子任務順序一致
        expected_agents = [st.agent_name for st in plan.sub_tasks]
        assert order == expected_agents

    def test_sequential_prev_result_passed(self):
        """SEQUENTIAL 模式下後續子任務應收到前一個結果的參考。"""
        received_inputs = []

        def km_executor(task_input):
            received_inputs.append(("KM_AGENT", task_input))
            return "知識卡片已建立"

        def process_executor(task_input):
            received_inputs.append(("PROCESS_AGENT", task_input))
            return "流程分析完成"

        executors = make_executors()
        executors["KM_AGENT"] = km_executor
        executors["PROCESS_AGENT"] = process_executor

        plan = self.planner.plan("先萃取知識然後優化流程")
        self.planner.execute(plan, executors)

        # 第二個子任務應在 task_input 中包含前置結果
        if len(received_inputs) >= 2:
            _, second_input = received_inputs[1]
            assert "知識卡片已建立" in second_input or "前置結果參考" in second_input


# ──────────────────────────────────────────────
# 4. PARALLEL 模式：並行執行
# ──────────────────────────────────────────────

class TestParallelExecution:
    def setup_method(self):
        self.planner = TaskPlanner()
        self.executors = make_executors()

    def test_parallel_execution(self):
        """PARALLEL 模式下多個子任務都被執行且狀態為 COMPLETED。"""
        plan = self.planner.plan("分析業績並且優化流程")
        assert plan.execution_mode == ExecutionMode.PARALLEL

        plan = self.planner.execute(plan, self.executors)
        for st in plan.sub_tasks:
            assert st.status == "COMPLETED", f"{st.sub_task_id} 應為 COMPLETED，實際: {st.status}"

    def test_parallel_no_dependency(self):
        """PARALLEL 模式下子任務不應有依賴鏈。"""
        plan = self.planner.plan("萃取SOP並且培訓員工")
        assert plan.execution_mode == ExecutionMode.PARALLEL
        for st in plan.sub_tasks:
            assert st.depends_on == []

    def test_parallel_all_results_populated(self):
        """PARALLEL 執行後每個子任務都應有 result。"""
        plan = self.planner.plan("分析風險並且優化流程")
        plan = self.planner.execute(plan, self.executors)
        for st in plan.sub_tasks:
            assert st.result is not None and len(st.result) > 0

    def test_parallel_plan_success(self):
        """所有子任務成功後 plan.success 應為 True。"""
        plan = self.planner.plan("萃取知識並且分析業績")
        plan = self.planner.execute(plan, self.executors)
        assert plan.success is True


# ──────────────────────────────────────────────
# 5. 聚合輸出
# ──────────────────────────────────────────────

class TestAggregateOutput:
    def setup_method(self):
        self.planner = TaskPlanner()
        self.executors = make_executors()

    def test_aggregate_output(self):
        """聚合結果應包含所有子任務的輸出。"""
        plan = self.planner.plan("分析業績並且優化流程並且培訓員工")
        plan = self.planner.execute(plan, self.executors)
        output = self.planner.aggregate(plan)

        # 應包含每個子任務的 ID
        for st in plan.sub_tasks:
            assert st.sub_task_id in output

    def test_aggregate_contains_original_task(self):
        """聚合報告應包含原始任務描述。"""
        task = "萃取SOP並且分析風險"
        plan = self.planner.plan(task)
        plan = self.planner.execute(plan, self.executors)
        output = self.planner.aggregate(plan)
        assert task in output

    def test_aggregate_sets_plan_aggregated_output(self):
        """aggregate() 應設定 plan.aggregated_output。"""
        plan = self.planner.plan("優化流程並且培訓員工")
        plan = self.planner.execute(plan, self.executors)
        output = self.planner.aggregate(plan)
        assert plan.aggregated_output == output
        assert len(plan.aggregated_output) > 0

    def test_aggregate_status_label(self):
        """聚合報告應顯示整體成功/失敗狀態。"""
        plan = self.planner.plan("分析風險並且萃取文件")
        plan = self.planner.execute(plan, self.executors)
        output = self.planner.aggregate(plan)
        assert "成功" in output or "失敗" in output


# ──────────────────────────────────────────────
# 6. PlanResult / SubTask 資料結構
# ──────────────────────────────────────────────

class TestDataStructures:
    def setup_method(self):
        self.planner = TaskPlanner()

    def test_plan_result_has_plan_id(self):
        plan = self.planner.plan("萃取SOP")
        assert plan.plan_id.startswith("PLAN-")

    def test_subtask_status_default_pending(self):
        plan = self.planner.plan("萃取知識並且分析風險")
        for st in plan.sub_tasks:
            assert st.status == "PENDING"

    def test_plan_result_has_execution_mode(self):
        plan = self.planner.plan("萃取SOP")
        assert isinstance(plan.execution_mode, ExecutionMode)

    def test_execution_mode_values(self):
        assert ExecutionMode.SEQUENTIAL.value == "sequential"
        assert ExecutionMode.PARALLEL.value == "parallel"
