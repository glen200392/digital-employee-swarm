"""MCP 真實連線測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from protocols.mcp import MCPConnector, MCPResource, MCPResourceType


class TestMCPReal:
    """MCP 真實檔案系統連線測試"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # 建立測試目錄結構
        os.makedirs(os.path.join(self.tmpdir, "docs", "sops"), exist_ok=True)
        os.makedirs(os.path.join(self.tmpdir, "docs", "reports"), exist_ok=True)
        self.mcp = MCPConnector(project_root=self.tmpdir)

    def test_has_real_connections(self):
        """應有真實的檔案系統連線"""
        health = self.mcp.health_check()
        assert health["知識庫"] is True
        assert health["報告庫"] is True
        assert health["進度日誌"] is True

    def test_has_simulated_connections(self):
        """企業系統應標記為未連線"""
        health = self.mcp.health_check()
        assert health["向量資料庫"] is False
        assert health["ERP系統"] is False
        assert health["HR系統"] is False

    def test_read_empty_knowledge_base(self):
        """空知識庫讀取"""
        result = self.mcp.read("知識庫", {"keyword": ""})
        assert result["status"] == "success"
        assert result["count"] == 0

    def test_write_then_read_knowledge(self):
        """寫入後讀取知識庫"""
        self.mcp.write("知識庫", {
            "filename": "test_sop.md",
            "content": "# 測試 SOP\n\n步驟一：開始"
        })
        result = self.mcp.read("知識庫", {"keyword": "測試"})
        assert result["status"] == "success"
        assert result["count"] == 1
        assert result["data"][0]["title"] == "測試 SOP"

    def test_read_not_connected_resource(self):
        """未連線資源讀取"""
        result = self.mcp.read("ERP系統", {})
        assert result["status"] == "not_connected"

    def test_read_unknown_resource(self):
        result = self.mcp.read("不存在的資源", {})
        assert result is None

    def test_operation_log(self):
        """操作日誌記錄"""
        self.mcp.read("知識庫", {})
        self.mcp.read("ERP系統", {})
        assert len(self.mcp.operation_log) == 2

    def test_read_progress_log_empty(self):
        result = self.mcp.read("進度日誌", {})
        assert result["status"] == "success"
        assert result["count"] == 0

    def test_read_progress_log_with_data(self):
        """有資料的進度日誌"""
        log_path = os.path.join(self.tmpdir, "docs", "progress.log")
        with open(log_path, "w") as f:
            f.write("line1\nline2\nline3\n")
        result = self.mcp.read("進度日誌", {"limit": 2})
        assert result["count"] == 3
        assert len(result["data"]) == 2

    def test_get_report(self):
        report = self.mcp.get_report()
        assert "MCP Resources Report" in report
        assert "知識庫" in report
        assert "🟢" in report
        assert "🔴" in report
