"""
Human-in-the-Loop Manager
企業級人工審批機制：HIGH risk 任務強制暫停，等待人工批准。
"""
import sqlite3
import json
import uuid
import datetime
import os
import logging
import urllib.request
import urllib.error
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    PENDING = "PENDING"              # 等待審批
    APPROVED = "APPROVED"            # 已批准
    REJECTED = "REJECTED"            # 已拒絕
    TIMEOUT = "TIMEOUT"              # 超時（預設 24 小時）
    AUTO_APPROVED = "AUTO_APPROVED"  # 自動批准（LOW risk）


class ApprovalAction(Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass
class ApprovalRequest:
    request_id: str
    agent_name: str
    task: str
    risk_level: str          # LOW / MEDIUM / HIGH
    risk_reason: str
    status: ApprovalStatus
    created_at: str
    resolved_at: Optional[str]
    resolved_by: Optional[str]
    resolution_note: Optional[str]
    webhook_sent: bool
    timeout_hours: int


class HITLManager:
    """
    Human-in-the-Loop 管理器。

    核心流程：
    1. check_and_gate(task, agent_name, risk_level, risk_reason)
       - LOW  → 直接回傳 ApprovalStatus.AUTO_APPROVED
       - MED  → 記錄 log，依設定決定是否 gate
       - HIGH → 建立 ApprovalRequest，寫入 SQLite，發送 Webhook，
                 回傳 PENDING request

    2. resolve(request_id, action, resolved_by, note)
       - 更新 SQLite 中的審批狀態
       - 回傳 ApprovalRequest

    3. get_pending_requests() → List[ApprovalRequest]
    4. get_request(request_id) → Optional[ApprovalRequest]
    5. is_approved(request_id) → bool
    6. expire_timeouts()
    """

    HITL_DB_PATH = os.getenv("HITL_DB_PATH", "./data/hitl.db")
    REQUIRE_APPROVAL_FOR_MED = os.getenv("HITL_REQUIRE_MED", "false").lower() == "true"
    TIMEOUT_HOURS = int(os.getenv("HITL_TIMEOUT_HOURS", "24"))

    def __init__(self, db_path: str = None):
        self.db_path = db_path or self.HITL_DB_PATH
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()
        self._notifier = WebhookNotifier()

    def _init_db(self):
        """建立 approval_requests 資料表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id      TEXT PRIMARY KEY,
                    agent_name      TEXT NOT NULL,
                    task            TEXT NOT NULL,
                    risk_level      TEXT NOT NULL,
                    risk_reason     TEXT NOT NULL DEFAULT '',
                    status          TEXT NOT NULL DEFAULT 'PENDING',
                    created_at      TEXT NOT NULL,
                    resolved_at     TEXT,
                    resolved_by     TEXT,
                    resolution_note TEXT,
                    webhook_sent    INTEGER NOT NULL DEFAULT 0,
                    timeout_hours   INTEGER NOT NULL DEFAULT 24
                )
            """)
            conn.commit()

    def _row_to_request(self, row) -> ApprovalRequest:
        return ApprovalRequest(
            request_id=row[0],
            agent_name=row[1],
            task=row[2],
            risk_level=row[3],
            risk_reason=row[4],
            status=ApprovalStatus(row[5]),
            created_at=row[6],
            resolved_at=row[7],
            resolved_by=row[8],
            resolution_note=row[9],
            webhook_sent=bool(row[10]),
            timeout_hours=row[11],
        )

    def check_and_gate(
        self,
        task: str,
        agent_name: str,
        risk_level: str,
        risk_reason: str = "",
    ) -> ApprovalRequest:
        """
        主要 gate 方法。
        - LOW  → 立即回傳 AUTO_APPROVED
        - MED  → 記錄；若 HITL_REQUIRE_MED=true 則同 HIGH 流程
        - HIGH → 建立 PENDING request，送 Webhook，回傳 PENDING request
        """
        risk_upper = risk_level.upper()

        if risk_upper == "LOW":
            req = ApprovalRequest(
                request_id=str(uuid.uuid4()),
                agent_name=agent_name,
                task=task,
                risk_level=risk_upper,
                risk_reason=risk_reason,
                status=ApprovalStatus.AUTO_APPROVED,
                created_at=datetime.datetime.utcnow().isoformat(),
                resolved_at=datetime.datetime.utcnow().isoformat(),
                resolved_by="system",
                resolution_note="AUTO_APPROVED: LOW risk",
                webhook_sent=False,
                timeout_hours=self.TIMEOUT_HOURS,
            )
            self._save_request(req)
            return req

        if risk_upper == "MEDIUM" and not self.REQUIRE_APPROVAL_FOR_MED:
            req = ApprovalRequest(
                request_id=str(uuid.uuid4()),
                agent_name=agent_name,
                task=task,
                risk_level=risk_upper,
                risk_reason=risk_reason,
                status=ApprovalStatus.AUTO_APPROVED,
                created_at=datetime.datetime.utcnow().isoformat(),
                resolved_at=datetime.datetime.utcnow().isoformat(),
                resolved_by="system",
                resolution_note="AUTO_APPROVED: MEDIUM risk (HITL_REQUIRE_MED=false)",
                webhook_sent=False,
                timeout_hours=self.TIMEOUT_HOURS,
            )
            self._save_request(req)
            logger.info("[HITL] MEDIUM risk task logged (no gate): %s", task[:80])
            return req

        # HIGH or (MEDIUM with REQUIRE_APPROVAL_FOR_MED=true)
        req = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent_name=agent_name,
            task=task,
            risk_level=risk_upper,
            risk_reason=risk_reason,
            status=ApprovalStatus.PENDING,
            created_at=datetime.datetime.utcnow().isoformat(),
            resolved_at=None,
            resolved_by=None,
            resolution_note=None,
            webhook_sent=False,
            timeout_hours=self.TIMEOUT_HOURS,
        )
        self._save_request(req)

        sent = self._notifier.notify_approval_required(req)
        if sent:
            self._update_webhook_sent(req.request_id)
            req.webhook_sent = True

        logger.warning(
            "[HITL] Task gated (PENDING). request_id=%s risk=%s agent=%s",
            req.request_id, risk_upper, agent_name,
        )
        return req

    def resolve(
        self,
        request_id: str,
        action: ApprovalAction,
        resolved_by: str = "system",
        note: str = "",
    ) -> ApprovalRequest:
        """批准或拒絕一個審批請求"""
        new_status = (
            ApprovalStatus.APPROVED if action == ApprovalAction.APPROVE
            else ApprovalStatus.REJECTED
        )
        now = datetime.datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE approval_requests
                SET status=?, resolved_at=?, resolved_by=?, resolution_note=?
                WHERE request_id=?
                """,
                (new_status.value, now, resolved_by, note, request_id),
            )
            conn.commit()

        req = self.get_request(request_id)
        if req:
            self._notifier.notify_resolved(req)
        return req

    def get_pending_requests(self) -> List[ApprovalRequest]:
        """取得所有待審批請求"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM approval_requests WHERE status=? ORDER BY created_at DESC",
                (ApprovalStatus.PENDING.value,),
            ).fetchall()
        return [self._row_to_request(r) for r in rows]

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """取得指定審批請求"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_request(row)

    def is_approved(self, request_id: str) -> bool:
        """檢查請求是否已批准"""
        req = self.get_request(request_id)
        if req is None:
            return False
        return req.status in (ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED)

    def expire_timeouts(self):
        """將超過 timeout_hours 的 PENDING 請求標記為 TIMEOUT"""
        now = datetime.datetime.utcnow()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT request_id, created_at, timeout_hours FROM approval_requests WHERE status=?",
                (ApprovalStatus.PENDING.value,),
            ).fetchall()
            expired = []
            for request_id, created_at, timeout_hours in rows:
                try:
                    created = datetime.datetime.fromisoformat(created_at)
                except ValueError:
                    continue
                deadline = created + datetime.timedelta(hours=timeout_hours)
                if now >= deadline:
                    expired.append(request_id)
            if expired:
                conn.executemany(
                    "UPDATE approval_requests SET status=? WHERE request_id=?",
                    [(ApprovalStatus.TIMEOUT.value, rid) for rid in expired],
                )
                conn.commit()
                logger.info("[HITL] Expired %d pending requests", len(expired))
        return expired

    def _save_request(self, req: ApprovalRequest):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO approval_requests
                    (request_id, agent_name, task, risk_level, risk_reason,
                     status, created_at, resolved_at, resolved_by,
                     resolution_note, webhook_sent, timeout_hours)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    req.request_id, req.agent_name, req.task,
                    req.risk_level, req.risk_reason, req.status.value,
                    req.created_at, req.resolved_at, req.resolved_by,
                    req.resolution_note, int(req.webhook_sent), req.timeout_hours,
                ),
            )
            conn.commit()

    def _update_webhook_sent(self, request_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE approval_requests SET webhook_sent=1 WHERE request_id=?",
                (request_id,),
            )
            conn.commit()


class WebhookNotifier:
    """
    Webhook 通知器。
    支援：
    - Slack Incoming Webhook（自動偵測 SLACK_WEBHOOK_URL）
    - 通用 HTTP POST（HITL_WEBHOOK_URL）
    """

    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
    HITL_WEBHOOK_URL = os.getenv("HITL_WEBHOOK_URL", "")

    def notify_approval_required(self, request: ApprovalRequest) -> bool:
        """
        發送審批請求通知。
        Slack 格式：含 request_id、agent、task、risk_level、審批指令說明。
        通用 POST：JSON payload。
        失敗時不拋出例外，記錄 warning 並回傳 False。
        """
        payload = {
            "event": "approval_required",
            "request_id": request.request_id,
            "agent": request.agent_name,
            "task": request.task,
            "risk_level": request.risk_level,
            "risk_reason": request.risk_reason,
            "created_at": request.created_at,
            "timeout_hours": request.timeout_hours,
            "instructions": (
                f"請至 Web Dashboard 審批此任務，或呼叫 API:\n"
                f"  POST /api/approvals/{request.request_id}/approve\n"
                f"  POST /api/approvals/{request.request_id}/reject"
            ),
        }

        slack_url = os.getenv("SLACK_WEBHOOK_URL", self.SLACK_WEBHOOK_URL)
        generic_url = os.getenv("HITL_WEBHOOK_URL", self.HITL_WEBHOOK_URL)

        sent = False
        if slack_url:
            slack_payload = {
                "text": (
                    f"⏳ *審批請求* | 風險等級: `{request.risk_level}`\n"
                    f"*Agent*: {request.agent_name}\n"
                    f"*任務*: {request.task[:200]}\n"
                    f"*原因*: {request.risk_reason}\n"
                    f"*ID*: `{request.request_id}`\n"
                    f"請至 Dashboard 或 API 審批。"
                )
            }
            sent = self._post_json(slack_url, slack_payload) or sent

        if generic_url:
            sent = self._post_json(generic_url, payload) or sent

        return sent

    def notify_resolved(self, request: ApprovalRequest) -> bool:
        """發送審批結果通知"""
        payload = {
            "event": "approval_resolved",
            "request_id": request.request_id,
            "agent": request.agent_name,
            "task": request.task,
            "status": request.status.value,
            "resolved_by": request.resolved_by,
            "resolution_note": request.resolution_note,
            "resolved_at": request.resolved_at,
        }

        slack_url = os.getenv("SLACK_WEBHOOK_URL", self.SLACK_WEBHOOK_URL)
        generic_url = os.getenv("HITL_WEBHOOK_URL", self.HITL_WEBHOOK_URL)

        icon = "✅" if request.status == ApprovalStatus.APPROVED else "❌"
        sent = False
        if slack_url:
            slack_payload = {
                "text": (
                    f"{icon} *審批完成* | {request.status.value}\n"
                    f"*Agent*: {request.agent_name}\n"
                    f"*ID*: `{request.request_id}`\n"
                    f"*審批人*: {request.resolved_by}"
                )
            }
            sent = self._post_json(slack_url, slack_payload) or sent

        if generic_url:
            sent = self._post_json(generic_url, payload) or sent

        return sent

    def _post_json(self, url: str, data: dict) -> bool:
        try:
            body = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status < 400
        except Exception as exc:
            logger.warning("[HITL] Webhook notification failed: %s", exc)
            return False
