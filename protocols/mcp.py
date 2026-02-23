"""
Model Context Protocol (MCP) — 真實實作版
Agent 與外部系統的標準化連接介面。
包含真實的檔案系統 MCP Server + 知識庫索引。
"""

import os
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class MCPResourceType(Enum):
    """MCP 資源類型"""
    FILE_SYSTEM = "file_system"
    VECTOR_DB = "vector_database"
    ERP = "erp"
    HR_SYSTEM = "hr_system"
    DOCUMENT_STORE = "document_store"
    EMAIL = "email"
    CALENDAR = "calendar"
    WORKSPACE = "workspace"


class MCPResource:
    """MCP 資源描述"""

    def __init__(self, name: str, resource_type: MCPResourceType,
                 endpoint: str = "", connected: bool = False,
                 description: str = "",
                 handler: Optional[Callable] = None):
        self.name = name
        self.resource_type = resource_type
        self.endpoint = endpoint
        self.connected = connected
        self.description = description
        self.handler = handler  # 真實處理函數

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.resource_type.value,
            "endpoint": self.endpoint,
            "connected": self.connected,
            "description": self.description,
        }

    def __repr__(self):
        status = "🟢" if self.connected else "🔴"
        return f"{status} {self.name} ({self.resource_type.value})"


class MCPConnector:
    """
    MCP 連接器 — 真實實作版。

    真實連線：
    - FileSystem MCP：讀寫 docs/ 目錄中的檔案
    - KnowledgeBase：掃描 docs/sops/ 建立知識索引

    模擬連線（標記為未連接）：
    - ERP / HR / 向量資料庫
    """

    def __init__(self, project_root: Optional[str] = None):
        if project_root is None:
            project_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        self.project_root = project_root
        self.resources: Dict[str, MCPResource] = {}
        self.operation_log: List[Dict] = []
        self._setup_resources()

    def _setup_resources(self):
        """註冊所有資源"""
        # === 真實連線：本地檔案系統 ===
        self.resources["知識庫"] = MCPResource(
            name="知識庫",
            resource_type=MCPResourceType.FILE_SYSTEM,
            endpoint=os.path.join(self.project_root, "docs", "sops"),
            connected=True,
            description="知識卡片庫（docs/sops/）— 即時連線",
            handler=self._handle_knowledge_base,
        )
        self.resources["報告庫"] = MCPResource(
            name="報告庫",
            resource_type=MCPResourceType.FILE_SYSTEM,
            endpoint=os.path.join(self.project_root, "docs", "reports"),
            connected=True,
            description="分析報告庫（docs/reports/）— 即時連線",
            handler=self._handle_report_store,
        )
        self.resources["進度日誌"] = MCPResource(
            name="進度日誌",
            resource_type=MCPResourceType.FILE_SYSTEM,
            endpoint=os.path.join(self.project_root, "docs", "progress.log"),
            connected=True,
            description="Agent 進度日誌 — 即時連線",
            handler=self._handle_progress_log,
        )

        # === 模擬連線：企業系統 ===
        self.resources["向量資料庫"] = MCPResource(
            name="向量資料庫",
            resource_type=MCPResourceType.VECTOR_DB,
            endpoint="localhost:6333",
            connected=False,
            description="Qdrant 向量資料庫（需部署 Qdrant Server）",
        )
        self.resources["ERP系統"] = MCPResource(
            name="ERP系統",
            resource_type=MCPResourceType.ERP,
            endpoint="erp.internal.company.com",
            connected=False,
            description="企業 ERP 系統 API（需設定連線）",
        )
        self.resources["HR系統"] = MCPResource(
            name="HR系統",
            resource_type=MCPResourceType.HR_SYSTEM,
            endpoint="hr.internal.company.com",
            connected=False,
            description="人力資源管理系統 API（需設定連線）",
        )

    # === 真實 Handler 實作 ===

    def _handle_knowledge_base(self, operation: str,
                               query: Dict[str, Any]) -> Any:
        """知識庫真實讀寫"""
        sops_dir = os.path.join(self.project_root, "docs", "sops")
        os.makedirs(sops_dir, exist_ok=True)

        if operation == "READ":
            keyword = query.get("keyword", "")
            results = []
            for f in os.listdir(sops_dir):
                if not f.endswith(".md"):
                    continue
                filepath = os.path.join(sops_dir, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    if not keyword or keyword.lower() in content.lower():
                        title = content.split("\n")[0].replace("#", "").strip()
                        results.append({"file": f, "title": title, "size": len(content)})
                except Exception:
                    pass
            return {"status": "success", "count": len(results), "data": results}

        elif operation == "WRITE":
            filename = query.get("filename", "untitled.md")
            content = query.get("content", "")
            filepath = os.path.join(sops_dir, filename)
            with open(filepath, "w", encoding="utf-8") as fh:
                fh.write(content)
            return {"status": "success", "file": filepath}

        return {"status": "error", "message": f"不支援的操作: {operation}"}

    def _handle_report_store(self, operation: str,
                             query: Dict[str, Any]) -> Any:
        """報告庫真實讀寫"""
        reports_dir = os.path.join(self.project_root, "docs", "reports")
        os.makedirs(reports_dir, exist_ok=True)

        if operation == "READ":
            results = []
            for f in os.listdir(reports_dir):
                if not f.endswith(".md"):
                    continue
                filepath = os.path.join(reports_dir, f)
                try:
                    with open(filepath, "r", encoding="utf-8") as fh:
                        first_line = fh.readline().replace("#", "").strip()
                    results.append({"file": f, "title": first_line})
                except Exception:
                    pass
            return {"status": "success", "count": len(results), "data": results}

        return {"status": "error", "message": f"不支援的操作: {operation}"}

    def _handle_progress_log(self, operation: str,
                             query: Dict[str, Any]) -> Any:
        """進度日誌真實讀取"""
        log_path = os.path.join(self.project_root, "docs", "progress.log")
        if operation == "READ":
            if not os.path.exists(log_path):
                return {"status": "success", "data": [], "count": 0}
            with open(log_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
            n = query.get("limit", 20)
            return {"status": "success", "data": lines[-n:], "count": len(lines)}
        return {"status": "error", "message": f"不支援的操作: {operation}"}

    # === 統一介面 ===

    def read(self, resource_name: str, query: Dict[str, Any] = None) -> Optional[Dict]:
        """透過 MCP 讀取資源"""
        query = query or {}
        if resource_name not in self.resources:
            return None

        resource = self.resources[resource_name]
        self.operation_log.append({
            "operation": "READ", "resource": resource_name,
            "query": str(query)[:100],
        })

        # 真實 handler
        if resource.handler and resource.connected:
            return resource.handler("READ", query)

        # 模擬
        return {
            "status": "not_connected",
            "resource": resource_name,
            "message": f"{resource_name} 尚未連線。請設定連線後重試。",
        }

    def write(self, resource_name: str, data: Dict[str, Any]) -> Optional[Dict]:
        """透過 MCP 寫入資源"""
        if resource_name not in self.resources:
            return None

        resource = self.resources[resource_name]
        self.operation_log.append({
            "operation": "WRITE", "resource": resource_name,
            "data": str(data)[:100],
        })

        if resource.handler and resource.connected:
            return resource.handler("WRITE", data)

        return {"status": "not_connected", "message": f"{resource_name} 尚未連線"}

    def health_check(self) -> Dict[str, bool]:
        """檢查所有資源連線狀態"""
        return {name: r.connected for name, r in self.resources.items()}

    def get_report(self) -> str:
        """產出 MCP 資源報告"""
        lines = ["=== MCP Resources Report ==="]
        connected = sum(1 for r in self.resources.values() if r.connected)
        lines.append(f"  連線中: {connected}/{len(self.resources)}")
        lines.append("")
        for name, resource in self.resources.items():
            lines.append(f"  {resource}")
            lines.append(f"    {resource.description}")
        lines.append(f"\n  操作總數: {len(self.operation_log)}")
        return "\n".join(lines)
