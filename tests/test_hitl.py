"""Tests for HITLManager and related components (P0-2)"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from harness.hitl_manager import (
    HITLManager,
    WebhookNotifier,
    ApprovalStatus,
    ApprovalAction,
    ApprovalRequest,
)
from harness.core import EnterpriseHarness, SessionResult
from harness.risk_assessor import RiskLevel


# === Fixtures ===

@pytest.fixture
def hitl(tmp_path):
    db = str(tmp_path / "test_hitl.db")
    return HITLManager(db_path=db)


# === HITLManager.check_and_gate ===

class TestCheckAndGate:
    def test_low_risk_auto_approved(self, hitl):
        req = hitl.check_and_gate("查詢報告", "KM_AGENT", "LOW")
        assert req.status == ApprovalStatus.AUTO_APPROVED
        assert req.risk_level == "LOW"

    def test_medium_risk_auto_approved_by_default(self, hitl):
        req = hitl.check_and_gate("修改 SOP", "KM_AGENT", "MEDIUM")
        assert req.status == ApprovalStatus.AUTO_APPROVED
        assert req.risk_level == "MEDIUM"

    def test_medium_risk_gated_when_required(self, tmp_path):
        db = str(tmp_path / "hitl_med.db")
        manager = HITLManager(db_path=db)
        manager.REQUIRE_APPROVAL_FOR_MED = True
        req = manager.check_and_gate("修改 SOP", "KM_AGENT", "MEDIUM", "中風險關鍵字: 修改")
        assert req.status == ApprovalStatus.PENDING

    def test_high_risk_pending(self, hitl):
        req = hitl.check_and_gate("刪除所有客戶資料", "KM_AGENT", "HIGH", "高風險關鍵字: 刪除")
        assert req.status == ApprovalStatus.PENDING
        assert req.risk_level == "HIGH"
        assert req.request_id is not None

    def test_high_risk_saved_to_db(self, hitl):
        req = hitl.check_and_gate("刪除資料", "KM_AGENT", "HIGH", "高風險")
        fetched = hitl.get_request(req.request_id)
        assert fetched is not None
        assert fetched.status == ApprovalStatus.PENDING

    def test_low_risk_case_insensitive(self, hitl):
        req = hitl.check_and_gate("任務", "AGENT", "low")
        assert req.status == ApprovalStatus.AUTO_APPROVED

    def test_high_risk_case_insensitive(self, hitl):
        req = hitl.check_and_gate("刪除", "AGENT", "high")
        assert req.status == ApprovalStatus.PENDING


# === HITLManager.resolve ===

class TestResolve:
    def test_approve(self, hitl):
        req = hitl.check_and_gate("刪除", "AGENT", "HIGH")
        updated = hitl.resolve(req.request_id, ApprovalAction.APPROVE, "admin", "OK")
        assert updated.status == ApprovalStatus.APPROVED
        assert updated.resolved_by == "admin"
        assert updated.resolution_note == "OK"
        assert updated.resolved_at is not None

    def test_reject(self, hitl):
        req = hitl.check_and_gate("刪除", "AGENT", "HIGH")
        updated = hitl.resolve(req.request_id, ApprovalAction.REJECT, "admin", "Denied")
        assert updated.status == ApprovalStatus.REJECTED
        assert updated.resolved_by == "admin"

    def test_is_approved_after_approve(self, hitl):
        req = hitl.check_and_gate("刪除", "AGENT", "HIGH")
        hitl.resolve(req.request_id, ApprovalAction.APPROVE)
        assert hitl.is_approved(req.request_id) is True

    def test_is_approved_after_reject(self, hitl):
        req = hitl.check_and_gate("刪除", "AGENT", "HIGH")
        hitl.resolve(req.request_id, ApprovalAction.REJECT)
        assert hitl.is_approved(req.request_id) is False

    def test_is_approved_low_risk(self, hitl):
        req = hitl.check_and_gate("查詢", "AGENT", "LOW")
        assert hitl.is_approved(req.request_id) is True

    def test_is_approved_nonexistent(self, hitl):
        assert hitl.is_approved("nonexistent-id") is False


# === HITLManager.get_pending_requests ===

class TestGetPendingRequests:
    def test_empty(self, hitl):
        assert hitl.get_pending_requests() == []

    def test_one_pending(self, hitl):
        hitl.check_and_gate("刪除", "AGENT", "HIGH")
        pending = hitl.get_pending_requests()
        assert len(pending) == 1

    def test_resolved_not_in_pending(self, hitl):
        req = hitl.check_and_gate("刪除", "AGENT", "HIGH")
        hitl.resolve(req.request_id, ApprovalAction.APPROVE)
        assert hitl.get_pending_requests() == []

    def test_multiple_pending(self, hitl):
        hitl.check_and_gate("刪除1", "A", "HIGH")
        hitl.check_and_gate("刪除2", "B", "HIGH")
        assert len(hitl.get_pending_requests()) == 2


# === HITLManager.expire_timeouts ===

class TestExpireTimeouts:
    def test_no_expired(self, hitl):
        hitl.check_and_gate("刪除", "AGENT", "HIGH")
        expired = hitl.expire_timeouts()
        assert len(expired) == 0

    def test_expired_marked_as_timeout(self, tmp_path):
        import sqlite3
        import datetime
        db = str(tmp_path / "hitl_exp.db")
        manager = HITLManager(db_path=db)
        req = manager.check_and_gate("刪除", "AGENT", "HIGH")
        # Manually backdate created_at to 25 hours ago
        old_time = (datetime.datetime.utcnow() - datetime.timedelta(hours=25)).isoformat()
        with sqlite3.connect(db) as conn:
            conn.execute(
                "UPDATE approval_requests SET created_at=? WHERE request_id=?",
                (old_time, req.request_id),
            )
            conn.commit()
        expired = manager.expire_timeouts()
        assert req.request_id in expired
        updated = manager.get_request(req.request_id)
        assert updated.status == ApprovalStatus.TIMEOUT


# === WebhookNotifier ===

class TestWebhookNotifier:
    def test_no_url_does_not_raise(self):
        notifier = WebhookNotifier()
        # No URLs set → should return False without raising
        from harness.hitl_manager import ApprovalRequest, ApprovalStatus
        req = ApprovalRequest(
            request_id="test-id",
            agent_name="AGENT",
            task="test task",
            risk_level="HIGH",
            risk_reason="test reason",
            status=ApprovalStatus.PENDING,
            created_at="2024-01-01T00:00:00",
            resolved_at=None,
            resolved_by=None,
            resolution_note=None,
            webhook_sent=False,
            timeout_hours=24,
        )
        result = notifier.notify_approval_required(req)
        assert result is False

    def test_notify_resolved_no_url(self):
        notifier = WebhookNotifier()
        from harness.hitl_manager import ApprovalRequest, ApprovalStatus
        req = ApprovalRequest(
            request_id="test-id",
            agent_name="AGENT",
            task="test task",
            risk_level="HIGH",
            risk_reason="",
            status=ApprovalStatus.APPROVED,
            created_at="2024-01-01T00:00:00",
            resolved_at="2024-01-01T01:00:00",
            resolved_by="admin",
            resolution_note="OK",
            webhook_sent=True,
            timeout_hours=24,
        )
        result = notifier.notify_resolved(req)
        assert result is False

    def test_invalid_url_does_not_raise(self, tmp_path):
        db = str(tmp_path / "hitl_wh.db")
        os.environ["HITL_WEBHOOK_URL"] = "http://localhost:19999/nonexistent"
        try:
            manager = HITLManager(db_path=db)
            req = manager.check_and_gate("刪除", "AGENT", "HIGH")
            # Should not raise despite webhook failure
            assert req.status == ApprovalStatus.PENDING
        finally:
            del os.environ["HITL_WEBHOOK_URL"]


# === EnterpriseHarness HITL integration ===

class TestEnterpriseHarnessHITL:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        db_path = os.path.join(self.tmp, "hitl.db")
        self.harness = EnterpriseHarness()
        self.harness.hitl = HITLManager(db_path=db_path)

    def test_low_risk_executes(self):
        result = self.harness.run_epcc_cycle("KM_AGENT", "請幫我萃取採購SOP")
        assert result.success is True
        assert result.risk_level == RiskLevel.LOW

    def test_high_risk_returns_pending(self):
        result = self.harness.run_epcc_cycle("KM_AGENT", "刪除所有客戶資料")
        assert result.success is False
        assert "PENDING" in result.task_id
        assert "審批" in result.output
        assert result.risk_level == RiskLevel.HIGH

    def test_high_risk_not_executed(self):
        executed = []
        def mock_executor(task, ctx):
            executed.append(task)
            return "done"
        result = self.harness.run_epcc_cycle("KM_AGENT", "刪除生產資料庫", executor_fn=mock_executor)
        assert result.success is False
        assert len(executed) == 0  # executor should NOT have been called

    def test_pending_result_contains_request_id(self):
        result = self.harness.run_epcc_cycle("KM_AGENT", "刪除所有客戶資料")
        assert "審批 ID:" in result.output


# === FastAPI Approval API ===

try:
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi/httpx not installed")
class TestApprovalAPI:
    def setup_method(self):
        from web.app import app, hitl, auth
        self.client = TestClient(app)
        self.hitl = hitl
        self.auth = auth
        self._admin_token = self.auth.authenticate("admin", "admin123")
        self._viewer_token = self.auth.authenticate("viewer", "viewer123")

    def test_get_pending_no_auth(self):
        res = self.client.get("/api/approvals/pending?token=invalid")
        assert res.status_code == 401

    def test_get_pending_viewer_forbidden(self):
        res = self.client.get(f"/api/approvals/pending?token={self._viewer_token}")
        assert res.status_code == 403

    def test_get_pending_empty(self):
        res = self.client.get(f"/api/approvals/pending?token={self._admin_token}")
        assert res.status_code == 200
        # Should have "requests" key
        assert "requests" in res.json()

    def test_get_nonexistent_request(self):
        res = self.client.get(f"/api/approvals/nonexistent-id?token={self._admin_token}")
        assert res.status_code == 404

    def test_approve_request(self, tmp_path):
        # Create a PENDING request directly
        db = str(tmp_path / "hitl_api.db")
        manager = HITLManager(db_path=db)
        req = manager.check_and_gate("刪除生產資料", "KM_AGENT", "HIGH", "高風險")

        # Swap hitl in app module
        import web.app as web_app
        original = web_app.hitl
        web_app.hitl = manager
        try:
            res = self.client.post(
                f"/api/approvals/{req.request_id}/approve",
                json={"token": self._admin_token, "resolved_by": "admin", "note": "OK"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "APPROVED"
            assert data["resolved_by"] == "admin"
        finally:
            web_app.hitl = original

    def test_reject_request(self, tmp_path):
        db = str(tmp_path / "hitl_api2.db")
        manager = HITLManager(db_path=db)
        req = manager.check_and_gate("刪除生產資料", "KM_AGENT", "HIGH", "高風險")

        import web.app as web_app
        original = web_app.hitl
        web_app.hitl = manager
        try:
            res = self.client.post(
                f"/api/approvals/{req.request_id}/reject",
                json={"token": self._admin_token, "resolved_by": "admin", "note": "Denied"},
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "REJECTED"
        finally:
            web_app.hitl = original

    def test_expire_endpoint(self):
        res = self.client.post(f"/api/approvals/expire?token={self._admin_token}")
        assert res.status_code == 200
        assert "expired_count" in res.json()
