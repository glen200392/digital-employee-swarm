"""
企業級 Digital Employee Swarm 設定模組
管理所有環境變數、API Key、系統常量
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AgentConfig:
    """單一 Agent 的配置"""
    name: str
    role: str
    status: str = "ACTIVE"
    trigger_keywords: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class Settings:
    """系統全域設定"""

    # === 專案路徑 ===
    PROJECT_ROOT: str = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    DOCS_DIR: str = os.path.join(PROJECT_ROOT, "docs")
    SOPS_DIR: str = os.path.join(PROJECT_ROOT, "docs", "sops")
    PROGRESS_LOG: str = os.path.join(PROJECT_ROOT, "docs", "progress.log")
    PROGRESS_MD: str = os.path.join(PROJECT_ROOT, "PROGRESS.md")
    AGENTS_MD: str = os.path.join(PROJECT_ROOT, "AGENTS.md")

    # === 風險閾值 ===
    RISK_THRESHOLD_LOW: float = 0.3
    RISK_THRESHOLD_HIGH: float = 0.7

    # === 評估引擎 ===
    EVAL_PASS_SCORE: float = 0.7
    EVAL_MAX_RETRIES: int = 3

    # === Agent 註冊表 ===
    AGENT_REGISTRY: Dict[str, AgentConfig] = field(default_factory=lambda: {
        "KM_AGENT": AgentConfig(
            name="KM_AGENT",
            role="知識萃取專家",
            status="ACTIVE",
            trigger_keywords=["萃取", "sop", "文件", "知識", "整理", "extract", "knowledge"],
            description="負責將隱性知識轉化為結構化知識資產"
        ),
        "PROCESS_AGENT": AgentConfig(
            name="PROCESS_AGENT",
            role="流程優化顧問",
            status="ACTIVE",
            trigger_keywords=["流程", "優化", "效率", "瓶頸", "process", "optimize"],
            description="負責流程瓶頸分析與新版SOP生成"
        ),
        "TALENT_AGENT": AgentConfig(
            name="TALENT_AGENT",
            role="人才發展顧問",
            status="ACTIVE",
            trigger_keywords=["人才", "培訓", "能力", "學習", "評估", "talent", "skill"],
            description="負責能力差距分析與個人化學習路徑規劃"
        ),
        "DECISION_AGENT": AgentConfig(
            name="DECISION_AGENT",
            role="決策支援分析師",
            status="ACTIVE",
            trigger_keywords=["決策", "分析", "風險", "比較", "數據", "decision", "risk", "analyze"],
            description="負責數據分析、風險評估與多方案比較"
        ),
    })

    # === API 金鑰（從環境變數讀取）===
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")

    # === 系統版本 ===
    VERSION: str = "1.0.0"
    SYSTEM_NAME: str = "Digital Employee Swarm System"
