"""
Enterprise Harness 核心模組
實作 Anthropic 雙層 Harness 設計 + EPCC 工作流
"""

import datetime
from typing import Any, Dict, Optional

from harness.git_memory import GitMemory
from harness.eval_engine import EvalEngine
from harness.risk_assessor import RiskAssessor, RiskLevel


class SessionResult:
    """單次 Agent Session 的執行結果"""

    def __init__(self, agent_name: str, task_id: str, success: bool,
                 output: str, risk_level: RiskLevel = RiskLevel.LOW,
                 eval_score: float = 0.0):
        self.agent_name = agent_name
        self.task_id = task_id
        self.success = success
        self.output = output
        self.risk_level = risk_level
        self.eval_score = eval_score
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __repr__(self):
        status = "✅" if self.success else "❌"
        return (
            f"{status} [{self.agent_name}] Task-{self.task_id} | "
            f"Score: {self.eval_score:.1f} | Risk: {self.risk_level.value}"
        )


class EnterpriseHarness:
    """
    企業級 Harness 核心架構
    整合 Anthropic 雙層設計 + Google A2A + OpenAI Swarm 模式

    流程：
    1. Initializer 重建 Context（Anthropic 模式）
    2. EPCC 執行週期
    3. 風險評估護欄（人類確認節點）
    4. 執行與追蹤
    5. Commit + 狀態持久化
    """

    def __init__(self, repo_path: Optional[str] = None):
        self.memory = GitMemory(repo_path)
        self.eval_engine = EvalEngine()
        self.risk_assessor = RiskAssessor()

    def restore_context(self, agent_name: str) -> Dict[str, Any]:
        """
        Initializer Agent 功能：Session 開始時重建上下文。
        讀取 Git Log、PROGRESS.md、AGENTS.md 來恢復記憶。
        """
        context = {
            "agent_name": agent_name,
            "last_progress": self.memory.get_last_context(agent_name),
            "session_start": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return context

    def assess_risk(self, task: str, agent_name: str) -> RiskLevel:
        """風險評估護欄"""
        return self.risk_assessor.assess(task, agent_name)

    def evaluate_output(self, agent_name: str, task: str,
                        output: str) -> float:
        """評估 Agent 輸出品質"""
        return self.eval_engine.evaluate(agent_name, task, output)

    def commit_session(self, result: SessionResult):
        """
        Session 結束時的 Commit 操作。
        確保每個 Session 都留下記憶（Anthropic 原則）。
        """
        status = "COMPLETED" if result.success else "FAILED"
        message = (
            f"{status} | Score: {result.eval_score:.1f} | "
            f"Risk: {result.risk_level.value} | {result.output[:100]}"
        )
        self.memory.commit_progress(
            result.agent_name, result.task_id, message
        )

    def run_epcc_cycle(self, agent_name: str, task: str,
                       executor_fn=None) -> SessionResult:
        """
        完整 EPCC（Explore → Plan → Code → Commit）週期。
        這是 Anthropic 社群驗證的實用執行框架。
        """
        import time
        task_id = f"TASK-{int(time.time())}"

        # E: Explore — 恢復上下文
        context = self.restore_context(agent_name)
        print(f"  [Harness] Explore: 上下文已恢復 ({len(context['last_progress'])} 條記憶)")

        # P: Plan — 風險評估
        risk = self.assess_risk(task, agent_name)
        print(f"  [Harness] Plan: 風險等級 = {risk.value}")

        if risk == RiskLevel.HIGH:
            print(f"  [Harness] ⚠️  高風險任務，需要 Harness Architect 確認")

        # C: Code — 執行任務
        try:
            if executor_fn:
                output = executor_fn(task, context)
            else:
                output = f"[模擬] 已處理任務: {task}"
            success = True
        except Exception as e:
            output = f"執行失敗: {str(e)}"
            success = False

        # Evaluate
        eval_score = self.evaluate_output(agent_name, task, output)
        print(f"  [Harness] Eval: 品質分數 = {eval_score:.1f}")

        # C: Commit — 提交結果
        result = SessionResult(
            agent_name=agent_name,
            task_id=task_id,
            success=success,
            output=output,
            risk_level=risk,
            eval_score=eval_score,
        )
        self.commit_session(result)

        return result
