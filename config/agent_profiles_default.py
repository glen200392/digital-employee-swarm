"""
4 個 Agent 的預設員工檔案設定
包含技能矩陣、SLA 目標
"""

import datetime

from harness.agent_profile import AgentProfile, SkillEntry, SkillLevel, SLATarget

_today = datetime.date.today().isoformat()

DEFAULT_PROFILES = {
    "KM_AGENT": AgentProfile(
        agent_name="KM_AGENT",
        role="知識萃取專家",
        department="知識管理部",
        sla_targets=[
            SLATarget("avg_score", 0.75, 0.0, "score"),
            SLATarget("success_rate", 0.90, 0.0, "percent"),
            SLATarget("avg_response_time", 30.0, 0.0, "seconds"),
        ],
        skill_matrix={
            "文件解析": SkillEntry("文件解析", SkillLevel.EXPERT, _today),
            "知識卡片生成": SkillEntry("知識卡片生成", SkillLevel.EXPERT, _today),
            "向量索引": SkillEntry("向量索引", SkillLevel.ADVANCED, _today),
        },
    ),
    "PROCESS_AGENT": AgentProfile(
        agent_name="PROCESS_AGENT",
        role="流程優化顧問",
        department="流程管理部",
        sla_targets=[
            SLATarget("avg_score", 0.75, 0.0, "score"),
            SLATarget("success_rate", 0.85, 0.0, "percent"),
            SLATarget("avg_response_time", 45.0, 0.0, "seconds"),
        ],
        skill_matrix={
            "流程分析": SkillEntry("流程分析", SkillLevel.EXPERT, _today),
            "瓶頸識別": SkillEntry("瓶頸識別", SkillLevel.ADVANCED, _today),
            "SOP生成": SkillEntry("SOP生成", SkillLevel.ADVANCED, _today),
            "ROI估算": SkillEntry("ROI估算", SkillLevel.INTERMEDIATE, _today),
        },
    ),
    "TALENT_AGENT": AgentProfile(
        agent_name="TALENT_AGENT",
        role="人才發展顧問",
        department="人力資源部",
        sla_targets=[
            SLATarget("avg_score", 0.75, 0.0, "score"),
            SLATarget("success_rate", 0.85, 0.0, "percent"),
            SLATarget("avg_response_time", 40.0, 0.0, "seconds"),
        ],
        skill_matrix={
            "能力評估": SkillEntry("能力評估", SkillLevel.EXPERT, _today),
            "學習路徑規劃": SkillEntry("學習路徑規劃", SkillLevel.ADVANCED, _today),
            "人才風險分析": SkillEntry("人才風險分析", SkillLevel.ADVANCED, _today),
            "績效追蹤": SkillEntry("績效追蹤", SkillLevel.INTERMEDIATE, _today),
        },
    ),
    "DECISION_AGENT": AgentProfile(
        agent_name="DECISION_AGENT",
        role="決策支援分析師",
        department="策略決策部",
        sla_targets=[
            SLATarget("avg_score", 0.80, 0.0, "score"),
            SLATarget("success_rate", 0.90, 0.0, "percent"),
            SLATarget("avg_response_time", 35.0, 0.0, "seconds"),
        ],
        skill_matrix={
            "數據分析": SkillEntry("數據分析", SkillLevel.EXPERT, _today),
            "風險評估": SkillEntry("風險評估", SkillLevel.EXPERT, _today),
            "方案比較": SkillEntry("方案比較", SkillLevel.ADVANCED, _today),
            "決策建議": SkillEntry("決策建議", SkillLevel.ADVANCED, _today),
        },
    ),
}
