# 🤖 Digital Employee Swarm

> Anthropic Harness + Google A2A/MCP + OpenAI Swarm — Enterprise AI Agent Fleet

## 架構總覽

```
┌─────────────────────────────────────────────┐
│              Web Dashboard (FastAPI)         │
│        REST API + WebSocket + RBAC          │
├─────────────────────────────────────────────┤
│           Master Orchestrator               │
│    LLM-based NLU + Risk + A2A Dispatch      │
├──────────┬──────────┬──────────┬────────────┤
│ KM Agent │ Process  │ Talent   │ Decision   │
│ 知識萃取  │ 流程優化  │ 人才發展  │ 決策支援    │
├──────────┴──────────┴──────────┴────────────┤
│ Harness: LLM Provider + Skill + VectorStore │
│ Claude / GPT-4o / Gemini + Offline Fallback │
├─────────────────┬───────────────────────────┤
│   MCP Protocol  │    A2A Protocol           │
│ 外部資源標準介面   │  跨 Agent 真實委派         │
└─────────────────┴───────────────────────────┘
```

## 快速開始

### CLI 模式
```bash
git clone https://github.com/glen200392/digital-employee-swarm.git
cd digital-employee-swarm
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 設定 API Key（選填，無 Key 使用離線模板模式）
export ANTHROPIC_API_KEY=your-key

python main.py
```

### Web Dashboard 模式
```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
# 打開 http://localhost:8000
# 預設帳號: admin / admin123
```

### Docker 模式
```bash
docker compose up -d
# 打開 http://localhost:8000
```

## 系統指令

| 指令 | 說明 |
|------|------|
| `status` | Agent Fleet 狀態 |
| `health` | 健康度儀表板 |
| `agents` | Agent 能力清單 |
| `history` | 任務分派歷史 |
| `llm` | LLM Provider 狀態 |
| `mcp` | MCP 資源報告 |
| `a2a` | A2A 協議報告 |
| `skills` | 可用技能清單 |

## 技術堆疊

| 技術 | 實作 |
|------|------|
| **LLM** | Claude / GPT-4o / Gemini 統一介面 + 離線 fallback |
| **意圖分類** | LLM-based NLU + 關鍵字 fallback |
| **向量資料庫** | Qdrant in-memory（無需另外部署） |
| **MCP** | 真實檔案系統讀寫（知識庫/報告庫） |
| **A2A** | 跨 Agent 真實委派（delegate → run()） |
| **Skill** | 5 個內建技能 + 動態註冊 |
| **Web** | FastAPI + WebSocket + 暗黑風 UI |
| **RBAC** | JWT 認證 × 3 角色（admin/monitor/viewer） |
| **部署** | Dockerfile + docker-compose |

## RBAC 角色

| 角色 | 權限 |
|------|------|
| `admin` | 全部功能 |
| `monitor` | 除使用者管理外的全部功能 |
| `viewer` | 僅查看狀態/歷史 |

## 目錄結構

```
digital_employee_swarm/
├── agents/           4 個 Domain Agent
├── orchestrator/     Master Orchestrator + Intent Classifier
├── harness/          LLM + Skill + VectorStore + Eval + Risk
├── protocols/        MCP + A2A
├── dashboard/        Health Monitor
├── web/              FastAPI + RBAC + 前端 UI
│   ├── app.py
│   ├── auth.py
│   └── static/       HTML + CSS + JS
├── tests/            136 個測試
├── docs/             架構文件 + 知識庫 + 報告庫
├── Dockerfile
├── docker-compose.yml
└── main.py           CLI 入口
```

## 測試

```bash
python3 -m pytest tests/ -v
# 136 passed in 2.31s
```