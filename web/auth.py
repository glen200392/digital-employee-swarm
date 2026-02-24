"""
JWT RBAC 認證系統
支援 3 個角色：admin / monitor / viewer
"""

import hashlib
import hmac
import json
import time
import os
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum


class Role(Enum):
    ADMIN = "admin"        # Harness Architect
    MONITOR = "monitor"    # Young Talent Monitor
    VIEWER = "viewer"      # Business Owner


# 角色權限
ROLE_PERMISSIONS = {
    Role.ADMIN: {"dispatch", "status", "health", "agents", "history",
                 "llm", "mcp", "a2a", "skills", "users", "config", "approvals"},
    Role.MONITOR: {"dispatch", "status", "health", "agents", "history",
                   "llm", "mcp", "a2a", "skills", "approvals"},
    Role.VIEWER: {"status", "health", "agents", "history"},
}


@dataclass
class User:
    username: str
    role: Role
    password_hash: str
    display_name: str = ""


class AuthManager:
    """JWT 認證 + RBAC 管理"""

    def __init__(self, secret: Optional[str] = None):
        self.secret = secret or os.getenv(
            "JWT_SECRET", "digital-employee-swarm-secret-key-change-me"
        )
        self.users: Dict[str, User] = {}
        self._setup_defaults()

    def _setup_defaults(self):
        """建立預設使用者"""
        self.create_user("admin", "admin123", Role.ADMIN, "Harness Architect")
        self.create_user("monitor", "monitor123", Role.MONITOR, "Young Talent")
        self.create_user("viewer", "viewer123", Role.VIEWER, "Business Owner")

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(
            (password + self.secret).encode()
        ).hexdigest()

    def create_user(self, username: str, password: str,
                    role: Role, display_name: str = "") -> User:
        user = User(
            username=username,
            role=role,
            password_hash=self._hash_password(password),
            display_name=display_name or username,
        )
        self.users[username] = user
        return user

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """驗證帳密，回傳 JWT token"""
        user = self.users.get(username)
        if not user:
            return None
        if user.password_hash != self._hash_password(password):
            return None
        return self._create_token(user)

    def _create_token(self, user: User, expires_hours: int = 24) -> str:
        """建立簡易 JWT token"""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user.username,
            "role": user.role.value,
            "name": user.display_name,
            "exp": int(time.time()) + (expires_hours * 3600),
        }
        # 簡易 JWT 實作（base64url encode）
        import base64
        h = base64.urlsafe_b64encode(
            json.dumps(header).encode()
        ).rstrip(b"=").decode()
        p = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b"=").decode()
        msg = f"{h}.{p}"
        sig = hmac.new(
            self.secret.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()
        return f"{msg}.{sig}"

    def verify_token(self, token: str) -> Optional[Dict]:
        """驗證 JWT token，回傳 payload"""
        try:
            import base64
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # 驗證簽名
            msg = f"{parts[0]}.{parts[1]}"
            expected_sig = hmac.new(
                self.secret.encode(), msg.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(parts[2], expected_sig):
                return None

            # 解碼 payload
            padding = 4 - len(parts[1]) % 4
            payload_str = base64.urlsafe_b64decode(
                parts[1] + "=" * padding
            ).decode()
            payload = json.loads(payload_str)

            # 檢查過期
            if payload.get("exp", 0) < time.time():
                return None

            return payload
        except Exception:
            return None

    def check_permission(self, token: str, action: str) -> bool:
        """檢查 token 是否有執行指定動作的權限"""
        payload = self.verify_token(token)
        if not payload:
            return False
        role = Role(payload["role"])
        allowed = ROLE_PERMISSIONS.get(role, set())
        return action in allowed

    def get_user_info(self, token: str) -> Optional[Dict]:
        """從 token 取得使用者資訊"""
        payload = self.verify_token(token)
        if not payload:
            return None
        return {
            "username": payload["sub"],
            "role": payload["role"],
            "display_name": payload.get("name", ""),
        }
