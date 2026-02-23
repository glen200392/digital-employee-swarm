"""
KM Agent（知識萃取專家）
場景A：知識永生化 — 將 40 年隱性知識轉化為結構化知識資產。
整合 LLM 進行真實內容解析 + Skill 系統 + EPCC 工作流。
"""

import os
import time
from typing import Any, Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """你是一位資深的知識管理顧問，擅長將隱性知識轉化為結構化知識資產。
你的工作是分析使用者提供的主題或文件，產出結構化的知識卡片（Markdown 格式）。

知識卡片必須包含：
1. 核心流程步驟（編號列表）
2. 關鍵注意事項（每個步驟的要點）
3. 常見例外與處理方式
4. 相關名詞解釋
5. 品質檢核清單

輸出格式必須是 Markdown。使用繁體中文。"""


class KMAgent(BaseAgent):
    """
    知識萃取 Agent：負責解析文件、萃取 SOP、生成知識卡片。
    LLM 模式下使用真實 AI 解析，離線模式使用結構化模板。
    """

    def __init__(self):
        super().__init__(
            name="KM_AGENT",
            role="知識萃取專家",
            description="負責將隱性知識轉化為結構化知識資產（知識卡片、SOP、向量索引）",
            system_prompt=SYSTEM_PROMPT,
            trigger_keywords=["萃取", "sop", "文件", "知識", "整理",
                              "extract", "knowledge", "document"],
        )

    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        """核心執行邏輯：解析任務指令，生成結構化知識卡片。"""
        task_id = f"KM-{int(time.time())}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        topic = self._extract_topic(task)

        # 檢查知識庫中是否已有相關文件（透過 Skill）
        existing = self.skills.execute("knowledge_search", keyword=topic)
        existing_info = ""
        if existing:
            existing_info = f"\n已有 {len(existing)} 份相關知識卡片：{', '.join(e['title'] for e in existing[:3])}"

        # 恢復上下文
        prev_progress = context.get("last_progress", [])
        prev_info = ""
        if prev_progress:
            prev_info = "\n上次進度：\n" + "\n".join(f"- {p}" for p in prev_progress[:3])

        # 組裝 LLM Prompt
        llm_prompt = (
            f"請為以下主題萃取知識並建立結構化知識卡片：\n\n"
            f"主題：{topic}\n"
            f"原始指令：{task}\n"
            f"{existing_info}\n{prev_info}\n\n"
            f"請產出完整的 Markdown 知識卡片。"
        )

        # 使用 LLM 生成內容（如果可用），否則使用模板
        fallback = self._generate_template(topic, task, timestamp, context)
        knowledge_card = self.call_llm(llm_prompt, fallback=fallback)

        # 確保有標題頭
        if not knowledge_card.startswith("#"):
            knowledge_card = f"# 知識卡片: {topic}\n\n{knowledge_card}"

        # 儲存知識卡片（透過 Skill）
        sops_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "sops"
        )
        filename = f"knowledge_{task_id}.md"
        filepath = os.path.join(sops_dir, filename)
        self.skills.execute("file_write", filepath=filepath, content=knowledge_card)

        return f"知識卡片已建立: docs/sops/{filename}"

    def _extract_topic(self, task: str) -> str:
        """從任務指令中提取主題"""
        prefixes = [
            "請幫我萃取", "幫我萃取", "萃取", "請整理", "整理",
            "請幫我整理", "幫我整理", "請分析", "幫我分析",
        ]
        topic = task
        for prefix in prefixes:
            if topic.startswith(prefix):
                topic = topic[len(prefix):].strip()
                break
        return topic or task

    def _generate_template(self, topic: str, task: str,
                           timestamp: str, context: Dict[str, Any]) -> str:
        """離線模式下的結構化模板"""
        prev_progress = context.get("last_progress", [])
        prev_info = ""
        if prev_progress:
            prev_info = (
                "\n## 延續上次進度\n"
                + "\n".join(f"- {p}" for p in prev_progress[:3])
                + "\n"
            )

        return f"""# 知識卡片: {topic}

## 基本資訊
- **建立時間**: {timestamp}
- **來源指令**: {task}
- **狀態**: 初稿（待知識大使驗證）
- **Agent**: {self.name}
- **模式**: 離線模板（建議設定 LLM API Key 以取得 AI 深度解析）
{prev_info}
## 核心流程
1. 步驟一：待 LLM 解析後自動填入
2. 步驟二：關鍵操作要點
3. 步驟三：例外處理流程

## 隱性知識要點
- 此區域需要資深知識大使補充驗證
- 特殊案例與經驗法則
- 常見陷阱與解決方案

## 品質檢核
- [ ] 知識大使已審核
- [ ] 內容準確性已確認
- [ ] 例外案例已補充
- [ ] 可供新人直接執行
"""