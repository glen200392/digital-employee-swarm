"""WorkflowEngine 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock
from harness.workflow_engine import (
    WorkflowEngine,
    WorkflowDefinition,
    WorkflowStep,
    StepType,
    StepResult,
    WorkflowResult,
)


def _make_agent(name: str, output: str):
    """建立一個回傳固定輸出的 mock agent"""
    agent = MagicMock()
    agent.run.return_value = output
    return agent


def _make_orchestrator(*agent_pairs):
    """建立一個帶有指定 agents 的 mock orchestrator"""
    orch = MagicMock()
    orch.agents = {name: _make_agent(name, output) for name, output in agent_pairs}
    return orch


class TestSequentialWorkflow:
    def test_sequential_workflow(self):
        orch = _make_orchestrator(
            ("KM_AGENT", "# 知識卡片\n- 重點一\n- 重點二"),
            ("PROCESS_AGENT", "# 流程優化\n- 改進步驟一"),
        )
        engine = WorkflowEngine(orchestrator=orch)
        wf = WorkflowDefinition(
            workflow_id="test_seq",
            name="測試循序",
            description="",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    step_type=StepType.AGENT,
                    agent_name="KM_AGENT",
                    task_template="萃取：{topic}",
                ),
                WorkflowStep(
                    step_id="s2",
                    step_type=StepType.AGENT,
                    agent_name="PROCESS_AGENT",
                    task_template="優化：{s1}",
                ),
            ],
        )
        engine.register(wf)
        result = engine.execute("test_seq", {"topic": "採購SOP"})

        assert result.success is True
        assert result.workflow_id == "test_seq"
        assert len(result.steps) == 2
        assert result.steps[0].agent_name == "KM_AGENT"
        assert result.steps[1].agent_name == "PROCESS_AGENT"
        # step2 template should have used step1 output
        call_args = orch.agents["PROCESS_AGENT"].run.call_args[0][0]
        assert "知識卡片" in call_args

    def test_workflow_result_contains_all_steps(self):
        orch = _make_orchestrator(("KM_AGENT", "output_km"))
        engine = WorkflowEngine(orchestrator=orch)
        wf = WorkflowDefinition(
            workflow_id="test_steps",
            name="步驟測試",
            description="",
            steps=[
                WorkflowStep(
                    step_id="step_a",
                    step_type=StepType.AGENT,
                    agent_name="KM_AGENT",
                    task_template="任務",
                ),
            ],
        )
        engine.register(wf)
        result = engine.execute("test_steps", {})
        assert result.get_step_result("step_a") is not None
        assert result.get_step_result("nonexistent") is None


class TestParallelWorkflow:
    def test_parallel_workflow(self):
        orch = _make_orchestrator(
            ("PROCESS_AGENT", "# 流程面分析\n- 重點"),
            ("TALENT_AGENT", "# 人員面分析\n- 能力"),
            ("DECISION_AGENT", "# 決策建議\n- 建議"),
        )
        engine = WorkflowEngine(orchestrator=orch)
        wf = WorkflowDefinition(
            workflow_id="test_parallel",
            name="平行測試",
            description="",
            steps=[
                WorkflowStep(
                    step_id="parallel_step",
                    step_type=StepType.PARALLEL,
                    parallel_steps=[
                        WorkflowStep(
                            step_id="sub_a",
                            step_type=StepType.AGENT,
                            agent_name="PROCESS_AGENT",
                            task_template="流程分析：{topic}",
                        ),
                        WorkflowStep(
                            step_id="sub_b",
                            step_type=StepType.AGENT,
                            agent_name="TALENT_AGENT",
                            task_template="人才分析：{topic}",
                        ),
                    ],
                ),
            ],
        )
        engine.register(wf)
        result = engine.execute("test_parallel", {"topic": "組織效能"})

        assert result.success is True
        assert len(result.steps) == 1
        parallel_result = result.steps[0]
        assert parallel_result.agent_name == "PARALLEL"
        assert "PROCESS_AGENT" in parallel_result.output or "TALENT_AGENT" in parallel_result.output


class TestLoopWorkflow:
    def test_loop_workflow_success(self):
        """第一次就通過品質門檻"""
        long_output = "# 高品質報告\n" + "- 詳細說明\n" * 20
        orch = _make_orchestrator(("KM_AGENT", long_output))
        engine = WorkflowEngine(orchestrator=orch)
        wf = WorkflowDefinition(
            workflow_id="test_loop_ok",
            name="Loop 成功",
            description="",
            steps=[
                WorkflowStep(
                    step_id="loop_step",
                    step_type=StepType.LOOP,
                    agent_name="KM_AGENT",
                    task_template="任務：{topic}",
                    condition="eval_score >= 0.75",
                    max_iterations=3,
                ),
            ],
        )
        engine.register(wf)
        result = engine.execute("test_loop_ok", {"topic": "測試主題"})
        assert result.success is True
        assert result.steps[0].success is True

    def test_loop_workflow_max_iterations(self):
        """品質始終不達標，達到 max_iterations"""
        orch = _make_orchestrator(("KM_AGENT", "短"))
        engine = WorkflowEngine(orchestrator=orch)
        wf = WorkflowDefinition(
            workflow_id="test_loop_fail",
            name="Loop 失敗",
            description="",
            steps=[
                WorkflowStep(
                    step_id="loop_fail",
                    step_type=StepType.LOOP,
                    agent_name="KM_AGENT",
                    task_template="任務",
                    condition="eval_score >= 0.75",
                    max_iterations=3,
                ),
            ],
        )
        engine.register(wf)
        result = engine.execute("test_loop_fail", {})
        assert result.steps[0].success is False
        # Should have called agent up to max_iterations times
        assert orch.agents["KM_AGENT"].run.call_count == 3


class TestConditionalBranching:
    def test_conditional_branching(self):
        """測試 CONDITION 步驟"""
        engine = WorkflowEngine(orchestrator=None)
        wf = WorkflowDefinition(
            workflow_id="test_cond",
            name="條件測試",
            description="",
            steps=[
                WorkflowStep(
                    step_id="cond_true",
                    step_type=StepType.CONDITION,
                    condition="x > 5",
                ),
                WorkflowStep(
                    step_id="cond_false",
                    step_type=StepType.CONDITION,
                    condition="x > 100",
                ),
            ],
        )
        engine.register(wf)
        result = engine.execute("test_cond", {"x": 10})
        assert result.steps[0].success is True   # 10 > 5
        assert result.steps[1].success is False  # 10 > 100


class TestVariableSubstitution:
    def test_variable_substitution_in_task_template(self):
        """測試 task_template 中的 {variable} 替換"""
        orch = _make_orchestrator(("KM_AGENT", "output"))
        engine = WorkflowEngine(orchestrator=orch)
        wf = WorkflowDefinition(
            workflow_id="test_var",
            name="變數替換",
            description="",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    step_type=StepType.AGENT,
                    agent_name="KM_AGENT",
                    task_template="主題是 {topic}，部門是 {dept}",
                ),
            ],
        )
        engine.register(wf)
        engine.execute("test_var", {"topic": "採購", "dept": "資訊部"})
        call_arg = orch.agents["KM_AGENT"].run.call_args[0][0]
        assert "採購" in call_arg
        assert "資訊部" in call_arg


class TestBuiltinWorkflows:
    def test_builtin_workflows_registered(self):
        """3 個預設工作流應已被註冊"""
        engine = WorkflowEngine(orchestrator=None)
        assert "knowledge_immortalization" in engine.workflow_registry
        assert "decision_support" in engine.workflow_registry
        assert "quality_retry" in engine.workflow_registry

    def test_builtin_workflow_knowledge_immortalization(self):
        """知識永生化工作流有 3 個步驟"""
        engine = WorkflowEngine(orchestrator=None)
        wf = engine.workflow_registry["knowledge_immortalization"]
        assert len(wf.steps) == 3
        assert wf.steps[0].agent_name == "KM_AGENT"
        assert wf.steps[1].agent_name == "PROCESS_AGENT"
        assert wf.steps[2].agent_name == "TALENT_AGENT"

    def test_builtin_workflow_decision_support(self):
        """決策支援工作流有 Parallel + Merge + Agent"""
        engine = WorkflowEngine(orchestrator=None)
        wf = engine.workflow_registry["decision_support"]
        assert len(wf.steps) == 3
        assert wf.steps[0].step_type == StepType.PARALLEL
        assert wf.steps[1].step_type == StepType.MERGE
        assert wf.steps[2].step_type == StepType.AGENT

    def test_builtin_workflow_quality_retry(self):
        """品質重試工作流使用 Loop 類型"""
        engine = WorkflowEngine(orchestrator=None)
        wf = engine.workflow_registry["quality_retry"]
        assert len(wf.steps) == 1
        assert wf.steps[0].step_type == StepType.LOOP
        assert wf.steps[0].max_iterations == 3


class TestExecutionHistory:
    def test_execution_history(self):
        """執行後應記錄到 execution_history"""
        engine = WorkflowEngine(orchestrator=None)
        assert len(engine.execution_history) == 0

        wf = WorkflowDefinition(
            workflow_id="hist_test",
            name="歷史測試",
            description="",
            steps=[
                WorkflowStep(
                    step_id="cond",
                    step_type=StepType.CONDITION,
                    condition="True",
                ),
            ],
        )
        engine.register(wf)
        engine.execute("hist_test", {})
        assert len(engine.execution_history) == 1
        assert engine.execution_history[0].workflow_id == "hist_test"

    def test_nonexistent_workflow(self):
        """執行不存在的工作流應回傳失敗結果"""
        engine = WorkflowEngine(orchestrator=None)
        result = engine.execute("nonexistent_id", {})
        assert result.success is False
        assert "不存在" in result.final_output


class TestWorkflowSerialization:
    def test_workflow_definition_to_dict_and_from_dict(self):
        """WorkflowDefinition 序列化與反序列化"""
        engine = WorkflowEngine(orchestrator=None)
        original = engine.workflow_registry["knowledge_immortalization"]
        data = original.to_dict()
        restored = WorkflowDefinition.from_dict(data)
        assert restored.workflow_id == original.workflow_id
        assert restored.name == original.name
        assert len(restored.steps) == len(original.steps)
        assert restored.steps[0].agent_name == original.steps[0].agent_name


class TestWebWorkflowAPI:
    """Web API workflow 端點測試"""

    def setup_method(self):
        try:
            from fastapi.testclient import TestClient
            from web.app import app
            self.client = TestClient(app)
            self.available = True
        except ImportError:
            self.available = False

    def _login(self):
        if not self.available:
            pytest.skip("fastapi/httpx not installed")
        res = self.client.post("/api/login",
                               json={"username": "admin", "password": "admin123"})
        return res.json().get("token")

    def test_list_workflows(self):
        if not self.available:
            pytest.skip("fastapi/httpx not installed")
        token = self._login()
        res = self.client.get(f"/api/workflows?token={token}")
        assert res.status_code == 200
        data = res.json()
        assert "workflows" in data
        wf_ids = [w["workflow_id"] for w in data["workflows"]]
        assert "knowledge_immortalization" in wf_ids
        assert "decision_support" in wf_ids
        assert "quality_retry" in wf_ids

    def test_execute_workflow_endpoint(self):
        if not self.available:
            pytest.skip("fastapi/httpx not installed")
        token = self._login()
        res = self.client.post(
            "/api/workflows/quality_retry/execute",
            json={"token": token, "context": {"topic": "採購流程", "feedback": ""}},
        )
        assert res.status_code == 200
        data = res.json()
        assert "workflow_id" in data
        assert "success" in data
        assert "steps" in data

    def test_execute_nonexistent_workflow(self):
        if not self.available:
            pytest.skip("fastapi/httpx not installed")
        token = self._login()
        res = self.client.post(
            "/api/workflows/nonexistent/execute",
            json={"token": token, "context": {}},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False

    def test_list_workflows_no_auth(self):
        if not self.available:
            pytest.skip("fastapi/httpx not installed")
        res = self.client.get("/api/workflows?token=invalid")
        assert res.status_code == 401
