# Digital Employee Swarm System

> **數位員工管理團隊 × AI Agent Fleet 完整人機協作架構**

整合 **Anthropic Harness + Google A2A/MCP + OpenAI Swarm** 三大技術陣營的企業級 Agent 系統。

📄 **完整架構文件**：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)（含三大陣營對比、四層架構圖、六大場景、人類角色矩陣、評估框架）

## 架構概覽

```
LAYER 0：治理層（Governance）    → Harness Architect 設計護欄規則
LAYER 1：指揮層（Orchestration） → Master Orchestrator 任務分派
LAYER 2：域層  （Domain Agents） → KM / Process / Talent / Decision Agent
LAYER 3：資料層（Data & Memory） → Git Memory / MCP / A2A Protocol
```

## Agent Fleet

| Agent | 角色 | 場景 |
|-------|------|------|
| **KM Agent** | 知識萃取專家 | 40年隱性知識 → 結構化知識卡片 |
| **Process Agent** | 流程優化顧問 | 流程瓶頸分析 → 優化方案 |
| **Talent Agent** | 人才發展顧問 | 能力差距分析 → 學習路徑 |
| **Decision Agent** | 決策支援分析師 | 數據分析 → 風險矩陣 |

## 快速開始

```bash
# 1. 進入專案目錄
cd digital_employee_swarm

# 2. 執行系統
python main.py

# 3. 輸入指令
DTO 指令 > 請幫我萃取採購SOP
DTO 指令 > 優化出貨流程
DTO 指令 > 評估新人能力
DTO 指令 > 分析風險
```

## 系統指令

| 指令 | 說明 |
|------|------|
| `status` | 顯示所有 Agent 狀態 |
| `health` | 顯示健康度儀表板 |
| `agents` | 顯示 Agent 能力清單 |
| `history` | 顯示任務分派歷史 |
| `help` | 顯示指令說明 |
| `exit` | 結束系統 |

## 測試

```bash
python -m pytest tests/ -v
```

## 目錄結構

```
digital_employee_swarm/
├── main.py                      # 系統入口
├── AGENTS.md                    # Agent Fleet 註冊表
├── config/
│   └── settings.py              # 環境設定
├── harness/                     # Harness 層（Anthropic 模式）
│   ├── core.py                  # EnterpriseHarness 雙層設計
│   ├── git_memory.py            # Git-based 記憶
│   ├── eval_engine.py           # 品質評估引擎
│   └── risk_assessor.py         # 風險分級評估
├── agents/                      # Domain Agent 層
│   ├── base_agent.py            # Agent 抽象基底
│   ├── km_agent.py              # 知識萃取 Agent
│   ├── process_agent.py         # 流程優化 Agent
│   ├── talent_agent.py          # 人才發展 Agent
│   └── decision_agent.py        # 決策支援 Agent
├── orchestrator/                # 指揮層
│   ├── router.py                # Master Orchestrator
│   └── intent_classifier.py     # 意圖分類器
├── protocols/                   # 通訊協議層
│   ├── a2a.py                   # Agent-to-Agent Protocol
│   └── mcp.py                   # Model Context Protocol
├── dashboard/
│   └── health_monitor.py        # Agent 健康度儀表板
├── docs/                        # 知識庫存放區
│   ├── sops/                    # 知識卡片
│   └── reports/                 # 分析報告
└── tests/                       # 測試
```

## 核心設計原則

1. **人類定義邊界，Agent 在邊界內自主執行**
2. **每個 Agent Session 結束必須留下記憶（Git Commit）**
3. **風險分級決定人機介入比例**（LOW → 自主 / MED → 監控 / HIGH → 確認）
4. **持續迭代靠評估框架驅動**
5. **KM Agent 是所有其他 Agent 的基礎設施**