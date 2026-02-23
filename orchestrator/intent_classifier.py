"""
意圖分類器 — LLM-based + 關鍵字 fallback
有 LLM 時使用 AI 分析意圖和信心度，無 LLM 時 fallback 到關鍵字匹配。
"""

import json
from typing import Dict, List, Optional, Tuple


# Agent 關鍵字定義
AGENT_KEYWORDS: Dict[str, List[str]] = {
    "KM_AGENT": ["萃取", "sop", "文件", "知識", "整理",
                  "extract", "knowledge", "document"],
    "PROCESS_AGENT": ["流程", "優化", "效率", "瓶頸",
                      "process", "optimize", "bottleneck", "reengineering"],
    "TALENT_AGENT": ["人才", "培訓", "能力", "學習", "評估",
                     "talent", "skill", "training", "competency"],
    "DECISION_AGENT": ["決策", "分析", "風險", "比較", "數據",
                       "decision", "risk", "analyze", "compare"],
}

LLM_CLASSIFY_PROMPT = """你是一個意圖分類器。根據使用者的指令，判斷應該由哪個 Agent 處理。

可用的 Agent：
1. KM_AGENT — 知識萃取專家：處理知識萃取、SOP 整理、文件分析
2. PROCESS_AGENT — 流程優化顧問：處理流程分析、效率優化、瓶頸識別
3. TALENT_AGENT — 人才發展顧問：處理能力評估、培訓規劃、學習路徑
4. DECISION_AGENT — 決策支援分析師：處理數據分析、風險評估、方案比較

請回傳 JSON 格式：
{"agent": "AGENT_NAME", "confidence": 0.0-1.0, "reason": "簡短說明"}

如果不確定，回傳：
{"agent": "UNKNOWN", "confidence": 0.0, "reason": "無法判定"}

使用者指令："""


class IntentClassifier:
    """
    意圖分類器：LLM-based + 關鍵字 fallback。
    """

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    @property
    def llm(self):
        if self._llm is None:
            try:
                from harness.llm_provider import LLMProvider
                self._llm = LLMProvider()
            except Exception:
                pass
        return self._llm

    def classify(self, prompt: str) -> Tuple[str, float]:
        """
        分類使用者意圖。
        有 LLM 時用 AI 分析，否則 fallback 到關鍵字匹配。
        """
        # 嘗試 LLM 分類
        if self.llm and self.llm.is_llm_available:
            result = self._classify_with_llm(prompt)
            if result:
                return result

        # Fallback: 關鍵字匹配
        return self._classify_with_keywords(prompt)

    def _classify_with_llm(self, prompt: str) -> Optional[Tuple[str, float]]:
        """使用 LLM 進行意圖分類"""
        try:
            full_prompt = LLM_CLASSIFY_PROMPT + prompt
            response = self.llm.chat(full_prompt)
            if not response:
                return None

            # 嘗試從回應中解析 JSON
            # 處理可能包含 markdown code block 的情況
            text = response.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            agent = data.get("agent", "UNKNOWN")
            confidence = float(data.get("confidence", 0.0))

            # 驗證 agent name
            valid_agents = list(AGENT_KEYWORDS.keys()) + ["UNKNOWN"]
            if agent not in valid_agents:
                return None

            return (agent, confidence)

        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None

    def _classify_with_keywords(self, prompt: str) -> Tuple[str, float]:
        """關鍵字匹配分類"""
        prompt_lower = prompt.lower()
        scores: Dict[str, int] = {}

        for agent_name, keywords in AGENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[agent_name] = score

        if not scores:
            return ("UNKNOWN", 0.0)

        best_agent = max(scores, key=scores.get)
        total_keywords = len(AGENT_KEYWORDS[best_agent])
        confidence = min(scores[best_agent] / total_keywords, 1.0)
        return (best_agent, confidence)

    def suggest_keywords(self) -> str:
        """建議使用者的關鍵字"""
        lines = []
        for agent, keywords in AGENT_KEYWORDS.items():
            lines.append(f"  {agent}: {', '.join(keywords[:4])}")
        return "\n".join(lines)

    @property
    def mode(self) -> str:
        if self.llm and self.llm.is_llm_available:
            return "LLM-based NLU"
        return "Keyword Matching"
