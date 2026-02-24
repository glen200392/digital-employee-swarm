"""
Task Planner — 複雜任務拆解與多 Agent 協作
將複合任務拆解為子任務序列，支援 Sequential / Parallel 兩種執行模式。
"""
import uuid
import re
import concurrent.futures
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


class ExecutionMode(Enum):
    SEQUENTIAL = "sequential"   # 依序執行（後者可使用前者結果）
    PARALLEL   = "parallel"     # 並行執行（互相獨立）


@dataclass
class SubTask:
    sub_task_id: str        # 例如 "ST-001"
    parent_task_id: str     # 來自哪個主任務
    agent_name: str         # 指派給哪個 Agent（KM_AGENT / PROCESS_AGENT 等）
    task: str               # 子任務內容
    priority: int           # 優先級（1最高）
    depends_on: List[str]   # 依賴的子任務 ID（空表示無依賴）
    status: str = "PENDING" # PENDING / RUNNING / COMPLETED / FAILED
    result: Optional[str] = None


@dataclass
class PlanResult:
    plan_id: str
    original_task: str
    sub_tasks: List[SubTask]
    execution_mode: ExecutionMode
    aggregated_output: str = ""
    success: bool = False


# 關鍵字 → ExecutionMode
_PARALLEL_KEYWORDS = ["and", "並且", "同時", "以及", "並"]
_SEQUENTIAL_KEYWORDS = ["然後", "接著", "之後", "先", "再"]

# 關鍵字 → Agent 名稱
_AGENT_KEYWORD_MAP: List[tuple] = [
    (["sop", "流程", "採購", "優化", "效率", "瓶頸"], "PROCESS_AGENT"),
    (["人才", "培訓", "員工", "能力", "學習", "評估"], "TALENT_AGENT"),
    (["知識", "萃取", "文件", "整理"],                 "KM_AGENT"),
    (["決策", "分析", "風險", "比較", "數據", "建議"],  "DECISION_AGENT"),
]

# 任務被視為複合任務的觸發詞（且 不在 _PARALLEL_KEYWORDS 中，故單獨加入）
_COMPOUND_TRIGGERS = _PARALLEL_KEYWORDS + _SEQUENTIAL_KEYWORDS + ["且"]

# 截斷前置結果的最大長度（供 SEQUENTIAL 模式傳遞上下文用）
_MAX_PREV_RESULT_LENGTH = 200

# 分割複合任務的 regex（從既有關鍵字動態建構）
_SPLIT_SEPARATOR_RE = (
    r"[，,、；;]"
    + "|" + "|".join(re.escape(kw) for kw in _PARALLEL_KEYWORDS + _SEQUENTIAL_KEYWORDS if kw != "and")
    + r"|and\b"
)


def _detect_agent(text: str) -> str:
    """依關鍵字判斷應指派的 Agent，預設 KM_AGENT。"""
    text_lower = text.lower()
    for keywords, agent in _AGENT_KEYWORD_MAP:
        if any(kw in text_lower for kw in keywords):
            return agent
    return "KM_AGENT"


