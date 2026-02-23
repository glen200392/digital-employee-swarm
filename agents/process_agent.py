"""
Process Agent（流程優化顧問）
場景B：流程再造 — 手工 SOP → 自動化智能流程。
分析流程瓶頸、生成優化方案、產出新版 SOP。
"""

import os
import time
from typing import Any, Dict

from agents.base_agent import BaseAgent


class ProcessAgent(BaseAgent):
    """
    流程再造 Agent：負責流程瓶頸分析、優化方案生成。

    工作流程：
    1. 接收流程分析指令
    2. A2A 呼叫 KM Agent 調取現有 SOP（模擬）
    3. 分析瓶頸並生成 3 個優化方案
    4. 產出新版 SOP 草稿
    """

    def __init__(self):
        super().__init__(
            name="PROCESS_AGENT",
            role="流程優化顧問",
            description="負責流程瓶頸分析與新版SOP生成",
            trigger_keywords=["流程", "優化", "效率", "瓶頸", "reengineering",
                              "process", "optimize", "bottleneck"],
        )

    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        """分析流程並生成優化報告"""
        task_id = f"PROC-{int(time.time())}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        topic = self._extract_topic(task)

        report = self._generate_process_report(
            topic=topic,
            task=task,
            timestamp=timestamp,
        )

        filename = self._save_report(task_id, report)
        return f"流程分析報告已建立: {filename}"

    def _extract_topic(self, task: str) -> str:
        """從任務指令中提取主題"""
        prefixes = [
            "請優化", "優化", "分析", "請分析",
            "幫我優化", "請幫我優化", "改善",
        ]
        topic = task
        for prefix in prefixes:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        return topic or task

    def _generate_process_report(self, topic: str, task: str,
                                 timestamp: str) -> str:
        """生成流程分析與優化報告"""
        return f"""# 流程分析報告: {topic}

## 基本資訊
- **建立時間**: {timestamp}
- **來源指令**: {task}
- **Agent**: {self.name}
- **狀態**: 分析完成

## 現有流程分析

### 流程概覽
- 流程名稱: {topic}
- 涉及部門: 待補充（需 A2A 呼叫 KM Agent 取得現有 SOP）
- 目前週期時間: 待量化

### 瓶頸識別
1. **瓶頸 1**: 人工審核環節耗時過長
   - 影響: 增加 30% 的流程週期時間
   - 根因: 審核標準未標準化

2. **瓶頸 2**: 跨部門溝通延遲
   - 影響: 平均等待時間 2-3 個工作天
   - 根因: 缺乏自動化通知機制

3. **瓶頸 3**: 資料重複輸入
   - 影響: 每次處理增加 15 分鐘
   - 根因: 系統間缺乏整合

## 優化方案

### 方案 A：漸進式改善
- **策略**: 在現有流程中導入自動化通知與審核 Checklist
- **預估效益**: 減少 20% 週期時間
- **風險**: 低
- **實施時間**: 2 週

### 方案 B：流程重組（建議）
- **策略**: 合併審核環節、導入平行處理、建立 SOP 自動化
- **預估效益**: 減少 40% 週期時間
- **風險**: 中
- **實施時間**: 4-6 週

### 方案 C：全面數位化
- **策略**: 導入智能流程引擎，Agent 自動處理 80% 環節
- **預估效益**: 減少 60% 週期時間
- **風險**: 高
- **實施時間**: 3 個月

## ROI 預估比較表

| 方案 | 投入成本 | 預估節省 | 風險 | 回收期 |
|------|---------|---------|------|--------|
| A    | 低      | 20%     | 低   | 1 個月 |
| B    | 中      | 40%     | 中   | 3 個月 |
| C    | 高      | 60%     | 高   | 6 個月 |

## 下一步行動
1. [ ] Business Owner 選擇優化方案
2. [ ] Harness Architect 確認護欄規則
3. [ ] 產出新版 SOP 草稿
4. [ ] 實施計畫與里程碑排定
"""

    def _save_report(self, task_id: str, content: str) -> str:
        """儲存報告"""
        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "reports"
        )
        os.makedirs(reports_dir, exist_ok=True)

        filename = f"docs/reports/process_{task_id}.md"
        full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            filename
        )

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return filename
