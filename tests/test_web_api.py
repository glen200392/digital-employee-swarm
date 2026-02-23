"""Web API 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# 只在有 FastAPI + httpx 時執行
try:
    from fastapi.testclient import TestClient
    from web.app import app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="fastapi/httpx not installed")
class TestWebAPI:
    def setup_method(self):
        self.client = TestClient(app)

    def _login(self, username="admin", password="admin123"):
        res = self.client.post("/api/login",
                               json={"username": username, "password": password})
        return res.json().get("token")

    def test_login_success(self):
        res = self.client.post("/api/login",
                               json={"username": "admin", "password": "admin123"})
        assert res.status_code == 200
        assert "token" in res.json()

    def test_login_fail(self):
        res = self.client.post("/api/login",
                               json={"username": "admin", "password": "wrong"})
        assert res.status_code == 401

    def test_status(self):
        token = self._login()
        res = self.client.get(f"/api/status?token={token}")
        assert res.status_code == 200
        data = res.json()
        assert "agents" in data
        assert "llm" in data
        assert "mcp" in data

    def test_status_no_auth(self):
        res = self.client.get("/api/status?token=invalid")
        assert res.status_code == 401

    def test_dispatch(self):
        token = self._login()
        res = self.client.post("/api/dispatch",
                               json={"prompt": "萃取SOP", "token": token})
        assert res.status_code == 200
        assert "result" in res.json()

    def test_dispatch_viewer_forbidden(self):
        token = self._login("viewer", "viewer123")
        res = self.client.post("/api/dispatch",
                               json={"prompt": "test", "token": token})
        assert res.status_code == 403

    def test_agents(self):
        token = self._login()
        res = self.client.get(f"/api/agents?token={token}")
        assert res.status_code == 200
        assert "agents" in res.json()
        assert len(res.json()["agents"]) == 4

    def test_history(self):
        token = self._login()
        res = self.client.get(f"/api/history?token={token}")
        assert res.status_code == 200

    def test_skills(self):
        token = self._login()
        res = self.client.get(f"/api/skills?token={token}")
        assert res.status_code == 200
        assert len(res.json()["skills"]) >= 5

    def test_mcp(self):
        token = self._login()
        res = self.client.get(f"/api/mcp?token={token}")
        assert res.status_code == 200
        assert "resources" in res.json()

    def test_search(self):
        res = self.client.post("/api/search",
                               json={"query": "test", "top_k": 3})
        assert res.status_code == 200
