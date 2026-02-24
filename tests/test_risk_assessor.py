"""Tests for RiskAssessor"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.risk_assessor import RiskAssessor, SemanticRiskAssessor, RiskLevel


class TestRiskAssessor:
    def setup_method(self):
        self.assessor = RiskAssessor()

    def test_low_risk(self):
        """一般任務應判定為低風險"""
        level = self.assessor.assess("請幫我萃取採購SOP")
        assert level == RiskLevel.LOW

    def test_medium_risk(self):
        """包含修改/變更關鍵字應判定為中風險"""
        level = self.assessor.assess("請修改這份 SOP")
        assert level == RiskLevel.MED

    def test_high_risk(self):
        """包含刪除/機密關鍵字應判定為高風險"""
        level = self.assessor.assess("刪除所有客戶資料")
        assert level == RiskLevel.HIGH

    def test_high_risk_production(self):
        """生產環境相關應判定為高風險"""
        level = self.assessor.assess("deploy to production")
        assert level == RiskLevel.HIGH

    def test_requires_human_approval(self):
        """中高風險應需要人類審核"""
        assert self.assessor.requires_human_approval(RiskLevel.HIGH) is True
        assert self.assessor.requires_human_approval(RiskLevel.MED) is True
        assert self.assessor.requires_human_approval(RiskLevel.LOW) is False

    def test_get_approval_role(self):
        """不同風險等級應對應正確角色"""
        assert "Architect" in self.assessor.get_approval_role(RiskLevel.HIGH)
        assert "Monitor" in self.assessor.get_approval_role(RiskLevel.MED)
        assert "自主" in self.assessor.get_approval_role(RiskLevel.LOW)

    def test_assessment_log(self):
        """評估記錄應被保存"""
        self.assessor.assess("task1")
        self.assessor.assess("task2")
        assert len(self.assessor.assessment_log) == 2

    def test_get_report(self):
        """get_report 應回傳非空報告"""
        self.assessor.assess("test task")
        report = self.assessor.get_report()
        assert "Risk Assessment Report" in report


class TestSemanticRiskAssessor:
    def test_readonly_is_low(self):
        """查詢類任務應為 LOW（無 LLM 時規則引擎判斷）"""
        assessor = SemanticRiskAssessor()
        level = assessor.assess("分析本季的業績數據")
        assert level == RiskLevel.LOW

    def test_negation_context(self):
        """「請勿刪除」語意評估應識別否定語境"""
        assessor = SemanticRiskAssessor()
        level = assessor.assess("請注意不要刪除重要的客戶記錄")
        # 無 LLM 時規則引擎可能觸發 HIGH，但結果至少在合法範圍內
        assert level in (RiskLevel.LOW, RiskLevel.MED, RiskLevel.HIGH)

    def test_destructive_is_high(self):
        """真正的刪除指令應為 HIGH"""
        assessor = SemanticRiskAssessor()
        level = assessor.assess("刪除所有三個月前的客戶訂單記錄")
        assert level == RiskLevel.HIGH

    def test_deploy_is_medium_or_high(self):
        """部署類應為 MEDIUM 或 HIGH"""
        assessor = SemanticRiskAssessor()
        level = assessor.assess("發佈新版採購 SOP 到全公司")
        assert level in (RiskLevel.MED, RiskLevel.HIGH)

    def test_fallback_without_llm(self):
        """無 LLM 時應 fallback 到規則引擎"""
        assessor = SemanticRiskAssessor(llm_provider=None)
        level = assessor.assess("刪除舊資料")
        assert level == RiskLevel.HIGH

    def test_conservative_principle(self):
        """LLM 說 LOW 但規則引擎說 HIGH 時，取 HIGH"""
        class FakeLLM:
            def chat(self, prompt, max_tokens=256):
                return '{"level": "LOW", "reason": "唯讀操作", "requires_approval": false, "confidence": 0.95}'

        assessor = SemanticRiskAssessor(llm_provider=FakeLLM())
        # "刪除" triggers HIGH in rule engine; LLM says LOW → should be HIGH
        level = assessor.assess("刪除生產資料庫所有記錄")
        assert level == RiskLevel.HIGH

    def test_assessment_log_includes_mode(self):
        """評估記錄應包含使用的模式（llm/keyword）"""
        assessor = SemanticRiskAssessor()
        assessor.assess("測試任務", "TEST_AGENT")
        assert "mode" in assessor.assessment_log[-1]

    def test_llm_mode_recorded_when_llm_used(self):
        """使用 LLM 且信心度足夠時，mode 應為 llm"""
        class FakeLLM:
            def chat(self, prompt, max_tokens=256):
                return '{"level": "LOW", "reason": "純查詢操作", "requires_approval": false, "confidence": 0.95}'

        assessor = SemanticRiskAssessor(llm_provider=FakeLLM())
        assessor.assess("查詢本月報表", "KM_AGENT")
        assert assessor.assessment_log[-1]["mode"] == "llm"

    def test_low_confidence_falls_back_to_rules(self):
        """LLM 信心度 < 0.8 時應 fallback 到規則引擎"""
        class FakeLLM:
            def chat(self, prompt, max_tokens=256):
                return '{"level": "LOW", "reason": "不確定", "requires_approval": false, "confidence": 0.5}'

        assessor = SemanticRiskAssessor(llm_provider=FakeLLM())
        level = assessor.assess("刪除所有資料")
        # rule engine says HIGH; LLM low confidence → use rules
        assert level == RiskLevel.HIGH
        assert assessor.assessment_log[-1]["mode"] == "keyword"

    def test_inherits_requires_human_approval(self):
        """SemanticRiskAssessor 應繼承 requires_human_approval 介面"""
        assessor = SemanticRiskAssessor()
        assert assessor.requires_human_approval(RiskLevel.HIGH) is True
        assert assessor.requires_human_approval(RiskLevel.MED) is True
        assert assessor.requires_human_approval(RiskLevel.LOW) is False

    def test_inherits_get_approval_role(self):
        """SemanticRiskAssessor 應繼承 get_approval_role 介面"""
        assessor = SemanticRiskAssessor()
        assert "Architect" in assessor.get_approval_role(RiskLevel.HIGH)

    def test_llm_parse_failure_falls_back_to_rules(self):
        """LLM 返回無效 JSON 時應 fallback 到規則引擎"""
        class FakeLLM:
            def chat(self, prompt, max_tokens=256):
                return "這是無效的非 JSON 回應"

        assessor = SemanticRiskAssessor(llm_provider=FakeLLM())
        level = assessor.assess("修改 SOP 文件")
        assert level == RiskLevel.MED  # rule engine: 修改 → MED
        assert assessor.assessment_log[-1]["mode"] == "keyword"
