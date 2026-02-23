"""
Agent-to-Agent Protocol (A2A)
對應 Google A2A Protocol：Agent 之間動態發現彼此能力、委派任務、協同執行。
"""

from typing import Any, Callable, Dict, List, Optional


class AgentCard:
    """
    Agent 名片：描述 Agent 的能力與端點。
    A2A 協議中，Agent 透過 AgentCard 動態發現彼此。
    """

    def __init__(self, name: str, capabilities: List[str],
                 endpoint: str = "", status: str = "ACTIVE"):
        self.name = name
        self.capabilities = capabilities
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
                 action: str, payload: Dict[str, Any]):
        self.sender = sender
        self.receiver = receiver
        self.action = action
        self.payload = payload

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "action": self.action,
            "payload": self.payload,
        }


class A2AProtocol:
    """
    Agent-to-Agent 通訊協議。

    功能：
    1. Agent 註冊與能力發現
    2. 跨 Agent 任務委派
    3. 執行結果回傳

    未來擴展：接入 Google A2A Protocol 標準實作。
    """

    def __init__(self):
        self.registry: Dict[str, AgentCard] = {}
        self.message_log: List[A2AMessage] = []

    def register_agent(self, card: AgentCard):
        """註冊 Agent 到 A2A 網路"""
        self.registry[card.name] = card
        print(f"  [A2A] Agent 已註冊: {card.name}")

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
        """
        傳送 A2A 訊息。
        目前為模擬實作；未來可接入實際的 HTTP/gRPC 通訊。
        """
        message = A2AMessage(sender, receiver, action, payload)
        self.message_log.append(message)

        if receiver not in self.registry:
            print(f"  [A2A] 目標 Agent {receiver} 不在註冊表中")
            return None

        print(f"  [A2A] {sender} → {receiver}: {action}")
        return {"status": "delivered", "message": message.to_dict()}

    def delegate_task(self, from_agent: str, capability_needed: str,
                      task_payload: Dict[str, Any]) -> Optional[Dict]:
        """
        委派任務給具備特定能力的 Agent。
        自動發現並選擇最適合的 Agent。
        """
        candidates = self.discover_agents(capability_needed)
        if not candidates:
            print(f"  [A2A] 找不到具備 '{capability_needed}' 能力的 Agent")
            return None

        target = candidates[0]
        return self.send_message(
            sender=from_agent,
            receiver=target.name,
            action="DELEGATE_TASK",
            payload=task_payload,
        )

    def get_report(self) -> str:
        """產出 A2A 通訊報告"""
        lines = ["=== A2A Protocol Report ==="]
        lines.append(f"  已註冊 Agent: {len(self.registry)}")
        for name, card in self.registry.items():
            lines.append(f"    {name}: {', '.join(card.capabilities[:3])}")
        lines.append(f"  訊息總數: {len(self.message_log)}")
        return "\n".join(lines)
