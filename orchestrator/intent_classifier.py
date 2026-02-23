"""
意圖分類器
分析使用者自然語言輸入，識別應該由哪個 Domain Agent 處理。
"""

from typing import Dict, List, Optional, Tuple


class IntentClassifier:
    """
    意圖分類器：將使用者輸入映射到正確的 Domain Agent。

    分類策略：
    1. 關鍵字匹配（目前版本）
    2. 未來可接入 LLM（GPT-4o / Claude）進行語義分類
    """

    # Agent 觸發關鍵字對應表
    INTENT_MAP: Dict[str, List[str]] = {
        "KM_AGENT": [
            "萃取", "sop", "文件", "知識", "整理", "盤點",
            "extract", "knowledge", "document", "organize",
            "知識卡片", "隱性知識", "結構化",
        ],
        "PROCESS_AGENT": [
            "流程", "優化", "效率", "瓶頸", "改善",
            "process", "optimize", "bottleneck", "efficiency",
            "自動化", "再造", "重組",
        ],
        "TALENT_AGENT": [
            "人才", "培訓", "能力", "學習", "評估",
            "talent", "skill", "training", "learning", "competency",
            "職能", "圖譜", "發展", "接班",
        ],
        "DECISION_AGENT": [
            "決策", "分析", "風險", "比較", "數據",
            "decision", "risk", "analyze", "compare", "data",
            "方案", "評估", "建議",
        ],
    }

    def classify(self, prompt: str) -> Tuple[str, float]:
        """
        分類使用者意圖。
        回傳 (agent_name, confidence_score)。
        """
        prompt_lower = prompt.lower()
        scores: Dict[str, int] = {}

        for agent_name, keywords in self.INTENT_MAP.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[agent_name] = score

        if not scores:
            return "UNKNOWN", 0.0

        # 選擇匹配分數最高的 Agent
        best_agent = max(scores, key=scores.get)
        total_keywords = len(self.INTENT_MAP[best_agent])
        confidence = min(scores[best_agent] / max(total_keywords * 0.3, 1), 1.0)

        return best_agent, confidence

    def get_all_keywords(self) -> Dict[str, List[str]]:
        """取得所有 Agent 的觸發關鍵字"""
        return self.INTENT_MAP.copy()

    def suggest_keywords(self) -> str:
        """產出使用者提示"""
        suggestions = []
        for agent, keywords in self.INTENT_MAP.items():
            sample = ", ".join(keywords[:3])
            suggestions.append(f"  {agent}: {sample}")
        return "\n".join(suggestions)
