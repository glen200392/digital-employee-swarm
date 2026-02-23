"""A2A 真實跨 Agent 呼叫測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocols.a2a import A2AProtocol, AgentCard


class TestA2AReal:
    """A2A Protocol 真實任務委派測試"""

    def setup_method(self):
        self.a2a = A2AProtocol()

    def test_register_agent(self):
        card = AgentCard(name="TEST_AGENT", capabilities=["testing"])
        self.a2a.register_agent(card)
        assert "TEST_AGENT" in self.a2a.registry

    def test_discover_agents(self):
        self.a2a.register_agent(
            AgentCard(name="KM", capabilities=["知識", "萃取"])
        )
        self.a2a.register_agent(
            AgentCard(name="PROC", capabilities=["流程", "優化"])
        )
        results = self.a2a.discover_agents("知識")
        assert len(results) == 1
        assert results[0].name == "KM"

    def test_discover_no_match(self):
        results = self.a2a.discover_agents("nonexistent")
        assert len(results) == 0

    def test_send_message(self):
        self.a2a.register_agent(
            AgentCard(name="TARGET", capabilities=["test"])
        )
        result = self.a2a.send_message("SENDER", "TARGET", "TEST", {"key": "val"})
        assert result["status"] == "delivered"
        assert len(self.a2a.message_log) == 1

    def test_send_to_unknown(self):
        result = self.a2a.send_message("SENDER", "UNKNOWN", "TEST", {})
        assert result is None

    def test_delegate_task_with_executor(self):
        """真實委派：應呼叫 executor"""
        call_log = []

        def mock_run(task):
            call_log.append(task)
            return f"executed: {task}"

        self.a2a.register_agent(
            AgentCard(name="WORKER", capabilities=["work"], executor=mock_run)
        )
        result = self.a2a.delegate_task("BOSS", "work", "do something")
        assert result == "executed: do something"
        assert len(call_log) == 1
        assert call_log[0] == "do something"

    def test_delegate_task_no_executor(self):
        """無 executor 的 Agent 應回傳 None"""
        self.a2a.register_agent(
            AgentCard(name="LAZY", capabilities=["idle"])
        )
        result = self.a2a.delegate_task("BOSS", "idle", "task")
        assert result is None

    def test_delegate_no_matching_agent(self):
        result = self.a2a.delegate_task("BOSS", "nonexistent", "task")
        assert result is None

    def test_message_log_tracks_delegations(self):
        self.a2a.register_agent(
            AgentCard(name="W", capabilities=["x"], executor=lambda t: "ok")
        )
        self.a2a.delegate_task("A", "x", "task1")
        self.a2a.delegate_task("B", "x", "task2")
        assert len(self.a2a.message_log) == 2

    def test_get_report(self):
        self.a2a.register_agent(
            AgentCard(name="AG1", capabilities=["cap1"], executor=lambda t: "r")
        )
        self.a2a.delegate_task("TEST", "cap1", "task")
        report = self.a2a.get_report()
        assert "A2A Protocol Report" in report
        assert "AG1" in report
        assert "✅" in report

    def test_agent_card_without_executor_shows_x(self):
        self.a2a.register_agent(
            AgentCard(name="NO_EXEC", capabilities=["test"])
        )
        report = self.a2a.get_report()
        assert "❌" in report
