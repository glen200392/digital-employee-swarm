"""
Master Orchestrator（中央指揮官）
整合 LLM + A2A + MCP + Skill 的完整指揮系統。
"""

from typing import Dict, List, Optional

from harness.task_queue import TaskQueue, TaskPriority
from agents.km_agent import KMAgent
from agents.process_agent import ProcessAgent
from agents.talent_agent import TalentAgent
from agents.decision_agent import DecisionAgent
from agents.base_agent import BaseAgent
from orchestrator.intent_classifier import IntentClassifier
from harness.risk_assessor import RiskAssessor
from harness.llm_provider import LLMProvider
from harness.skill_registry import SkillRegistry
from protocols.a2a import A2AProtocol, AgentCard
from protocols.mcp import MCPConnector


class MasterOrchestrator:
    """
    中央指揮官：整合所有子系統。
    
    啟動流程：
    1. 初始化 LLM Provider + Skill Registry（共享資源）
    2. 初始化 4 個 Domain Agent
    3. 註冊所有 Agent 到 A2A 網路
    4. 初始化 MCP 連接器
    5. 等待使用者指令
    """

    def __init__(self):
        # 共享資源
        self.llm = LLMProvider()
        self.skill_registry = SkillRegistry()

        # 初始化共享資源到 BaseAgent
        BaseAgent.init_shared_resources(self.llm, self.skill_registry)

        # 初始化所有 Domain Agent
        self.agents: Dict[str, BaseAgent] = {
            "KM_AGENT": KMAgent(),
            "PROCESS_AGENT": ProcessAgent(),
            "TALENT_AGENT": TalentAgent(),
            "DECISION_AGENT": DecisionAgent(),
        }

        self.classifier = IntentClassifier()
        self.risk_assessor = RiskAssessor()

        # A2A 協議 — 自動註冊所有 Agent
        self.a2a = A2AProtocol()
        self._register_agents_to_a2a()

        # MCP 連接器
        self.mcp = MCPConnector()

        self.dispatch_log: List[Dict] = []

        # 非同步任務佇列
        self.task_queue = TaskQueue(
            db_path="data/task_queue.db",
            num_workers=2,
            agent_executor=self._execute_for_queue,
        )
        self.task_queue.start()

    def _register_agents_to_a2a(self):
        """將所有 Agent 註冊到 A2A 網路"""
        for name, agent in self.agents.items():
            card = AgentCard(
                name=name,
                capabilities=agent.trigger_keywords,
                executor=agent.run,  # 真實綁定 Agent.run()
            )
            self.a2a.register_agent(card)

    def submit(
        self,
        agent_name: str,
        instruction: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        callback_url: Optional[str] = None,
    ) -> str:
        """非同步提交任務，返回 task_id（不等待結果）"""
        return self.task_queue.enqueue(
            agent_name, instruction, priority, callback_url
        )

    def _execute_for_queue(self, agent_name: str, instruction: str) -> str:
        """供 TaskQueue Worker 呼叫的執行器"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent [{agent_name}] 不存在")
        return self.agents[agent_name].run(instruction)

    def dispatch(self, user_prompt: str) -> str:
        """接收使用者指令，分析意圖，派發給對應 Agent。"""
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

        # 3. Agent 可用性
        if agent_name not in self.agents:
            return f"Agent [{agent_name}] 尚未就緒。"

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
        """取得所有 Agent + 子系統的狀態"""
        llm_status = self.llm.get_status()
        llm_icon = "🟢" if llm_status["is_llm"] else "🟡"
        llm_label = llm_status["active"] if llm_status["is_llm"] else "離線模式"

        lines = [
            "╔══════════════════════════════════════════════════╗",
            "║           Agent Fleet Status Dashboard           ║",
            "╠══════════════════════════════════════════════════╣",
            f"║  {llm_icon} LLM Provider: {llm_label:<30}  ║",
            "╠══════════════════════════════════════════════════╣",
        ]
        for name, agent in self.agents.items():
            status = agent.get_status()
            icon = "🟢" if status["status"] == "IDLE" else "🔵"
            lines.append(
                f"║  {icon} {name:<18} │ {status['role']:<10} │ "
                f"Tasks: {status['tasks_completed']:<3}  ║"
            )
        lines.append("╚══════════════════════════════════════════════════╝")
        return "\n".join(lines)

    def get_dispatch_history(self) -> str:
        if not self.dispatch_log:
            return "尚無分派記錄。"
        lines = ["=== Dispatch History ==="]
        for i, entry in enumerate(self.dispatch_log[-10:], 1):
            lines.append(
                f"  {i}. [{entry['agent']}] ({entry['risk']}) "
                f"{entry['prompt'][:40]}..."
            )
        return "\n".join(lines)