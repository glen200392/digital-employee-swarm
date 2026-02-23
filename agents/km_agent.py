"""
KM Agent（知識萃取專家）
場景A：知識永生化 — 將 40 年隱性知識轉化為結構化知識資產。
採用 EPCC（Explore → Plan → Code → Commit）工作流。
"""

import os
import time
from typing import Any, Dict

from agents.base_agent import BaseAgent


class KMAgent(BaseAgent):
    """
    知識萃取 Agent：負責解析文件、萃取 SOP、生成知識卡片。

    工作流程：
    1. 接收知識萃取指令（文件/錄音/訪談紀錄）
    2. 解析內容並建立結構化大綱
    3. 生成 Markdown 知識卡片
    4. 存入 docs/sops/ 並更新進度
    """

    def __init__(self):
        super().__init__(
            name="KM_AGENT",
            role="知識萃取專家",
            description="負責將隱性知識轉化為結構化知識資產（知識卡片、SOP、向量索引）",
            trigger_keywords=["萃取", "sop", "文件", "知識", "整理",
                              "extract", "knowledge", "document"],
        )

    def _execute(self, task: str, context: Dict[str, Any]) -> str:
        """
        核心執行邏輯：解析任務指令，生成結構化知識卡片。
        """
        task_id = f"KM-{int(time.time())}"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # 分析任務意圖
        topic = self._extract_topic(task)

        # 生成知識卡片內容
        knowledge_card = self._generate_knowledge_card(
            topic=topic,
            task=task,
            timestamp=timestamp,
            context=context,
        )

        # 儲存知識卡片
        filename = self._save_knowledge_card(task_id, knowledge_card)

        return f"知識卡片已建立: {filename}"

    def _extract_topic(self, task: str) -> str:
        """從任務指令中提取主題"""
        # 移除常見的指令性前綴
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

    def _generate_knowledge_card(self, topic: str, task: str,
                                 timestamp: str,
                                 context: Dict[str, Any]) -> str:
        """
        生成結構化知識卡片。
        在真實場景中，這裡會呼叫 Claude API 進行深度解析。
        """
        # 從 context 取得上次進度
        prev_progress = context.get("last_progress", [])
        prev_info = ""
        if prev_progress:
            prev_info = (
                "\n## 延續上次進度\n"
                + "\n".join(f"- {p}" for p in prev_progress[:3])
                + "\n"
            )

        card = f"""# 知識卡片: {topic}

## 基本資訊
- **建立時間**: {timestamp}
- **來源指令**: {task}
- **狀態**: 初稿（待知識大使驗證）
- **Agent**: {self.name}
{prev_info}
## 知識摘要

### 核心流程
1. 待補充：此區域由 Agent 自動解析原始文件後填入
2. 關鍵步驟與注意事項
3. 例外處理流程

### 隱性知識要點
- 此區域需要資深知識大使補充驗證
- 特殊案例與經驗法則
- 常見陷阱與解決方案

### 相關文件
- 原始 SOP 文件連結（待補充）
- 參考資料來源

## 驗證狀態
- [ ] 知識大使已審核
- [ ] 內容準確性已確認
- [ ] 例外案例已補充
- [ ] 可供新人直接執行

## 品質指標
- **可執行性**: 待評估（目標：新人可 0 問題執行）
- **完整性**: 初稿階段
"""
        return card

    def _save_knowledge_card(self, task_id: str, content: str) -> str:
        """儲存知識卡片到 docs/sops/"""
        sops_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "sops"
        )
        os.makedirs(sops_dir, exist_ok=True)

        filename = f"docs/sops/knowledge_{task_id}.md"
        full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            filename
        )

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        return filename