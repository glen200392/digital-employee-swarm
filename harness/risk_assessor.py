"""
風險評估模組
根據任務內容與 Agent 類型進行風險分級，決定人機介入比例。

風險等級：
  LOW  → Agent 自主執行
  MED  → Young Talent 監控員審核後執行
  HIGH → Harness Architect 確認
"""

import json
from enum import Enum
from typing import Dict, List, Optional, Tuple


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


# LLM 語意風險評估 Prompt
RISK_PROMPT = """
你是企業 AI 安全護欄系統的風險評估員。
請分析以下 AI Agent 即將執行的任務，評估其風險等級。

**Agent 名稱**：{agent_name}
**任務描述**：{task}

風險等級定義：
- **LOW**：查詢、分析、生成報告、萃取知識等唯讀或創建類操作，對企業資料無破壞性影響
- **MEDIUM**：修改、更新、發佈、部署等需要謹慎的操作，影響範圍有限且可回滾
- **HIGH**：刪除、覆蓋生產資料、批量變更、涉及客戶個資/薪資/合約等敏感資料的操作，後果不可逆

請嚴格按照此 JSON 格式輸出，不要有多餘文字：
{{
  "level": "LOW",
  "reason": "簡短說明（繁體中文，30字以內）",
  "requires_approval": false,
  "confidence": 0.95
}}
"""

# Risk level ordering for conservative principle (higher index = higher risk)
_RISK_ORDER = [RiskLevel.LOW, RiskLevel.MED, RiskLevel.HIGH]


def _max_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    """Return the higher risk level (conservative principle)."""
    return a if _RISK_ORDER.index(a) >= _RISK_ORDER.index(b) else b


class SemanticRiskAssessor(RiskAssessor):
    """語意化風險評估器：LLM 語意分析 + 規則引擎兜底"""

    def __init__(self, llm_provider=None):
        super().__init__()
        self._llm = llm_provider

    def assess(self, task: str, agent_name: str = "") -> RiskLevel:
        """
        評估流程：
        1. 先用 LLM 進行語意分析（有 LLM 時）
        2. LLM 信心度 < 0.8 或解析失敗時，使用規則引擎兜底
        3. 取兩者中較高的風險等級（保守原則）
        """
        mode = "keyword"
        llm_level: Optional[RiskLevel] = None
        confidence: float = 0.0

        # Step 1: LLM semantic assessment
        if self._llm is not None:
            llm_result = self._assess_with_llm(task, agent_name)
            if llm_result is not None:
                llm_level, confidence = llm_result

        # Step 2: Rule engine (always run as safety net)
        rule_level = self._assess_with_rules(task)

        # Step 3: Determine final level
        if llm_level is not None and confidence >= 0.8:
            # Use LLM result but apply conservative principle
            level = _max_risk(llm_level, rule_level)
            mode = "llm"
            reason = f"[語意] 信心度={confidence:.2f}, 規則引擎兜底"
        else:
            level = rule_level
            mode = "keyword"
            if llm_level is not None:
                reason = f"[規則] LLM 信心度不足({confidence:.2f})，使用規則引擎"
            else:
                reason = "[規則] 無 LLM，使用規則引擎"

        self.assessment_log.append({
            "task": task[:80],
            "agent": agent_name,
            "level": level.value,
            "reason": reason,
            "mode": mode,
        })

        return level

    def _assess_with_llm(self, task: str, agent_name: str) -> Optional[Tuple[RiskLevel, float]]:
        """LLM 語意評估，返回 (level, confidence)"""
        try:
            prompt = RISK_PROMPT.format(agent_name=agent_name or "未知", task=task)
            response = self._llm.chat(prompt, max_tokens=256)
            if not response:
                return None

            # Extract JSON from response (handle possible surrounding text)
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return None

            data = json.loads(response[start:end])
            raw_level = str(data.get("level", "")).upper()
            level_map = {
                "LOW": RiskLevel.LOW,
                "MEDIUM": RiskLevel.MED,
                "MED": RiskLevel.MED,
                "HIGH": RiskLevel.HIGH,
            }
            if raw_level not in level_map:
                return None

            confidence = float(data.get("confidence", 0.0))
            return level_map[raw_level], confidence

        except Exception:
            return None

    def _assess_with_rules(self, task: str) -> RiskLevel:
        """原有的關鍵字規則引擎（兜底）"""
        task_lower = task.lower()
        if any(kw in task_lower for kw in HIGH_RISK_KEYWORDS):
            return RiskLevel.HIGH
        if any(kw in task_lower for kw in MED_RISK_KEYWORDS):
            return RiskLevel.MED
        return RiskLevel.LOW