def _split_task_text(task: str) -> List[str]:
    """將複合任務文字拆成多個子句。"""
    parts = re.split(_SPLIT_SEPARATOR_RE, task, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


class TaskPlanner:
    """
    任務規劃器。

    核心方法：
    1. plan(task) → PlanResult
    2. execute(plan, agent_executors) → PlanResult
    3. aggregate(plan) → str
    """

    SUPPORTED_AGENTS = ["KM_AGENT", "PROCESS_AGENT", "TALENT_AGENT", "DECISION_AGENT"]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def plan(self, task: str, llm_provider=None) -> PlanResult:
        """分析並產生執行計畫。有 LLM 時優先使用 LLM；否則規則型 fallback。"""
        if llm_provider is not None and getattr(llm_provider, "is_llm_available", False):
            try:
                return self._llm_based_plan(task, llm_provider)
            except Exception:
                pass  # fallback to rule-based
        return self._rule_based_plan(task)

    def execute(self, plan: PlanResult, agent_executors: Dict[str, Callable]) -> PlanResult:
        """依照 execution_mode 執行子任務。"""
        if plan.execution_mode == ExecutionMode.PARALLEL:
            self._execute_parallel(plan, agent_executors)
        else:
            self._execute_sequential(plan, agent_executors)

        plan.success = all(st.status == "COMPLETED" for st in plan.sub_tasks)
        return plan

    def aggregate(self, plan: PlanResult) -> str:
        """合併所有子任務的結果，生成統一報告。"""
        lines = [f"=== 任務規劃報告 ({plan.plan_id}) ===",
                 f"原始任務: {plan.original_task}",
                 f"執行模式: {plan.execution_mode.value}",
                 f"子任務數: {len(plan.sub_tasks)}",
                 ""]
        for st in plan.sub_tasks:
            lines.append(f"[{st.sub_task_id}] {st.agent_name} — {st.task}")
            lines.append(f"  狀態: {st.status}")
            if st.result:
                lines.append(f"  結果: {st.result}")
            lines.append("")

        status_label = "✅ 成功" if plan.success else "⚠️ 部分失敗"
        lines.append(f"整體狀態: {status_label}")
        plan.aggregated_output = "\n".join(lines)
        return plan.aggregated_output

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _is_complex_task(self, task: str) -> bool:
        """判斷是否為複合任務（包含多個動作/目標）。"""
        task_lower = task.lower()
        if any(kw in task_lower for kw in _COMPOUND_TRIGGERS):
            return True
        # 以逗號/分號分隔且各部分有實際內容也視為複合任務
        parts = _split_task_text(task)
        return len(parts) >= 2

    def _rule_based_plan(self, task: str) -> PlanResult:
        """規則型任務規劃（無 LLM fallback）。"""
        plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"

        if not self._is_complex_task(task):
            # 簡單任務 — 單一子任務，不拆解
            agent = _detect_agent(task)
            sub_task = SubTask(
                sub_task_id="ST-001",
                parent_task_id=plan_id,
                agent_name=agent,
                task=task,
                priority=1,
                depends_on=[],
            )
            return PlanResult(
                plan_id=plan_id,
                original_task=task,
                sub_tasks=[sub_task],
                execution_mode=ExecutionMode.SEQUENTIAL,
            )

        # 複合任務 — 判斷執行模式
        task_lower = task.lower()
        if any(kw in task_lower for kw in _SEQUENTIAL_KEYWORDS):
            mode = ExecutionMode.SEQUENTIAL
        else:
            mode = ExecutionMode.PARALLEL

        # 拆解子任務
        parts = _split_task_text(task)
        if len(parts) < 2:
            # 無法進一步拆解，回傳單一子任務
            agent = _detect_agent(task)
            return PlanResult(
                plan_id=plan_id,
                original_task=task,
                sub_tasks=[SubTask(
                    sub_task_id="ST-001",
                    parent_task_id=plan_id,
                    agent_name=agent,
                    task=task,
                    priority=1,
                    depends_on=[],
                )],
                execution_mode=mode,
            )

        sub_tasks: List[SubTask] = []
        prev_id: Optional[str] = None
        for i, part in enumerate(parts[:5], start=1):  # 最多 5 個子任務
            st_id = f"ST-{i:03d}"
            depends = [prev_id] if (mode == ExecutionMode.SEQUENTIAL and prev_id) else []
            sub_tasks.append(SubTask(
                sub_task_id=st_id,
                parent_task_id=plan_id,
                agent_name=_detect_agent(part),
                task=part,
                priority=i,
                depends_on=depends,
            ))
            prev_id = st_id

        return PlanResult(
            plan_id=plan_id,
            original_task=task,
            sub_tasks=sub_tasks,
            execution_mode=mode,
        )

    def _llm_based_plan(self, task: str, llm) -> PlanResult:
        """LLM 輔助拆解（呼叫 LLM，解析回傳的 JSON 格式計畫）。"""
        import json

        prompt = (
            "你是任務規劃器。請將以下複合任務拆解為子任務，並以 JSON 回傳。\n"
            "格式：{\"mode\": \"sequential|parallel\", \"sub_tasks\": "
            "[{\"task\": \"...\", \"agent\": \"KM_AGENT|PROCESS_AGENT|TALENT_AGENT|DECISION_AGENT\"}]}\n"
            f"任務：{task}"
        )
        response = llm.chat(prompt)
        if not response:
            raise ValueError("LLM returned empty response")

        text = response.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        data = json.loads(text)
        mode_str = data.get("mode", "parallel").lower()
        mode = ExecutionMode.SEQUENTIAL if mode_str == "sequential" else ExecutionMode.PARALLEL

        plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"
        sub_tasks: List[SubTask] = []
        prev_id: Optional[str] = None
        for i, item in enumerate(data.get("sub_tasks", [])[:5], start=1):
            st_id = f"ST-{i:03d}"
            agent = item.get("agent", "KM_AGENT")
            if agent not in self.SUPPORTED_AGENTS:
                agent = "KM_AGENT"
            depends = [prev_id] if (mode == ExecutionMode.SEQUENTIAL and prev_id) else []
            sub_tasks.append(SubTask(
                sub_task_id=st_id,
                parent_task_id=plan_id,
                agent_name=agent,
                task=item.get("task", task),
                priority=i,
                depends_on=depends,
            ))
            prev_id = st_id

        if not sub_tasks:
            raise ValueError("LLM returned no sub_tasks")

        return PlanResult(
            plan_id=plan_id,
            original_task=task,
            sub_tasks=sub_tasks,
            execution_mode=mode,
        )

    def _execute_sequential(self, plan: PlanResult, agent_executors: Dict[str, Callable]) -> None:
        """依序執行子任務；後者可取得前一個結果作為上下文。"""
        prev_result: Optional[str] = None
        for st in plan.sub_tasks:
            executor = agent_executors.get(st.agent_name)
            if executor is None:
                st.status = "FAILED"
                st.result = f"找不到 executor for {st.agent_name}"
                continue
            st.status = "RUNNING"
            task_input = st.task
            if prev_result:
                task_input = f"{st.task}（前置結果參考：{prev_result[:_MAX_PREV_RESULT_LENGTH]}）"
            try:
                st.result = executor(task_input)
                st.status = "COMPLETED"
                prev_result = st.result
            except Exception as exc:  # pragma: no cover
                st.status = "FAILED"
                st.result = str(exc)
                prev_result = None

    def _execute_parallel(self, plan: PlanResult, agent_executors: Dict[str, Callable]) -> None:
        """並行執行所有子任務。"""
        def _run(st: SubTask) -> None:
            executor = agent_executors.get(st.agent_name)
            if executor is None:
                st.status = "FAILED"
                st.result = f"找不到 executor for {st.agent_name}"
                return
            st.status = "RUNNING"
            try:
                st.result = executor(st.task)
                st.status = "COMPLETED"
            except Exception as exc:  # pragma: no cover
                st.status = "FAILED"
                st.result = str(exc)

        with concurrent.futures.ThreadPoolExecutor() as pool:
            list(pool.map(_run, plan.sub_tasks))
