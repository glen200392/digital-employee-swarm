"""
Agent 評估引擎
自動評分 Agent 輸出品質，驅動持續優化迴路。
"""

import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class EvalRecord:
    """單次評估記錄"""
    agent_name: str
    task: str
    score: float
    timestamp: str
    feedback: str = ""


class EvalEngine:
    """
    Agent 輸出品質評估引擎。

    評估維度：
    - 結構完整性：輸出是否包含必要的結構化元素
    - 內容豐富度：輸出長度與細節程度
    - 任務相關性：輸出是否回應了原始任務
    """

    def __init__(self, pass_score: float = 0.7):
        self.pass_score = pass_score
        self.history: List[EvalRecord] = []

    def evaluate(self, agent_name: str, task: str, output: str) -> float:
        """
        評估 Agent 輸出品質，回傳 0.0 ~ 1.0 的分數。
        """
        scores = []

        # 維度 1：結構完整性（是否有標題、段落結構）
        structure_score = self._eval_structure(output)
        scores.append(structure_score)

        # 維度 2：內容豐富度（長度與內容密度）
        content_score = self._eval_content_richness(output)
        scores.append(content_score)

        # 維度 3：任務相關性（輸出是否包含任務關鍵字）
        relevance_score = self._eval_relevance(task, output)
        scores.append(relevance_score)

        # 綜合分數
        final_score = sum(scores) / len(scores) if scores else 0.0

        # 記錄歷史
        record = EvalRecord(
            agent_name=agent_name,
            task=task,
            score=final_score,
            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self.history.append(record)

        return final_score

    def _eval_structure(self, output: str) -> float:
        """評估結構完整性"""
        score = 0.3  # 基礎分
        if "#" in output:
            score += 0.2  # 有標題
        if "-" in output or "*" in output:
            score += 0.2  # 有列表
        if len(output.split("\n")) >= 3:
            score += 0.15  # 有多行
        if ":" in output:
            score += 0.15  # 有鍵值對結構
        return min(score, 1.0)

    def _eval_content_richness(self, output: str) -> float:
        """評估內容豐富度"""
        length = len(output)
        if length >= 500:
            return 1.0
        elif length >= 200:
            return 0.8
        elif length >= 100:
            return 0.6
        elif length >= 50:
            return 0.4
        return 0.2

    def _eval_relevance(self, task: str, output: str) -> float:
        """評估任務相關性"""
        task_words = set(task.lower().replace("'", "").replace('"', "").split())
        output_lower = output.lower()

        matches = sum(1 for word in task_words if word in output_lower)
        if not task_words:
            return 0.5
        return min(matches / max(len(task_words), 1), 1.0)

    def is_passing(self, score: float) -> bool:
        """分數是否達到通過門檻"""
        return score >= self.pass_score

    def get_agent_stats(self, agent_name: str) -> Dict:
        """取得指定 Agent 的歷史評估統計"""
        agent_records = [r for r in self.history if r.agent_name == agent_name]
        if not agent_records:
            return {"count": 0, "avg_score": 0.0, "pass_rate": 0.0}

        scores = [r.score for r in agent_records]
        return {
            "count": len(agent_records),
            "avg_score": sum(scores) / len(scores),
            "pass_rate": sum(1 for s in scores if s >= self.pass_score) / len(scores),
            "latest_score": scores[-1],
        }

    def get_report(self) -> str:
        """產出評估引擎概覽報告"""
        if not self.history:
            return "尚無評估記錄。"

        agents = set(r.agent_name for r in self.history)
        lines = ["=== Eval Engine Report ==="]
        for agent in sorted(agents):
            stats = self.get_agent_stats(agent)
            lines.append(
                f"  {agent}: {stats['count']} evaluations | "
                f"Avg: {stats['avg_score']:.2f} | "
                f"Pass rate: {stats['pass_rate']:.0%}"
            )
        return "\n".join(lines)
