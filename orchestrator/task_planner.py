"""
TaskPlanner — 複雜任務自動拆解器
使用 LLM 將複雜的使用者指令分析為多個子任務，
並決定執行模式（Sequential / Parallel）。
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional, Any

from orchestrator.intent_classifier import AGENT_KEYWORDS


PLANNER_PROMPT = """
你是企業 AI 員工管理系統的任務規劃師。
你的工作是分析使用者的複雜指令，判斷是否需要多個 AI Agent 協作，並規劃執行方案。

可用的 AI Agent：
1. KM_AGENT — 知識萃取專家：知識萃取、SOP 整理、文件分析
2. PROCESS_AGENT — 流程優化顧問：流程分析、效率優化、瓶頸識別
3. TALENT_AGENT — 人才發展顧問：能力評估、培訓規劃、學習路徑
4. DECISION_AGENT — 決策支援分析師：數據分析、風險評估、方案比較

請判斷使用者的指令是否需要多個 Agent，並輸出以下 JSON：

如果只需要一個 Agent：
{{"type": "single", "agent": "AGENT_NAME", "task": "任務描述"}}

如果需要多個 Agent（Sequential — 前一個的輸出是後一個的輸入）：
{{"type": "sequential", "steps": [{{"agent": "AGENT_NAME", "task": "子任務描述"}}, ...]}}

如果需要多個 Agent（Parallel — 可以同時執行，最後合併）：
{{"type": "parallel", "steps": [{{"agent": "AGENT_NAME", "task": "子任務描述"}}, ...], "merge_instruction": "如何合併結果"}}

使用者指令：{prompt}
"""


@dataclass
class SubTask:
    agent_name: str
    task: str
    depends_on: Optional[str] = None  # 依賴的前置子任務 ID


@dataclass
class ExecutionPlan:
    plan_type: str  # "single" | "sequential" | "parallel"
    steps: List[SubTask] = field(default_factory=list)
    merge_instruction: str = ""
    original_prompt: str = ""


class TaskPlanner:
    """
    複雜任務自動拆解器。
    有 LLM 時使用 AI 分析，無 LLM 時 fallback 到關鍵字多命中偵測。
    """

    def __init__(self, llm_provider: Optional[Any] = None):
        self._llm = llm_provider

    @property
    def llm(self):
        if self._llm is None:
            try:
                from harness.llm_provider import LLMProvider
                self._llm = LLMProvider()
            except Exception:
                pass
        return self._llm

    def plan(self, user_prompt: str) -> ExecutionPlan:
        """分析指令，返回執行計畫"""
        if self.llm and self.llm.is_llm_available:
            result = self._plan_with_llm(user_prompt)
            if result is not None:
                result.original_prompt = user_prompt
                return result

        plan = self._plan_with_keywords(user_prompt)
        plan.original_prompt = user_prompt
        return plan

    def _plan_with_llm(self, prompt: str) -> Optional[ExecutionPlan]:
        """使用 LLM 進行任務規劃"""
        try:
            full_prompt = PLANNER_PROMPT.format(prompt=prompt)
            response = self.llm.chat(full_prompt)
            if not response:
                return None

            text = response.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            return self._parse_plan(data)

        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None

    def _parse_plan(self, data: dict) -> Optional[ExecutionPlan]:
        """解析 LLM 回傳的 JSON 為 ExecutionPlan"""
        valid_agents = list(AGENT_KEYWORDS.keys())
        plan_type = data.get("type", "single")

        if plan_type == "single":
            agent = data.get("agent", "")
            if agent not in valid_agents:
                return None
            task = data.get("task", "")
            return ExecutionPlan(
                plan_type="single",
                steps=[SubTask(agent_name=agent, task=task)],
            )

        elif plan_type in ("sequential", "parallel"):
            steps_data = data.get("steps", [])
            steps = []
            for s in steps_data:
                agent = s.get("agent", "")
                if agent not in valid_agents:
                    continue
                steps.append(SubTask(agent_name=agent, task=s.get("task", "")))
            if not steps:
                return None
            merge_instruction = data.get("merge_instruction", "")
            return ExecutionPlan(
                plan_type=plan_type,
                steps=steps,
                merge_instruction=merge_instruction,
            )

        return None

    def _plan_with_keywords(self, prompt: str) -> ExecutionPlan:
        """Fallback: 多關鍵字命中時使用 sequential 模式"""
        prompt_lower = prompt.lower()
        matched: List[str] = []

        for agent_name, keywords in AGENT_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                matched.append(agent_name)

        if len(matched) == 0:
            # 找最佳單一 agent（score 最高）
            scores = {}
            for agent_name, keywords in AGENT_KEYWORDS.items():
                score = sum(1 for kw in keywords if kw in prompt_lower)
                if score > 0:
                    scores[agent_name] = score
            if scores:
                best = max(scores, key=scores.get)
                return ExecutionPlan(
                    plan_type="single",
                    steps=[SubTask(agent_name=best, task=prompt)],
                )
            # 完全無法匹配
            return ExecutionPlan(
                plan_type="single",
                steps=[SubTask(agent_name="UNKNOWN", task=prompt)],
            )

        if len(matched) == 1:
            return ExecutionPlan(
                plan_type="single",
                steps=[SubTask(agent_name=matched[0], task=prompt)],
            )

        # ≥2 個 Domain 關鍵字 → sequential
        steps = [SubTask(agent_name=a, task=prompt) for a in matched]
        return ExecutionPlan(
            plan_type="sequential",
            steps=steps,
        )
