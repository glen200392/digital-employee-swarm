"""
Digital Employee Swarm System — 主入口
整合 LLM + MCP + A2A + Skill 的完整互動 CLI。
"""

import sys
import os

# 確保專案根目錄在 Python path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.router import MasterOrchestrator


def print_banner():
    """啟動 Banner"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║    🤖  Digital Employee Swarm System  v2.0                    ║
║                                                               ║
║    Anthropic Harness + Google A2A/MCP + OpenAI Swarm          ║
║    Enterprise AI Agent Fleet                                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)


def print_help():
    """指令說明"""
    print("""
  系統指令:
  ─────────────────────────────────
  status    顯示 Agent Fleet 狀態
  health    顯示健康度儀表板
  agents    顯示 Agent 能力清單
  history   顯示任務分派歷史
  llm       顯示 LLM Provider 狀態
  mcp       顯示 MCP 資源報告
  a2a       顯示 A2A 協議報告
  skills    顯示可用技能清單
  help      顯示此說明
  exit      結束系統

  互動指令（範例）:
  ─────────────────────────────────
  請幫我萃取採購SOP        → KM Agent
  優化出貨流程              → Process Agent
  評估新人能力              → Talent Agent
  分析投資風險              → Decision Agent
    """)


def main():
    """主程式入口"""
    print_banner()

    # 初始化 Orchestrator（自動初始化所有子系統）
    print("  正在初始化 Agent Fleet...")
    orchestrator = MasterOrchestrator()

    llm_status = orchestrator.llm.get_status()
    if llm_status["is_llm"]:
        print(f"  🟢 LLM Provider: {llm_status['active']}")
    else:
        print("  🟡 離線模式（無 API Key，使用模板輸出）")
        print("     設定 ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY 啟用 LLM")

    mcp_health = orchestrator.mcp.health_check()
    connected = sum(1 for v in mcp_health.values() if v)
    print(f"  📡 MCP 資源: {connected}/{len(mcp_health)} 已連線")
    print(f"  🔗 A2A Agent: {len(orchestrator.a2a.registry)} 已註冊")
    print(f"  🛠️  Skills: {len(orchestrator.skill_registry.list_all())} 個可用")
    print()
    print("  輸入 'help' 查看指令說明")
    print("  ─────────────────────────────")

    while True:
        try:
            user_input = input("\n  DTO 指令 > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  系統已關閉。")
            break

        if not user_input:
            continue

        command = user_input.lower()

        if command in ("exit", "quit", "q"):
            print("  系統已關閉。再見！")
            break
        elif command == "help":
            print_help()
        elif command == "status":
            print(orchestrator.get_status())
        elif command == "health":
            from dashboard.health_monitor import AgentHealthDashboard
            dashboard = AgentHealthDashboard(orchestrator.agents)
            print(dashboard.render())
        elif command == "agents":
            for name, agent in orchestrator.agents.items():
                status = agent.get_status()
                print(f"\n  [{name}] {status['role']}")
                print(f"    {status['description']}")
                print(f"    觸發: {', '.join(agent.trigger_keywords[:5])}")
                print(f"    LLM: {status['llm_provider']}")
        elif command == "history":
            print(orchestrator.get_dispatch_history())
        elif command == "llm":
            status = orchestrator.llm.get_status()
            print(f"\n  LLM Provider 狀態:")
            print(f"    Active: {status['active']}")
            print(f"    Available: {', '.join(status['available']) or 'None'}")
            print(f"    Mode: {'LLM' if status['is_llm'] else '離線模板'}")
        elif command == "mcp":
            print(orchestrator.mcp.get_report())
        elif command == "a2a":
            print(orchestrator.a2a.get_report())
        elif command == "skills":
            print(orchestrator.skill_registry.get_report())
        else:
            # 分派給 Agent
            result = orchestrator.dispatch(user_input)
            print(f"\n{result}")


if __name__ == "__main__":
    main()