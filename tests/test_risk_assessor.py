"""Tests for RiskAssessor"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.risk_assessor import RiskAssessor, RiskLevel


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
