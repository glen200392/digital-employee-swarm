"""JWT RBAC 認證測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.auth import AuthManager, Role


class TestAuthManager:
    def setup_method(self):
        self.auth = AuthManager(secret="test-secret")

    def test_default_users(self):
        assert "admin" in self.auth.users
        assert "monitor" in self.auth.users
        assert "viewer" in self.auth.users

    def test_authenticate_ok(self):
        token = self.auth.authenticate("admin", "admin123")
        assert token is not None
        assert "." in token

    def test_authenticate_fail(self):
        token = self.auth.authenticate("admin", "wrong")
        assert token is None

    def test_authenticate_unknown_user(self):
        token = self.auth.authenticate("ghost", "pass")
        assert token is None

    def test_verify_valid_token(self):
        token = self.auth.authenticate("admin", "admin123")
        payload = self.auth.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "admin"
        assert payload["role"] == "admin"

    def test_verify_invalid_token(self):
        payload = self.auth.verify_token("invalid.token.here")
        assert payload is None

    def test_check_permission_admin(self):
        token = self.auth.authenticate("admin", "admin123")
        assert self.auth.check_permission(token, "dispatch") is True
        assert self.auth.check_permission(token, "config") is True

    def test_check_permission_viewer(self):
        token = self.auth.authenticate("viewer", "viewer123")
        assert self.auth.check_permission(token, "status") is True
        assert self.auth.check_permission(token, "dispatch") is False

    def test_check_permission_monitor(self):
        token = self.auth.authenticate("monitor", "monitor123")
        assert self.auth.check_permission(token, "dispatch") is True
        assert self.auth.check_permission(token, "config") is False

    def test_get_user_info(self):
        token = self.auth.authenticate("admin", "admin123")
        info = self.auth.get_user_info(token)
        assert info["username"] == "admin"
        assert info["role"] == "admin"

    def test_create_user(self):
        self.auth.create_user("new", "pass", Role.VIEWER, "New User")
        token = self.auth.authenticate("new", "pass")
        assert token is not None
        info = self.auth.get_user_info(token)
        assert info["role"] == "viewer"
