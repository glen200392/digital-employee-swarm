"""
ResultAggregator — 多 Agent 結果合併器
將多個 Agent 的輸出整合為一份完整報告。
"""

from typing import Dict, List, Optional, Any


class ResultAggregator:
    """
    合併多個 Agent 的執行結果。
    有 LLM 時：使用 LLM 根據 merge_instruction 智慧合併。
    無 LLM 時：按順序拼接，加上分隔標題。
    """

    def aggregate(
        self,
        results: List[Dict],
        merge_instruction: str = "",
        llm: Optional[Any] = None,
    ) -> str:
        """
        合併多個 Agent 的輸出。

        Args:
            results: 每個元素為 {"agent": str, "result": str}
            merge_instruction: 合併指示（LLM 模式使用）
            llm: LLMProvider 實例（可選）

        Returns:
            合併後的完整報告字串
        """
        if not results:
            return ""

        if llm and llm.is_llm_available and merge_instruction:
            merged = self._aggregate_with_llm(results, merge_instruction, llm)
            if merged:
                return merged

        return self._aggregate_simple(results)

    def _aggregate_with_llm(
        self,
        results: List[Dict],
        merge_instruction: str,
        llm: Any,
    ) -> str:
        """使用 LLM 智慧合併結果"""
        try:
            sections = "\n\n".join(
                f"[{r['agent']}]\n{r['result']}" for r in results
            )
            prompt = (
                f"{merge_instruction}\n\n"
                f"以下是各 Agent 的輸出結果：\n\n{sections}"
            )
            return llm.chat(prompt)
        except Exception:
            return ""

    def _aggregate_simple(self, results: List[Dict]) -> str:
        """簡單拼接：加上分隔標題"""
        parts = []
        for r in results:
            agent = r.get("agent", "AGENT")
            result = r.get("result", "")
            parts.append(f"=== {agent} ===\n{result}")
        return "\n\n".join(parts)
