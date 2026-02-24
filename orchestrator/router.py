"""
Master Orchestrator（中央指揮官）
整合 LLM + A2A + MCP + Skill 的完整指揮系統。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from agents.km_agent import KMAgent
from agents.process_agent import ProcessAgent
from agents.talent_agent import TalentAgent
from agents.decision_agent import DecisionAgent
from agents.base_agent import BaseAgent
from orchestrator.intent_classifier import IntentClassifier
from orchestrator.task_planner import TaskPlanner, ExecutionPlan
from orchestrator.result_aggregator import ResultAggregator
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
        self.planner = TaskPlanner(llm_provider=self.llm)
        self.aggregator = ResultAggregator()

        # A2A 協議 — 自動註冊所有 Agent
        self.a2a = A2AProtocol()
        self._register_agents_to_a2a()

        # MCP 連接器
        self.mcp = MCPConnector()

        self.dispatch_log: List[Dict] = []

    def _register_agents_to_a2a(self):
        """將所有 Agent 註冊到 A2A 網路"""
        for name, agent in self.agents.items():
            card = AgentCard(
                name=name,
                capabilities=agent.trigger_keywords,
                executor=agent.run,  # 真實綁定 Agent.run()
            )
            self.a2a.register_agent(card)

    def dispatch(self, user_prompt: str) -> str:
        """接收使用者指令，分析意圖，派發給對應 Agent。"""
        print(f"\n[Orchestrator] 收到指令: {user_prompt}")

        # 1. 用 TaskPlanner 分析執行計畫
        plan = self.planner.plan(user_prompt)
        print(f"[Orchestrator] 執行計畫: {plan.plan_type} ({len(plan.steps)} 步)")

        if plan.plan_type == "single":
            agent_name = plan.steps[0].agent_name if plan.steps else "UNKNOWN"
            return self._dispatch_single(user_prompt, agent_name)
        elif plan.plan_type == "sequential":
            return self._dispatch_sequential(plan)
        elif plan.plan_type == "parallel":
            return self._dispatch_parallel(plan)

        return self._dispatch_single(user_prompt, "UNKNOWN")

    def _dispatch_single(self, user_prompt: str, agent_name: str) -> str:
        """派發給單一 Agent（含風險評估與記錄）"""
        # 意圖分析（補充信心度）
        classified_agent, confidence = self.classifier.classify(user_prompt)
        # 如果 TaskPlanner 指定了 agent，優先使用
        if not agent_name or agent_name == "UNKNOWN":
            agent_name = classified_agent

        print(f"[Orchestrator] 意圖識別 → {agent_name} (信心度: {confidence:.0%})")

        if agent_name == "UNKNOWN":
            return self._handle_unknown(user_prompt)

        # 風險評估
        risk = self.risk_assessor.assess(user_prompt, agent_name)
        approval_role = self.risk_assessor.get_approval_role(risk)
        print(f"[Orchestrator] 風險等級: {risk.value} → {approval_role}")

        if agent_name not in self.agents:
            return f"Agent [{agent_name}] 尚未就緒。"

        agent = self.agents[agent_name]
        result = agent.run(user_prompt)

        self.dispatch_log.append({
            "prompt": user_prompt[:80],
            "agent": agent_name,
            "confidence": confidence,
            "risk": risk.value,
            "result": result[:100] if result else "N/A",
        })

        return result

    def _dispatch_sequential(self, plan: ExecutionPlan) -> str:
        """依序執行，前一步輸出作為後一步的 context"""
        results = []
        context = ""
        for step in plan.steps:
            agent_name = step.agent_name
            if agent_name not in self.agents:
                continue
            prompt = step.task
            if context:
                prompt = f"{prompt}\n\n[前置步驟結果]\n{context}"
            agent = self.agents[agent_name]
            result = agent.run(prompt)
            results.append({"agent": agent_name, "result": result})
            context = result

            risk = self.risk_assessor.assess(step.task, agent_name)
            self.dispatch_log.append({
                "prompt": step.task[:80],
                "agent": agent_name,
                "confidence": 1.0,
                "risk": risk.value,
                "result": result[:100] if result else "N/A",
            })

        return self.aggregator.aggregate(results, plan.merge_instruction, self.llm)

    def _dispatch_parallel(self, plan: ExecutionPlan) -> str:
        """使用 ThreadPoolExecutor 平行執行，然後合併"""
        results_map: Dict[str, str] = {}

        def run_step(step):
            agent_name = step.agent_name
            if agent_name not in self.agents:
                return agent_name, ""
            agent = self.agents[agent_name]
            return agent_name, agent.run(step.task)

        with ThreadPoolExecutor(max_workers=len(plan.steps)) as executor:
            futures = {executor.submit(run_step, step): step for step in plan.steps}
            for future in as_completed(futures):
                agent_name, result = future.result()
                results_map[agent_name] = result

        # 維持 plan 順序
        results = [
            {"agent": step.agent_name, "result": results_map.get(step.agent_name, "")}
            for step in plan.steps
        ]

        for step in plan.steps:
            result = results_map.get(step.agent_name, "")
            risk = self.risk_assessor.assess(step.task, step.agent_name)
            self.dispatch_log.append({
                "prompt": step.task[:80],
                "agent": step.agent_name,
                "confidence": 1.0,
                "risk": risk.value,
                "result": result[:100] if result else "N/A",
            })

        return self.aggregator.aggregate(results, plan.merge_instruction, self.llm)

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