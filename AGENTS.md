# Digital Employee Swarm — Agent Fleet Registry

## MASTER_ORCHESTRATOR
- **Role**: 中央指揮官
- **Status**: ACTIVE
- **Responsibility**: 接收使用者自然語言指令，解析意圖，派發給對應 Domain Agent
- **Risk Engine**: 自動風險評估（LOW / MEDIUM / HIGH）
- **Tech Stack**: Python, IntentClassifier
- **HITL Gate**: HIGH risk 任務強制暫停等待人工審批
- **Approval API**: POST /api/approvals/{id}/approve|reject
- **Webhook**: Slack / 通用 HTTP POST 通知審批人

---

## KM_AGENT (Knowledge Management)
- **Domain**: 知識萃取與結構化
- **Role**: 知識萃取專家（基於 Anthropic 雙層 Harness 概念）
- **Status**: ACTIVE
- **Capability**:
  - [x] 解析非結構化文件（PDF/Text/錄音轉文字）
  - [x] 生成結構化 Markdown 知識卡片
  - [x] 自動提交 Git Commit 記錄工作進度
  - [x] EPCC 工作流（Explore → Plan → Code → Commit）
- **Input**: 非結構化文件
- **Output**: 結構化知識卡片 + 向量索引 + 進度記錄
- **Trigger Keywords**: 萃取, SOP, 文件, 知識, 整理, extract, knowledge

---

## PROCESS_AGENT (Process Re-engineering)
- **Domain**: 流程優化建議
- **Role**: 流程優化顧問
- **Status**: ACTIVE
- **Capability**:
  - [x] 流程瓶頸識別與分析
  - [x] 生成 3 個層級的優化方案（保守/中庸/積極）
  - [x] ROI 預估比較表
  - [x] 新版 SOP 草稿生成
- **Dependency**: KM_AGENT（需先完成知識萃取以取得現有 SOP）
- **Trigger Keywords**: 流程, 優化, 效率, 瓶頸, process, optimize

---

## TALENT_AGENT (Talent Development)
- **Domain**: 人才發展與能力管理
- **Role**: 人才發展顧問
- **Status**: ACTIVE
- **Capability**:
  - [x] 能力差距分析（5 維度雷達圖）
  - [x] 個人化學習路徑規劃（3 Phase）
  - [x] 部門能力熱力圖
  - [x] 人才風險預警
- **Dependency**: KM_AGENT（查詢崗位知識要求）
- **Trigger Keywords**: 人才, 培訓, 能力, 學習, 評估, talent, skill

---

## DECISION_AGENT (Decision Support)
- **Domain**: 決策支援與風險分析
- **Role**: 決策支援分析師
- **Status**: ACTIVE
- **Capability**:
  - [x] 數據分析與指標追蹤
  - [x] 風險評估矩陣（3×3）
  - [x] 多方案比較表（保守/中庸/積極）
  - [x] 決策建議與條件分析
- **Trigger Keywords**: 決策, 分析, 風險, 比較, 數據, decision, risk