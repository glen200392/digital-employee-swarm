"""
風險評估模組
根據任務內容與 Agent 類型進行風險分級，決定人機介入比例。

風險等級：
  LOW  → Agent 自主執行
  MED  → Young Talent 監控員審核後執行
  HIGH → Harness Architect 確認
"""

from enum import Enum
from typing import Dict, List


class RiskLevel(Enum):
    LOW = "LOW"
    MED = "MEDIUM"
    HIGH = "HIGH"


# 高風險關鍵字
HIGH_RISK_KEYWORDS = [
    "刪除", "delete", "移除", "remove",
    "覆蓋", "overwrite",
    "全部", "all",
    "生產", "production", "prod",
    "客戶資料", "customer data",
    "薪資", "salary", "payroll",
    "合約", "contract",
    "機密", "confidential",
]

# 中風險關鍵字
MED_RISK_KEYWORDS = [
    "修改", "modify", "update", "編輯", "edit",
    "變更", "change",
    "批次", "batch",
    "發佈", "publish", "deploy",
    "通知", "notify",
    "流程變更", "process change",
]


class RiskAssessor:
    """
    風險分級評估器。
    對應參考架構的「風險評估引擎」：
      LOW  → Agent 自主執行
      MED  → Young Talent 審核後執行
      HIGH → Harness Architect 確認
    """

    def __init__(self):
        self.assessment_log: List[Dict] = []

    def assess(self, task: str, agent_name: str = "") -> RiskLevel:
        """
        評估任務的風險等級。
        """
        task_lower = task.lower()

        # 檢查高風險
        high_matches = [kw for kw in HIGH_RISK_KEYWORDS if kw in task_lower]
        if high_matches:
            level = RiskLevel.HIGH
            reason = f"高風險關鍵字: {', '.join(high_matches[:3])}"
        else:
            # 檢查中風險
            med_matches = [kw for kw in MED_RISK_KEYWORDS if kw in task_lower]
            if med_matches:
                level = RiskLevel.MED
                reason = f"中風險關鍵字: {', '.join(med_matches[:3])}"
            else:
                level = RiskLevel.LOW
                reason = "未偵測到風險關鍵字"

        # 記錄
        self.assessment_log.append({
            "task": task[:80],
            "agent": agent_name,
            "level": level.value,
            "reason": reason,
        })

        return level

    def requires_human_approval(self, level: RiskLevel) -> bool:
        """判斷是否需要人類確認"""
        return level in (RiskLevel.MED, RiskLevel.HIGH)

    def get_approval_role(self, level: RiskLevel) -> str:
        """根據風險等級回傳應審核的人類角色"""
        mapping = {
            RiskLevel.LOW: "Agent 自主執行",
            RiskLevel.MED: "Young Talent Monitor（監控員）",
            RiskLevel.HIGH: "Harness Architect（架構師）",
        }
        return mapping.get(level, "Unknown")

    def get_report(self) -> str:
        """產出風險評估歷史報告"""
        if not self.assessment_log:
            return "尚無風險評估記錄。"

        lines = ["=== Risk Assessment Report ==="]
        for entry in self.assessment_log[-10:]:
            lines.append(
                f"  [{entry['level']}] {entry['agent']}: "
                f"{entry['task'][:50]} — {entry['reason']}"
            )
        return "\n".join(lines)
