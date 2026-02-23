"""
Agent 基底類別
所有 Domain Agent 的共同抽象介面。
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from harness.git_memory import GitMemory
from harness.core import EnterpriseHarness, SessionResult


class BaseAgent(ABC):
    """
    所有 Domain Agent 的抽象基底類別。
    統一 Agent 介面，支援 EPCC 工作流。
    """

    def __init__(self, name: str, role: str, description: str,
                 trigger_keywords: Optional[List[str]] = None):
        self.name = name
        self.role = role
        self.description = description
        self.trigger_keywords = trigger_keywords or []
        self.status = "IDLE"
        self.harness = EnterpriseHarness()
        self.memory = self.harness.memory
        self._task_count = 0

    def run(self, user_instruction: str) -> str:
        """
        執行完整的 EPCC 工作流。
        子類別只需實作 _execute() 方法。
        """
        self.status = "WORKING"
        self._task_count += 1
        print(f"\n{'='*50}")
        print(f"  [{self.name}] {self.role} 啟動")
        print(f"{'='*50}")

        result = self.harness.run_epcc_cycle(
            agent_name=self.name,
            task=user_instruction,
            executor_fn=self._execute,
        )

        self.status = "IDLE"
        print(f"  [{self.name}] 執行結果: {result}")
        return result.output

    @abstractmethod
    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        """
        子類別必須實作的核心執行邏輯。
        接收任務描述和上下文，回傳執行結果字串。
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """取得 Agent 目前狀態"""
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "tasks_completed": self._task_count,
            "description": self.description,
        }

    def get_capabilities(self) -> List[str]:
        """取得 Agent 能力清單"""
        return self.trigger_keywords

    def matches_intent(self, prompt: str) -> bool:
        """檢查使用者輸入是否匹配此 Agent 的觸發關鍵字"""
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in self.trigger_keywords)

    def __repr__(self):
        return f"<{self.name} | {self.role} | {self.status}>"
