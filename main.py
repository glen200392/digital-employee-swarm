"""
Digital Employee Swarm System — 主程式入口
整合架構: Harness(Git) + Orchestrator + Domain Agents + A2A + MCP

系統指令：
  status  - 顯示所有 Agent 狀態
  health  - 顯示健康度儀表板
  agents  - 顯示 Agent 能力清單
  history - 顯示任務分派歷史
  help    - 顯示指令說明
  exit    - 結束系統
"""

import sys
import os

# 確保可以 import 子模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator.router import MasterOrchestrator
from dashboard.health_monitor import AgentHealthDashboard
from harness.eval_engine import EvalEngine
from harness.risk_assessor import RiskAssessor
from config.settings import Settings


BANNER = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   Digital Employee Swarm System v{version}                ║
║                                                           ║
║   整合架構:                                               ║
║     Anthropic Harness + Google A2A/MCP + OpenAI Swarm     ║
║                                                           ║
║   Domain Agents:                                          ║
║     🧠 KM Agent      — 知識萃取專家                        ║
║     ⚙️ Process Agent  — 流程優化顧問                       ║
║     👤 Talent Agent   — 人才發展顧問                       ║
║     📊 Decision Agent — 決策支援分析師                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
╔═══════════════════════════════════════╗
║          系統指令說明                  ║
╠═══════════════════════════════════════╣
║  status   顯示所有 Agent 狀態         ║
║  health   顯示健康度儀表板            ║
║  agents   顯示 Agent 能力清單         ║
║  history  顯示任務分派歷史            ║
║  help     顯示此說明                  ║
║  exit     結束系統                    ║
╠═══════════════════════════════════════╣
║          任務指令範例                  ║
╠═══════════════════════════════════════╣
║  請幫我萃取採購SOP                    ║
║  優化出貨流程                         ║
║  評估新人能力                         ║
║  分析風險                             ║
╚═══════════════════════════════════════╝
"""


def main():
    settings = Settings()

    print(BANNER.format(version=settings.VERSION))

    # 初始化核心元件
    orchestrator = MasterOrchestrator()
    dashboard = AgentHealthDashboard(
        agents=orchestrator.agents,
        eval_engine=EvalEngine(),
        risk_assessor=orchestrator.risk_assessor,
    )

    # 確保目錄存在
    os.makedirs(settings.DOCS_DIR, exist_ok=True)
    os.makedirs(settings.SOPS_DIR, exist_ok=True)

    print("系統就緒。輸入任務指令或系統指令（輸入 'help' 查看說明）\n")

    while True:
        try:
            user_input = input("DTO 指令 > ").strip()

            if not user_input:
                continue

            cmd = user_input.lower()

            # 系統指令
            if cmd in ("exit", "quit", "q"):
                print("\n系統關閉。再見！")
                break
            elif cmd == "help":
                print(HELP_TEXT)
            elif cmd == "status":
                print(orchestrator.get_status())
            elif cmd == "health":
                print(dashboard.render())
            elif cmd == "agents":
                _show_agents(orchestrator)
            elif cmd == "history":
                print(orchestrator.get_dispatch_history())
            else:
                # 任務指令
                result = orchestrator.dispatch(user_input)
                print(f"\n{'─'*50}")
                print(f"[系統回報] {result}")
                print(f"{'─'*50}")

        except KeyboardInterrupt:
            print("\n\n強制終止。")
            break
        except Exception as e:
            print(f"\n[錯誤] 發生未預期的錯誤: {e}")


def _show_agents(orchestrator: MasterOrchestrator):
    """顯示所有 Agent 的能力清單"""
    print("\n=== Agent Fleet 能力清單 ===")
    for name, agent in orchestrator.agents.items():
        status = agent.get_status()
        icon = "🟢" if status["status"] == "IDLE" else "🔵"
        print(f"\n{icon} {name}")
        print(f"   角色: {status['role']}")
        print(f"   描述: {status['description']}")
        print(f"   觸發: {', '.join(agent.trigger_keywords[:5])}")
        print(f"   已完成任務數: {status['tasks_completed']}")


if __name__ == "__main__":
    main()