"""
Workflow Engine — 多 Agent 協作工作流引擎
支援 Sequential / Parallel / Conditional / Loop 四種模式。
每個工作流可以被定義、保存、重複執行。
"""

import ast
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class StepType(Enum):
    AGENT = "agent"           # 呼叫一個 Agent
    CONDITION = "condition"   # 條件判斷
    LOOP = "loop"             # 重複執行直到條件滿足
    PARALLEL = "parallel"     # 平行執行多個步驟
    MERGE = "merge"           # 合併前一個 parallel 的結果


@dataclass
class WorkflowStep:
    step_id: str
    step_type: StepType
    agent_name: Optional[str] = None       # AGENT 類型使用
    task_template: str = ""                # 支援 {variable} 變數替換
    condition: Optional[str] = None        # CONDITION 類型：Python 表達式字串
    max_iterations: int = 3                # LOOP 類型：最多重試次數
    parallel_steps: List["WorkflowStep"] = field(default_factory=list)  # PARALLEL 類型
    on_success: Optional[str] = None       # 成功後執行的 step_id
    on_failure: Optional[str] = None       # 失敗後執行的 step_id

    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "agent_name": self.agent_name,
            "task_template": self.task_template,
            "condition": self.condition,
            "max_iterations": self.max_iterations,
            "parallel_steps": [s.to_dict() for s in self.parallel_steps],
            "on_success": self.on_success,
            "on_failure": self.on_failure,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkflowStep":
        parallel_steps = [
            cls.from_dict(s) for s in data.get("parallel_steps", [])
        ]
        return cls(
            step_id=data["step_id"],
            step_type=StepType(data["step_type"]),
            agent_name=data.get("agent_name"),
            task_template=data.get("task_template", ""),
            condition=data.get("condition"),
            max_iterations=data.get("max_iterations", 3),
            parallel_steps=parallel_steps,
            on_success=data.get("on_success"),
            on_failure=data.get("on_failure"),
        )


@dataclass
class WorkflowDefinition:
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "WorkflowDefinition":
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            workflow_id=data["workflow_id"],
            name=data["name"],
            description=data["description"],
            steps=steps,
            created_at=data.get("created_at", ""),
        )


@dataclass
class StepResult:
    step_id: str
    agent_name: str
    success: bool
    output: str
    score: float = 0.0
    duration_sec: float = 0.0
    error: str = ""


@dataclass
class WorkflowResult:
    workflow_id: str
    success: bool
    steps: List[StepResult]
    final_output: str
    total_duration_sec: float

    def get_step_result(self, step_id: str) -> Optional[StepResult]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None


# Allowlist of safe AST node types for condition expressions
_SAFE_AST_NODES = (
    ast.Expression, ast.BoolOp, ast.UnaryOp, ast.Compare,
    ast.And, ast.Or, ast.Not,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Is, ast.IsNot,
    ast.In, ast.NotIn,
    ast.Constant,  # numbers, strings, booleans
    ast.Name,      # variable references from context
    ast.Load,
)


def _safe_eval_condition(condition: str, context: Dict) -> bool:
    """
    安全地評估條件表達式。
    只允許比較運算、布林運算和變數引用，防止代碼注入。
    """
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError:
        return False

    # Verify every node is in the allowlist
    for node in ast.walk(tree):
        if not isinstance(node, _SAFE_AST_NODES):
            raise ValueError(f"不允許的表達式節點: {type(node).__name__}")

    # Evaluate with only context variables (no builtins)
    return bool(eval(compile(tree, "<condition>", "eval"), {"__builtins__": {}}, context))  # noqa: S307


