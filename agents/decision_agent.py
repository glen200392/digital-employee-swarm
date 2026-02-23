"""
Decision Agent（決策支援分析師）
場景E：決策支援 — 直覺判斷 → 數據增強決策。
整合 LLM + Skill 系統。
"""

import os
import time
from typing import Any, Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """你是一位資深的決策支援分析師，擅長數據驅動的決策分析。
你的工作是根據使用者提供的決策需求，進行系統化分析。

分析報告必須包含：
1. 數據摘要（關鍵指標表格）
2. 風險評估矩陣（3×3：影響度 × 發生機率）
3. 多方案比較（至少 3 個方案，含優缺點、投入、預期收益）
4. 決策建議（推薦方案及其前提假設）

輸出格式必須是 Markdown。使用繁體中文。"""


class DecisionAgent(BaseAgent):
    """決策支援 Agent：數據分析、風險評估、方案比較。"""

    def __init__(self):
        super().__init__(
            name="DECISION_AGENT",
            role="決策支援分析師",
            description="負責數據分析、風險評估與多方案比較",
            system_prompt=SYSTEM_PROMPT,
            trigger_keywords=["決策", "分析", "風險", "比較", "數據",
                              "decision", "risk", "analyze", "compare"],
        )

    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        task_id = f"DEC-{int(time.time())}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        topic = self._extract_topic(task)

        # 搜尋已有的報告作為數據參考
        existing_reports = self.skills.execute("report_list")
        report_info = ""
        if existing_reports:
            report_info = f"\n已有 {len(existing_reports)} 份相關報告可參考。"

        llm_prompt = (
            f"請為以下決策需求產出完整的分析報告：\n\n"
            f"主題：{topic}\n"
            f"原始指令：{task}\n"
            f"{report_info}\n\n"
            f"請包含：數據指標、風險矩陣（3×3）、3 個方案比較、推薦建議。"
        )

        fallback = self._generate_template(topic, task, timestamp)
        report = self.call_llm(llm_prompt, fallback=fallback)

        if not report.startswith("#"):
            report = f"# 決策分析報告: {topic}\n\n{report}"

        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "reports"
        )
        filename = f"decision_{task_id}.md"
        filepath = os.path.join(reports_dir, filename)
        self.skills.execute("file_write", filepath=filepath, content=report)

        return f"決策分析報告已建立: docs/reports/{filename}"

    def _extract_topic(self, task: str) -> str:
        prefixes = ["請分析", "分析", "幫我分析", "請幫我分析", "評估", "請評估", "比較", "請比較"]
        topic = task
        for prefix in prefixes:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        return topic or task

    def _generate_template(self, topic: str, task: str, timestamp: str) -> str:
        return f"""# 決策分析報告: {topic}

## 基本資訊
- **建立時間**: {timestamp}
- **來源指令**: {task}
- **Agent**: {self.name}
- **模式**: 離線模板

## 風險評估矩陣

| 影響\\ 機率 | 低 | 中 | 高 |
|-----------|---|---|---|
| 高 | ⚠️ 中 | 🔴 高 | 🔴 極高 |
| 中 | ✅ 低 | ⚠️ 中 | 🔴 高 |
| 低 | ✅ 極低 | ✅ 低 | ⚠️ 中 |

## 方案比較

| 維度 | A 保守 | B 中庸 ⭐ | C 積極 |
|------|-------|---------|-------|
| 成本 | 低 | 中 | 高 |
| 收益 | 穩定 | 成長 | 高成長 |
| 風險 | 低 | 中 | 高 |

## 建議：方案 B
"""
