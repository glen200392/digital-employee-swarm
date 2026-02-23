"""
Agent-to-Agent Protocol (A2A) — 真實實作版
Agent 之間動態發現彼此能力、委派任務、協同執行。
delegate_task() 真正呼叫目標 Agent 的 run()。
"""

import datetime
from typing import Any, Callable, Dict, List, Optional


class AgentCard:
    """Agent 名片"""

    def __init__(self, name: str, capabilities: List[str],
                 executor: Optional[Callable] = None,
                 endpoint: str = "", status: str = "ACTIVE"):
        self.name = name
        self.capabilities = capabilities
        self.executor = executor  # 真實的 Agent.run() 方法
        self.endpoint = endpoint
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "endpoint": self.endpoint,
            "status": self.status,
        }

    def __repr__(self):
        return f"<AgentCard: {self.name} [{', '.join(self.capabilities[:3])}]>"


class A2AMessage:
    """A2A 訊息格式"""

    def __init__(self, sender: str, receiver: str,
                 action: str, payload: Dict[str, Any],
                 result: Optional[str] = None):
        self.sender = sender
        self.receiver = receiver
        self.action = action
        self.payload = payload
        self.result = result
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "action": self.action,
            "payload": self.payload,
            "result": self.result[:100] if self.result else None,
            "timestamp": self.timestamp,
        }


class A2AProtocol:
    """
    Agent-to-Agent 通訊協議 — 真實實作版。
    delegate_task() 會真正呼叫目標 Agent 的 run() 方法。
    """

    def __init__(self):
        self.registry: Dict[str, AgentCard] = {}
        self.message_log: List[A2AMessage] = []

    def register_agent(self, card: AgentCard):
        """註冊 Agent 到 A2A 網路"""
        self.registry[card.name] = card

    def discover_agents(self, capability: str) -> List[AgentCard]:
        """根據能力需求發現可用的 Agent"""
        results = []
        for card in self.registry.values():
            if card.status == "ACTIVE" and any(
                capability.lower() in cap.lower()
                for cap in card.capabilities
            ):
                results.append(card)
        return results

    def send_message(self, sender: str, receiver: str,
                     action: str, payload: Dict[str, Any]) -> Optional[Dict]:
        """傳送 A2A 訊息"""
        if receiver not in self.registry:
            return None

        message = A2AMessage(sender, receiver, action, payload)
        self.message_log.append(message)
        print(f"  [A2A] {sender} → {receiver}: {action}")
        return {"status": "delivered", "message": message.to_dict()}

    def delegate_task(self, from_agent: str, capability_needed: str,
                      task_description: str) -> Optional[str]:
        """
        真實的跨 Agent 任務委派。
        找到具備指定能力的 Agent，呼叫其 run() 方法，回傳結果。
        """
        candidates = self.discover_agents(capability_needed)
        if not candidates:
            print(f"  [A2A] 找不到具備 '{capability_needed}' 能力的 Agent")
            return None

        target = candidates[0]
        print(f"  [A2A] {from_agent} 委派任務給 {target.name}")

        # 真實呼叫目標 Agent
        result = None
        if target.executor:
            try:
                result = target.executor(task_description)
            except Exception as e:
                result = f"A2A 呼叫失敗: {e}"

        # 記錄
        message = A2AMessage(
            sender=from_agent,
            receiver=target.name,
            action="DELEGATE_TASK",
            payload={"task": task_description},
            result=result,
        )
        self.message_log.append(message)

        return result

    def get_report(self) -> str:
        """產出 A2A 通訊報告"""
        lines = ["=== A2A Protocol Report ==="]
        lines.append(f"  已註冊 Agent: {len(self.registry)}")
        for name, card in self.registry.items():
            has_executor = "✅" if card.executor else "❌"
            lines.append(
                f"    {has_executor} {name}: {', '.join(card.capabilities[:3])}"
            )
        lines.append(f"  訊息總數: {len(self.message_log)}")

        # 最近 5 筆通訊
        if self.message_log:
            lines.append("  最近通訊:")
            for msg in self.message_log[-5:]:
                lines.append(
                    f"    [{msg.timestamp}] {msg.sender} → {msg.receiver}: {msg.action}"
                )
        return "\n".join(lines)
