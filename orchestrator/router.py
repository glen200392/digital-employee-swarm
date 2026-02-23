"""
Master Orchestrator（中央指揮官）
對應架構 Layer 1：指揮層 Orchestration。
接收 DTO 意圖指令 → 意圖分析 → 風險評估 → 派發給 Domain Agent。
"""

from typing import Dict, List, Optional

from agents.km_agent import KMAgent
from agents.process_agent import ProcessAgent
from agents.talent_agent import TalentAgent
from agents.decision_agent import DecisionAgent
from agents.base_agent import BaseAgent
from orchestrator.intent_classifier import IntentClassifier
from harness.risk_assessor import RiskAssessor


class MasterOrchestrator:
    """
    中央指揮官：根據 AGENTS.md 的定義進行任務路由。

    決策流程：
    1. 接收使用者自然語言指令
    2. IntentClassifier 解析意圖
    3. RiskAssessor 評估風險
    4. 派發給對應的 Domain Agent
    5. 監控執行並彙整回報
    """

    def __init__(self):
        # 初始化所有 Domain Agent
        self.agents: Dict[str, BaseAgent] = {
            "KM_AGENT": KMAgent(),
            "PROCESS_AGENT": ProcessAgent(),
            "TALENT_AGENT": TalentAgent(),
            "DECISION_AGENT": DecisionAgent(),
        }

        self.classifier = IntentClassifier()
        self.risk_assessor = RiskAssessor()
        self.dispatch_log: List[Dict] = []

    def dispatch(self, user_prompt: str) -> str:
        """
        接收使用者指令，分析意圖，派發給對應 Agent。
        """
        print(f"\n[Orchestrator] 收到指令: {user_prompt}")

        # 1. 意圖分析
        agent_name, confidence = self.classifier.classify(user_prompt)
        print(f"[Orchestrator] 意圖識別 → {agent_name} (信心度: {confidence:.0%})")

        if agent_name == "UNKNOWN":
            return self._handle_unknown(user_prompt)

        # 2. 風險評估
        risk = self.risk_assessor.assess(user_prompt, agent_name)
        approval_role = self.risk_assessor.get_approval_role(risk)
        print(f"[Orchestrator] 風險等級: {risk.value} → {approval_role}")

        # 3. 檢查 Agent 是否可用
        if agent_name not in self.agents:
            return f"Agent [{agent_name}] 目前尚未就緒或正在開發中。"

        # 4. 派發任務
        agent = self.agents[agent_name]
        result = agent.run(user_prompt)

        # 5. 記錄
        self.dispatch_log.append({
            "prompt": user_prompt[:80],
            "agent": agent_name,
            "confidence": confidence,
            "risk": risk.value,
            "result": result[:100] if result else "N/A",
        })

        return result

    def _handle_unknown(self, prompt: str) -> str:
        """處理無法識別意圖的情況"""
        keywords_hint = self.classifier.suggest_keywords()
        return (
            "抱歉，我不確定該找哪位數位員工處理此需求。\n"
            "請嘗試使用以下關鍵字：\n"
            f"{keywords_hint}\n\n"
            "範例：\n"
            "  - '請幫我萃取採購SOP' → KM Agent\n"
            "  - '優化出貨流程' → Process Agent\n"
            "  - '評估新人能力' → Talent Agent\n"
            "  - '分析風險' → Decision Agent"
        )

    def get_status(self) -> str:
        """取得所有 Agent 的狀態摘要"""
        lines = [
            "╔══════════════════════════════════════════╗",
            "║        Agent Fleet Status Dashboard       ║",
            "╠══════════════════════════════════════════╣",
        ]
        for name, agent in self.agents.items():
            status = agent.get_status()
            icon = "🟢" if status["status"] == "IDLE" else "🔵"
            lines.append(
                f"║ {icon} {name:<18} │ "
                f"{status['role']:<12} │ "
                f"Tasks: {status['tasks_completed']:<3} ║"
            )
        lines.append("╚══════════════════════════════════════════╝")
        return "\n".join(lines)

    def get_dispatch_history(self) -> str:
        """取得任務分派歷史"""
        if not self.dispatch_log:
            return "尚無分派記錄。"

        lines = ["=== Dispatch History ==="]
        for i, entry in enumerate(self.dispatch_log[-10:], 1):
            lines.append(
                f"  {i}. [{entry['agent']}] ({entry['risk']}) "
                f"{entry['prompt'][:40]}..."
            )
        return "\n".join(lines)