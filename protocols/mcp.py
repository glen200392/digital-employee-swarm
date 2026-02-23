"""
Model Context Protocol (MCP)
對應 Google MCP 層：Agent 與外部系統（ERP、HR系統、資料庫、向量資料庫）
的標準化連接介面。
"""

from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class MCPResourceType(Enum):
    """MCP 資源類型"""
    ERP = "erp"
    HR_SYSTEM = "hr_system"
    VECTOR_DB = "vector_database"
    DOCUMENT_STORE = "document_store"
    EMAIL = "email"
    CALENDAR = "calendar"
    WORKSPACE = "workspace"  # M365 / Google Workspace


class MCPResource:
    """
    MCP 資源描述：定義一個外部系統資源的連接介面。
    """

    def __init__(self, name: str, resource_type: MCPResourceType,
                 endpoint: str = "", connected: bool = False,
                 description: str = ""):
        self.name = name
        self.resource_type = resource_type
        self.endpoint = endpoint
        self.connected = connected
        self.description = description

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
    MCP 連接器：管理 Agent 與外部系統的標準化介面。

    功能：
    1. 註冊與管理外部資源
    2. 提供統一的讀/寫介面
    3. 連線狀態健康檢查

    未來擴展：
    - 接入實際的 API 連接器（FastAPI MCP Server）
    - 支援 OAuth / API Key 認證
    """

    def __init__(self):
        self.resources: Dict[str, MCPResource] = {}
        self.operation_log: List[Dict] = []
        self._setup_default_resources()

    def _setup_default_resources(self):
        """註冊預設資源（模擬）"""
        defaults = [
            MCPResource(
                name="向量資料庫",
                resource_type=MCPResourceType.VECTOR_DB,
                endpoint="localhost:6333",
                connected=False,
                description="Qdrant 向量資料庫，供 RAG 問答使用",
            ),
            MCPResource(
                name="ERP系統",
                resource_type=MCPResourceType.ERP,
                endpoint="erp.internal.company.com",
                connected=False,
                description="企業 ERP 系統 API",
            ),
            MCPResource(
                name="HR系統",
                resource_type=MCPResourceType.HR_SYSTEM,
                endpoint="hr.internal.company.com",
                connected=False,
                description="人力資源管理系統 API",
            ),
            MCPResource(
                name="文件庫",
                resource_type=MCPResourceType.DOCUMENT_STORE,
                endpoint="docs.internal.company.com",
                connected=False,
                description="企業文件管理系統",
            ),
        ]
        for resource in defaults:
            self.resources[resource.name] = resource

    def register_resource(self, resource: MCPResource):
        """註冊新的外部資源"""
        self.resources[resource.name] = resource
        print(f"  [MCP] 資源已註冊: {resource}")

    def connect(self, resource_name: str) -> bool:
        """嘗試連接外部資源"""
        if resource_name not in self.resources:
            print(f"  [MCP] 未知資源: {resource_name}")
            return False

        resource = self.resources[resource_name]
        # 模擬連接（實際實作時會進行真正的 API 連接）
        resource.connected = True
        print(f"  [MCP] 已連接: {resource}")
        return True

    def read(self, resource_name: str, query: Dict[str, Any]) -> Optional[Dict]:
        """透過 MCP 讀取外部資源"""
        if resource_name not in self.resources:
            return None

        resource = self.resources[resource_name]
        self.operation_log.append({
            "operation": "READ",
            "resource": resource_name,
            "query": str(query)[:100],
        })

        # 模擬回傳
        return {
            "status": "success",
            "resource": resource_name,
            "data": f"[模擬] 來自 {resource_name} 的查詢結果",
        }

    def write(self, resource_name: str, data: Dict[str, Any]) -> bool:
        """透過 MCP 寫入外部資源"""
        if resource_name not in self.resources:
            return False

        self.operation_log.append({
            "operation": "WRITE",
            "resource": resource_name,
            "data": str(data)[:100],
        })

        return True

    def health_check(self) -> Dict[str, bool]:
        """檢查所有資源的連線狀態"""
        return {
            name: resource.connected
            for name, resource in self.resources.items()
        }

    def get_report(self) -> str:
        """產出 MCP 資源報告"""
        lines = ["=== MCP Resources Report ==="]
        for name, resource in self.resources.items():
            lines.append(f"  {resource}")
        lines.append(f"\n  操作總數: {len(self.operation_log)}")
        return "\n".join(lines)
