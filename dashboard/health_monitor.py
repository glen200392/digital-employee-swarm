"""
Agent 健康度儀表板
對應參考架構的 Agent Health Dashboard。
即時監控所有 Agent 的運行狀態、完成率、失憶率、人工介入率。
"""

import datetime
from typing import Any, Dict, List, Optional

from harness.eval_engine import EvalEngine
from harness.risk_assessor import RiskAssessor
from harness.git_memory import GitMemory


class AgentHealthDashboard:
    """
    Agent Fleet 健康度監控儀表板。

    監控指標：
    - 完成率：成功完成的任務比例
    - 失憶率：需要重建上下文的比例
    - 人工介入率：需要人類確認的任務比例
    - Git Commit 覆蓋率
    - 知識入庫數量
    """

    def __init__(self, agents: Dict = None,
                 eval_engine: Optional[EvalEngine] = None,
                 risk_assessor: Optional[RiskAssessor] = None,
                 memory: Optional[GitMemory] = None):
        self.agents = agents or {}
        self.eval_engine = eval_engine or EvalEngine()
        self.risk_assessor = risk_assessor or RiskAssessor()
        self.memory = memory or GitMemory()
        self._metrics: Dict[str, Dict] = {}

    def collect_metrics(self) -> Dict[str, Any]:
        """蒐集所有 Agent 的健康度指標"""
        metrics = {}
        for name, agent in self.agents.items():
            status = agent.get_status()
            eval_stats = self.eval_engine.get_agent_stats(name)
            context = self.memory.get_last_context(name)

            metrics[name] = {
                "status": status["status"],
                "role": status["role"],
                "tasks_completed": status["tasks_completed"],
                "avg_score": eval_stats.get("avg_score", 0.0),
                "pass_rate": eval_stats.get("pass_rate", 0.0),
                "has_context": len(context) > 0,
            }

        self._metrics = metrics
        return metrics

    def render(self) -> str:
        """
        產出完整的儀表板報告（CLI 文字版）。
        對應參考文件的 Agent Health Dashboard。
        """
        self.collect_metrics()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 整體統計
        total_agents = len(self._metrics)
        active_agents = sum(
            1 for m in self._metrics.values() if m["status"] == "IDLE"
        )
        total_tasks = sum(m["tasks_completed"] for m in self._metrics.values())

        all_progress = self.memory.get_all_progress()

        lines = [
            "",
            "╔═══════════════════════════════════════════════════════════╗",
            "║              Agent Health Dashboard                      ║",
            f"║              {now}                    ║",
            "╠═══════════════════════════════════════════════════════════╣",
            f"║  Active Agents: {active_agents}/{total_agents}"
            f"        Total Tasks: {total_tasks:<5}"
            f"        Log Entries: {len(all_progress):<5} ║",
            "╠═══════════════════════════════════════════════════════════╣",
        ]

        # 每個 Agent 的指標
        for name, m in self._metrics.items():
            icon = "🟢" if m["status"] == "IDLE" else "🔵"
            context_icon = "✅" if m["has_context"] else "⚠️"
            lines.append(
                f"║ {icon} {name:<18} │ {m['role']:<12} │ "
                f"Tasks: {m['tasks_completed']:<3} │ "
                f"Score: {m['avg_score']:.1f} │ "
                f"Ctx: {context_icon} ║"
            )

        lines.append("╠═══════════════════════════════════════════════════════════╣")

        # Eval Engine 報告
        eval_report = self.eval_engine.get_report()
        for line in eval_report.split("\n"):
            lines.append(f"║  {line:<55} ║")

        # Risk Report
        risk_report = self.risk_assessor.get_report()
        for line in risk_report.split("\n"):
            lines.append(f"║  {line:<55} ║")

        lines.append("╚═══════════════════════════════════════════════════════════╝")
        return "\n".join(lines)

    def get_alerts(self) -> List[str]:
        """取得需要關注的警示"""
        self.collect_metrics()
        alerts = []

        for name, m in self._metrics.items():
            if m["avg_score"] > 0 and m["avg_score"] < 0.5:
                alerts.append(
                    f"🔴 {name}: 平均品質分數過低 ({m['avg_score']:.1f})"
                )
            if not m["has_context"]:
                alerts.append(
                    f"⚠️ {name}: 無歷史上下文（可能是首次執行）"
                )

        return alerts