class WorkflowEngine:
    """
    工作流執行引擎。
    執行 WorkflowDefinition，返回 WorkflowResult。
    """

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator  # MasterOrchestrator 的引用
        self.workflow_registry: Dict[str, WorkflowDefinition] = {}
        self.execution_history: List[WorkflowResult] = []
        self._register_builtin_workflows()

    def register(self, workflow: WorkflowDefinition):
        """註冊一個工作流定義"""
        self.workflow_registry[workflow.workflow_id] = workflow

    def execute(self, workflow_id: str, context: Dict[str, Any] = None) -> WorkflowResult:
        """
        執行指定的工作流。
        context 可包含變數，用於 task_template 的 {variable} 替換。
        """
        if workflow_id not in self.workflow_registry:
            return WorkflowResult(
                workflow_id=workflow_id,
                success=False,
                steps=[],
                final_output=f"工作流 [{workflow_id}] 不存在。",
                total_duration_sec=0.0,
            )

        workflow = self.workflow_registry[workflow_id]
        ctx = dict(context or {})
        step_results: List[StepResult] = []
        start_time = time.time()

        steps_by_id = {s.step_id: s for s in workflow.steps}
        step_queue = list(workflow.steps)  # ordered list for sequential execution

        i = 0
        while i < len(step_queue):
            step = step_queue[i]
            result = self._execute_step(step, ctx)
            step_results.append(result)

            # Update context with this step's output
            ctx[step.step_id] = result.output
            ctx["last_output"] = result.output
            if result.agent_name:
                ctx[f"{result.agent_name}_output"] = result.output

            # Handle on_success / on_failure branching
            if result.success and step.on_success:
                target = steps_by_id.get(step.on_success)
                if target and target not in step_queue[i + 1:]:
                    step_queue.insert(i + 1, target)
            elif not result.success and step.on_failure:
                target = steps_by_id.get(step.on_failure)
                if target and target not in step_queue[i + 1:]:
                    step_queue.insert(i + 1, target)

            i += 1

        total_duration = time.time() - start_time
        final_output = ctx.get("last_output", "")
        success = all(r.success for r in step_results) if step_results else False

        workflow_result = WorkflowResult(
            workflow_id=workflow_id,
            success=success,
            steps=step_results,
            final_output=final_output,
            total_duration_sec=round(total_duration, 3),
        )
        self.execution_history.append(workflow_result)
        return workflow_result

    def _execute_step(self, step: WorkflowStep, context: Dict) -> StepResult:
        """分派到對應的執行方法"""
        if step.step_type == StepType.AGENT:
            return self._execute_agent_step(step, context)
        elif step.step_type == StepType.PARALLEL:
            return self._execute_parallel_step(step, context)
        elif step.step_type == StepType.CONDITION:
            passed = self._execute_condition_step(step, context)
            return StepResult(
                step_id=step.step_id,
                agent_name="CONDITION",
                success=passed,
                output="condition_passed" if passed else "condition_failed",
            )
        elif step.step_type == StepType.LOOP:
            return self._execute_loop_step(step, context)
        elif step.step_type == StepType.MERGE:
            merged = self._merge_parallel_results(context)
            return StepResult(
                step_id=step.step_id,
                agent_name="MERGE",
                success=True,
                output=merged,
            )
        return StepResult(
            step_id=step.step_id,
            agent_name="UNKNOWN",
            success=False,
            output="",
            error=f"未知的步驟類型: {step.step_type}",
        )

    def _render_template(self, template: str, context: Dict) -> str:
        """將 task_template 中的 {variable} 替換為 context 中的值"""
        try:
            return template.format(**context)
        except (KeyError, ValueError):
            return template

    def _call_agent(self, agent_name: str, task: str) -> str:
        """呼叫指定 Agent 執行任務"""
        if self.orchestrator and hasattr(self.orchestrator, "agents"):
            agent = self.orchestrator.agents.get(agent_name)
            if agent:
                return agent.run(task)
        # 離線模式：回傳模擬輸出
        return f"[{agent_name}] 執行完成: {task[:80]}"

    def _execute_agent_step(self, step: WorkflowStep, context: Dict) -> StepResult:
        """執行 AGENT 類型步驟"""
        start = time.time()
        task = self._render_template(step.task_template, context)
        agent_name = step.agent_name or "UNKNOWN"
        try:
            output = self._call_agent(agent_name, task)
            duration = time.time() - start
            return StepResult(
                step_id=step.step_id,
                agent_name=agent_name,
                success=True,
                output=output,
                duration_sec=round(duration, 3),
            )
        except Exception as exc:
            duration = time.time() - start
            return StepResult(
                step_id=step.step_id,
                agent_name=agent_name,
                success=False,
                output="",
                duration_sec=round(duration, 3),
                error=str(exc),
            )

    def _execute_parallel_step(self, step: WorkflowStep, context: Dict) -> StepResult:
        """使用 ThreadPoolExecutor 真正平行執行多個子步驟"""
        start = time.time()
        sub_results: List[StepResult] = []

        with ThreadPoolExecutor(max_workers=len(step.parallel_steps) or 1) as executor:
            futures = {
                executor.submit(self._execute_step, sub_step, dict(context)): sub_step
                for sub_step in step.parallel_steps
            }
            for future in as_completed(futures):
                sub_results.append(future.result())

        duration = time.time() - start
        combined_output = "\n---\n".join(
            f"[{r.agent_name}] {r.output}" for r in sub_results
        )
        all_success = all(r.success for r in sub_results)

        # Store individual parallel results in a retrievable format
        context["_parallel_results"] = sub_results

        return StepResult(
            step_id=step.step_id,
            agent_name="PARALLEL",
            success=all_success,
            output=combined_output,
            duration_sec=round(duration, 3),
        )

    def _execute_condition_step(self, step: WorkflowStep, context: Dict) -> bool:
        """評估 condition 表達式，回傳 True/False（使用受限 AST 解析器）"""
        if not step.condition:
            return True
        try:
            return _safe_eval_condition(step.condition, context)
        except Exception:
            return False

    def _execute_loop_step(self, step: WorkflowStep, context: Dict) -> StepResult:
        """重複執行子步驟直到 condition 滿足或達到 max_iterations"""
        last_result = StepResult(
            step_id=step.step_id,
            agent_name=step.agent_name or "LOOP",
            success=False,
            output="",
        )
        for iteration in range(step.max_iterations):
            # Execute the agent task
            task = self._render_template(step.task_template, context)
            agent_name = step.agent_name or "UNKNOWN"
            try:
                output = self._call_agent(agent_name, task)
            except Exception as exc:
                last_result = StepResult(
                    step_id=step.step_id,
                    agent_name=agent_name,
                    success=False,
                    output="",
                    error=str(exc),
                )
                context["last_output"] = ""
                context["eval_score"] = 0.0
                context["iteration"] = iteration + 1
                continue

            # Score the output
            score = self._score_output(output)
            context["eval_score"] = score
            context["last_output"] = output
            context["iteration"] = iteration + 1

            last_result = StepResult(
                step_id=step.step_id,
                agent_name=agent_name,
                success=score >= 0.75,
                output=output,
                score=score,
            )

            # Check condition
            if step.condition:
                passed = self._execute_condition_step(step, context)
            else:
                passed = score >= 0.75

            if passed:
                last_result.success = True
                break

            # Prepare feedback for next iteration
            context["feedback"] = (
                f"第 {iteration + 1} 次嘗試品質分數 {score:.2f}，請改進輸出。"
            )

        return last_result

    def _score_output(self, output: str) -> float:
        """簡單評分：依輸出長度與結構評估品質"""
        if not output:
            return 0.0
        score = 0.3
        if len(output) >= 200:
            score += 0.3
        elif len(output) >= 100:
            score += 0.2
        elif len(output) >= 50:
            score += 0.1
        if "#" in output or "-" in output or "*" in output:
            score += 0.2
        if "\n" in output:
            score += 0.2
        return min(score, 1.0)

    def _merge_parallel_results(self, context: Dict) -> str:
        """合併上一個 parallel 步驟的結果"""
        parallel_results: List[StepResult] = context.get("_parallel_results", [])
        if not parallel_results:
            return context.get("last_output", "")
        return "\n---\n".join(
            f"[{r.agent_name}] {r.output}" for r in parallel_results
        )

    def _register_builtin_workflows(self):
        """註冊預設的業務工作流"""
        now = datetime.datetime.now().strftime("%Y-%m-%d")

        # ── 工作流一：知識永生化完整流程 ────────────────────────────
        knowledge_immortalization = WorkflowDefinition(
            workflow_id="knowledge_immortalization",
            name="知識永生化完整流程",
            description="萃取知識卡片 → 流程優化 → 培訓規劃",
            created_at=now,
            steps=[
                WorkflowStep(
                    step_id="step1_km",
                    step_type=StepType.AGENT,
                    agent_name="KM_AGENT",
                    task_template="請萃取並整理以下內容的知識卡片：{topic}",
                ),
                WorkflowStep(
                    step_id="step2_process",
                    step_type=StepType.AGENT,
                    agent_name="PROCESS_AGENT",
                    task_template="基於以下知識卡片，優化相關業務流程：\n{step1_km}",
                ),
                WorkflowStep(
                    step_id="step3_talent",
                    step_type=StepType.AGENT,
                    agent_name="TALENT_AGENT",
                    task_template=(
                        "基於以下知識與優化流程，規劃培訓計畫：\n"
                        "知識卡片：{step1_km}\n優化流程：{step2_process}"
                    ),
                ),
            ],
        )
        self.register(knowledge_immortalization)

        # ── 工作流二：決策支援完整分析 ──────────────────────────────
        decision_support = WorkflowDefinition(
            workflow_id="decision_support",
            name="決策支援完整分析",
            description="平行分析（流程面 + 人員面）→ 合併 → 綜合決策建議",
            created_at=now,
            steps=[
                WorkflowStep(
                    step_id="step1_parallel",
                    step_type=StepType.PARALLEL,
                    parallel_steps=[
                        WorkflowStep(
                            step_id="step1a_process",
                            step_type=StepType.AGENT,
                            agent_name="PROCESS_AGENT",
                            task_template="從流程面分析以下決策議題：{topic}",
                        ),
                        WorkflowStep(
                            step_id="step1b_talent",
                            step_type=StepType.AGENT,
                            agent_name="TALENT_AGENT",
                            task_template="從人員能力面分析以下決策議題：{topic}",
                        ),
                    ],
                ),
                WorkflowStep(
                    step_id="step2_merge",
                    step_type=StepType.MERGE,
                ),
                WorkflowStep(
                    step_id="step3_decision",
                    step_type=StepType.AGENT,
                    agent_name="DECISION_AGENT",
                    task_template="基於以下多面向分析，提供綜合決策建議：\n{step2_merge}",
                ),
            ],
        )
        self.register(decision_support)

        # ── 工作流三：品質不達標重試（Loop 模式）──────────────────────
        quality_retry = WorkflowDefinition(
            workflow_id="quality_retry",
            name="品質不達標重試",
            description="執行任務 → 評估品質 → 不達標則重試（最多 3 次）",
            created_at=now,
            steps=[
                WorkflowStep(
                    step_id="step1_loop",
                    step_type=StepType.LOOP,
                    agent_name="KM_AGENT",
                    task_template=(
                        "請針對以下任務產出高品質報告：{topic}"
                        "\n{feedback}"
                    ),
                    condition="eval_score >= 0.75",
                    max_iterations=3,
                ),
            ],
        )
        self.register(quality_retry)
