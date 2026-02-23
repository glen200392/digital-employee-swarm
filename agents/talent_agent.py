"""
Talent Agent（人才發展顧問）
場景C：人才發展 — 靜態職能 → 動態能力圖譜。
整合 LLM + Skill 系統。
"""

import os
import time
from typing import Any, Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """你是一位資深的人才發展顧問，專精於能力差距分析與學習路徑規劃。
你的工作是根據崗位需求，分析能力差距並規劃個人化學習路徑。

分析報告必須包含：
1. 能力差距分析表（至少 5 個維度，含要求等級/目前等級/差距）
2. 個人化學習路徑（分 3 個 Phase，含具體時程和資源）
3. 部門能力熱力圖（文字式呈現）
4. 人才風險預警

輸出格式必須是 Markdown。使用繁體中文。"""


class TalentAgent(BaseAgent):
    """人才發展 Agent：能力差距分析、學習路徑規劃。"""

    def __init__(self):
        super().__init__(
            name="TALENT_AGENT",
            role="人才發展顧問",
            description="負責能力差距分析與個人化學習路徑規劃",
            system_prompt=SYSTEM_PROMPT,
            trigger_keywords=["人才", "培訓", "能力", "學習", "評估",
                              "talent", "skill", "training", "competency"],
        )

    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        task_id = f"TAL-{int(time.time())}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        topic = self._extract_topic(task)

        llm_prompt = (
            f"請為以下需求產出完整的人才發展分析報告：\n\n"
            f"主題：{topic}\n"
            f"原始指令：{task}\n\n"
            f"請包含：能力差距分析（5維度表格）、3-Phase 學習路徑、能力熱力圖、風險預警。"
        )

        fallback = self._generate_template(topic, task, timestamp)
        report = self.call_llm(llm_prompt, fallback=fallback)

        if not report.startswith("#"):
            report = f"# 人才發展分析報告: {topic}\n\n{report}"

        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "reports"
        )
        filename = f"talent_{task_id}.md"
        filepath = os.path.join(reports_dir, filename)
        self.skills.execute("file_write", filepath=filepath, content=report)

        return f"人才分析報告已建立: docs/reports/{filename}"

    def _extract_topic(self, task: str) -> str:
        prefixes = ["請評估", "評估", "分析", "請分析", "幫我評估", "請幫我評估", "培訓"]
        topic = task
        for prefix in prefixes:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        return topic or task

    def _generate_template(self, topic: str, task: str, timestamp: str) -> str:
        return f"""# 人才發展分析報告: {topic}

## 基本資訊
- **建立時間**: {timestamp}
- **來源指令**: {task}
- **Agent**: {self.name}
- **模式**: 離線模板

## 能力差距分析

| 能力維度 | 要求 | 目前 | 差距 |
|---------|------|------|------|
| 專業知識 | 4/5 | 3/5 | -1 |
| 流程執行 | 4/5 | 4/5 | 0 |
| 問題解決 | 5/5 | 3/5 | -2 |
| 數位工具 | 3/5 | 2/5 | -1 |
| 跨部門協作 | 4/5 | 3/5 | -1 |

## 學習路徑
- **Phase 1**（第1-2週）：問題解決強化
- **Phase 2**（第3-4週）：專業知識深化
- **Phase 3**（第5-6週）：數位工具 + 協作

## 人才風險
- 🔴 問題解決能力差距最大
- ⚠️ 數位工具需提升
"""
