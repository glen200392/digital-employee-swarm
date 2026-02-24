"""
Agent 基底類別
所有 Domain Agent 的共同抽象介面，整合 LLM + Skill + EPCC。
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from harness.git_memory import GitMemory
from harness.core import EnterpriseHarness, SessionResult
from harness.llm_provider import LLMProvider
from harness.skill_registry import SkillRegistry
from harness.agent_profile import AgentProfileStore


class BaseAgent(ABC):
    """
    所有 Domain Agent 的抽象基底類別。
    統一 Agent 介面，支援 LLM 呼叫 + Skill 技能 + EPCC 工作流。
    """

    # 共享的 LLM Provider 和 Skill Registry（全系統單例）
    _shared_llm: Optional[LLMProvider] = None
    _shared_skills: Optional[SkillRegistry] = None
    _shared_profile_store: Optional[AgentProfileStore] = None

    def __init__(self, name: str, role: str, description: str,
                 system_prompt: str = "",
                 trigger_keywords: Optional[List[str]] = None):
        self.name = name
        self.role = role
        self.description = description
        self.system_prompt = system_prompt
        self.trigger_keywords = trigger_keywords or []
        self.status = "IDLE"
        self.harness = EnterpriseHarness()
        self.memory = self.harness.memory
        self._task_count = 0

    @classmethod
    def init_shared_resources(cls, llm: Optional[LLMProvider] = None,
                              skills: Optional[SkillRegistry] = None,
                              profile_store: Optional[AgentProfileStore] = None):
        """初始化共享資源（由 Orchestrator 在啟動時呼叫一次）"""
        cls._shared_llm = llm or LLMProvider()
        cls._shared_skills = skills or SkillRegistry()
        cls._shared_profile_store = profile_store

    @property
    def llm(self) -> LLMProvider:
        if self._shared_llm is None:
            BaseAgent._shared_llm = LLMProvider()
        return self._shared_llm

    @property
    def skills(self) -> SkillRegistry:
        if self._shared_skills is None:
            BaseAgent._shared_skills = SkillRegistry()
        return self._shared_skills

    def run(self, user_instruction: str) -> str:
        """
        執行完整的 EPCC 工作流。
        子類別只需實作 _execute() 方法。
        """
        self.status = "WORKING"
        self._task_count += 1
        print(f"\n{'='*50}")
        print(f"  [{self.name}] {self.role} 啟動")
        llm_mode = f"LLM: {self.llm.provider_name}" if self.llm.is_llm_available else "離線模式"
        print(f"  [{self.name}] {llm_mode}")
        print(f"{'='*50}")

        start_time = time.time()
        result = self.harness.run_epcc_cycle(
            agent_name=self.name,
            task=user_instruction,
            executor_fn=self._execute,
        )
        duration = time.time() - start_time

        # 更新 Agent 員工檔案
        if self._shared_profile_store:
            profile = self._shared_profile_store.load_profile(self.name)
            if profile:
                tokens = getattr(result, "tokens_used", 0)
                profile.record_task(
                    score=result.eval_score,
                    duration_sec=duration,
                    tokens=tokens,
                )
                self._shared_profile_store.save_profile(profile)
                self._shared_profile_store.record_performance(
                    self.name, profile.get_today_snapshot()
                )

        self.status = "IDLE"
        print(f"  [{self.name}] 執行結果: {result}")
        return result.output

    def call_llm(self, prompt: str, fallback: str = "") -> str:
        """
        呼叫 LLM。若無可用 LLM 或呼叫失敗，使用 fallback 值。
        """
        response = self.llm.chat(prompt, system_prompt=self.system_prompt)
        return response if response else fallback

    @abstractmethod
    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        """子類別必須實作的核心執行邏輯。"""
        pass

    def get_status(self) -> Dict[str, Any]:
        """取得 Agent 目前狀態"""
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "tasks_completed": self._task_count,
            "description": self.description,
            "llm_provider": self.llm.provider_name,
        }

    def get_capabilities(self) -> List[str]:
        return self.trigger_keywords

    def matches_intent(self, prompt: str) -> bool:
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in self.trigger_keywords)

    def __repr__(self):
        return f"<{self.name} | {self.role} | {self.status}>"
