"""
Process Agent（流程優化顧問）
場景B：流程再造 — 手工 SOP → 自動化智能流程。
整合 LLM + Skill + A2A 跨 Agent 協作。
"""

import os
import time
from typing import Any, Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """你是一位資深的流程優化顧問，專精於企業流程再造(BPR)。
你的工作是分析現有流程，找出瓶頸，並提出 3 個層級的優化方案。

分析報告必須包含：
1. 現有流程瓶頸分析（至少 3 個瓶頸，含影響與根因）
2. 3 個優化方案：漸進式(低風險)、流程重組(中風險)、全面數位化(高風險)
3. ROI 預估比較表
4. 具體的下一步行動建議

輸出格式必須是 Markdown。使用繁體中文。"""


class ProcessAgent(BaseAgent):
    """流程再造 Agent：流程瓶頸分析、優化方案生成。"""

    def __init__(self):
        super().__init__(
            name="PROCESS_AGENT",
            role="流程優化顧問",
            description="負責流程瓶頸分析與新版SOP生成",
            system_prompt=SYSTEM_PROMPT,
            trigger_keywords=["流程", "優化", "效率", "瓶頸", "reengineering",
                              "process", "optimize", "bottleneck"],
        )

    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        task_id = f"PROC-{int(time.time())}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        topic = self._extract_topic(task)

        # A2A：搜尋知識庫是否有現有 SOP
        existing_sops = self.skills.execute("knowledge_search", keyword=topic)
        sop_info = ""
        if existing_sops:
            sop_info = f"\n現有 SOP {len(existing_sops)} 份，可作為分析基礎。"
            # 讀取第一份 SOP 內容作為參考
            try:
                sop_content = self.skills.execute("file_read", filepath=existing_sops[0]["path"])
                sop_info += f"\n\n現有 SOP 參考內容（{existing_sops[0]['title']}）：\n{sop_content[:500]}"
            except Exception:
                pass

        llm_prompt = (
            f"請分析以下流程並產出完整的優化報告：\n\n"
            f"流程主題：{topic}\n"
            f"原始指令：{task}\n"
            f"{sop_info}\n\n"
            f"請包含：瓶頸分析、3 個優化方案、ROI 比較表。"
        )

        fallback = self._generate_template(topic, task, timestamp)
        report = self.call_llm(llm_prompt, fallback=fallback)

        if not report.startswith("#"):
            report = f"# 流程分析報告: {topic}\n\n{report}"

        # 儲存報告
        reports_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "reports"
        )
        filename = f"process_{task_id}.md"
        filepath = os.path.join(reports_dir, filename)
        self.skills.execute("file_write", filepath=filepath, content=report)

        return f"流程分析報告已建立: docs/reports/{filename}"

    def _extract_topic(self, task: str) -> str:
        prefixes = ["請優化", "優化", "分析", "請分析", "幫我優化", "請幫我優化", "改善"]
        topic = task
        for prefix in prefixes:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        return topic or task

    def _generate_template(self, topic: str, task: str, timestamp: str) -> str:
        return f"""# 流程分析報告: {topic}

## 基本資訊
- **建立時間**: {timestamp}
- **來源指令**: {task}
- **Agent**: {self.name}
- **模式**: 離線模板

## 瓶頸識別
1. **瓶頸 1**: 人工審核環節耗時過長（+30% 週期）
2. **瓶頸 2**: 跨部門溝通延遲（2-3 工作天）
3. **瓶頸 3**: 資料重複輸入（+15 分鐘/次）

## 優化方案

| 方案 | 策略 | 效益 | 風險 | 時間 |
|------|------|------|------|------|
| A 漸進式 | 自動化通知 + Checklist | 20% | 低 | 2 週 |
| B 流程重組 ⭐ | 合併審核 + 平行處理 | 40% | 中 | 4-6 週 |
| C 全面數位化 | Agent 自動處理 80% | 60% | 高 | 3 個月 |

## 下一步
1. [ ] Business Owner 選擇方案
2. [ ] Harness Architect 確認護欄
3. [ ] 產出新版 SOP
"""
