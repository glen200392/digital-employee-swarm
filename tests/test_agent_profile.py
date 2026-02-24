"""AgentProfile 系統測試"""
import os
import sys
import tempfile
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from harness.agent_profile import (
    AgentProfile,
    AgentProfileStore,
    CostRecord,
    PerformanceSnapshot,
    SkillEntry,
    SkillLevel,
    SLATarget,
)
from config.agent_profiles_default import DEFAULT_PROFILES


class TestAgentProfile:
    def setup_method(self):
        self.profile = AgentProfile(
            agent_name="TEST_AGENT",
            role="測試角色",
            department="測試部",
            sla_targets=[
                SLATarget("avg_score", 0.75, 0.0, "score"),
                SLATarget("success_rate", 0.80, 0.0, "percent"),
                SLATarget("avg_response_time", 30.0, 0.0, "seconds"),
            ],
        )

    def test_create_profile(self):
        assert self.profile.agent_name == "TEST_AGENT"
        assert self.profile.role == "測試角色"
        assert self.profile.department == "測試部"
        assert self.profile.total_tasks_completed == 0
        assert self.profile.total_tokens_used == 0
        assert self.profile.hired_date == datetime.date.today().isoformat()

    def test_record_task_updates_stats(self):
        self.profile.record_task(score=0.8, duration_sec=10.0, tokens=100)
        assert self.profile.total_tasks_completed == 1
        assert self.profile.total_tokens_used == 100
        snapshot = self.profile.get_today_snapshot()
        assert snapshot.tasks_completed == 1
        assert snapshot.avg_score == pytest.approx(0.8)
        assert snapshot.avg_response_time_sec == pytest.approx(10.0)
        assert snapshot.tokens_used == 100

    def test_record_multiple_tasks(self):
        self.profile.record_task(score=1.0, duration_sec=5.0, tokens=50)
        self.profile.record_task(score=0.5, duration_sec=15.0, tokens=150)
        assert self.profile.total_tasks_completed == 2
        snapshot = self.profile.get_today_snapshot()
        assert snapshot.avg_score == pytest.approx(0.75)
        assert snapshot.avg_response_time_sec == pytest.approx(10.0)

    def test_sla_compliance_calculation(self):
        # Before any tasks: all current_value=0.0, not meeting score/percent SLAs
        # avg_response_time: 0.0 <= 30.0 → not meeting (current_value=0 means no data yet)
        compliance = self.profile.calculate_sla_compliance()
        # All SLA current_values are 0.0 initially
        # avg_score: 0.0 >= 0.75 → False
        # success_rate: 0.0 >= 0.80 → False
        # avg_response_time: 0.0 <= 30.0 → False (current_value=0, is_meeting_sla is False when 0)
        assert compliance == pytest.approx(0.0)

        # Record a good task → should improve compliance
        self.profile.record_task(score=0.9, duration_sec=20.0)
        compliance = self.profile.calculate_sla_compliance()
        # avg_score: 0.9 >= 0.75 → True
        # success_rate: 1.0 >= 0.80 → True
        # avg_response_time: 20.0 <= 30.0 → True
        assert compliance == pytest.approx(1.0)

    def test_sla_not_meeting(self):
        self.profile.record_task(score=0.5, duration_sec=50.0)
        # avg_score: 0.5 >= 0.75 → False
        # success_rate: 1.0 >= 0.80 → True  (score>=0.5 counts as success)
        # avg_response_time: 50.0 <= 30.0 → False
        compliance = self.profile.calculate_sla_compliance()
        assert compliance == pytest.approx(1 / 3)

    def test_performance_trend(self):
        # Initially empty
        assert self.profile.get_performance_trend(7) == []

        # After adding history manually
        snap = PerformanceSnapshot("2024-01-01", 5, 0.8, 0.9, 12.0, 500)
        self.profile.performance_history.append(snap)
        trend = self.profile.get_performance_trend(7)
        assert len(trend) == 1
        assert trend[0].date == "2024-01-01"

    def test_update_skill(self):
        self.profile.update_skill("Python", SkillLevel.EXPERT)
        assert "Python" in self.profile.skill_matrix
        assert self.profile.skill_matrix["Python"].level == SkillLevel.EXPERT
        assert self.profile.skill_matrix["Python"].usage_count == 1

        self.profile.update_skill("Python", SkillLevel.EXPERT)
        assert self.profile.skill_matrix["Python"].usage_count == 2

    def test_to_dict(self):
        self.profile.record_task(score=0.8, duration_sec=10.0, tokens=100)
        d = self.profile.to_dict()
        assert d["agent_name"] == "TEST_AGENT"
        assert "skill_matrix" in d
        assert "sla_targets" in d
        assert "performance_history" in d
        assert "today_snapshot" in d
        assert d["total_tasks_completed"] == 1
        assert d["total_tokens_used"] == 100

    def test_no_sla_targets(self):
        profile = AgentProfile("EMPTY", "r", "d")
        assert profile.calculate_sla_compliance() == 1.0


class TestAgentProfileStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_profiles.db")
        self.store = AgentProfileStore(db_path=self.db_path)

    def _make_profile(self, name="AGENT_A"):
        return AgentProfile(
            agent_name=name,
            role="測試",
            department="部門",
            sla_targets=[SLATarget("avg_score", 0.7, 0.0, "score")],
            skill_matrix={"技能A": SkillEntry("技能A", SkillLevel.ADVANCED, "2024-01-01")},
        )

    def test_persistence_across_sessions(self):
        profile = self._make_profile()
        profile.record_task(score=0.9, duration_sec=5.0, tokens=200)
        self.store.save_profile(profile)

        # New store instance (simulates new session)
        store2 = AgentProfileStore(db_path=self.db_path)
        loaded = store2.load_profile("AGENT_A")
        assert loaded is not None
        assert loaded.agent_name == "AGENT_A"
        assert loaded.total_tasks_completed == 1
        assert loaded.total_tokens_used == 200

    def test_load_nonexistent_profile(self):
        result = self.store.load_profile("NONEXISTENT")
        assert result is None

    def test_save_and_load_skill_matrix(self):
        profile = self._make_profile()
        self.store.save_profile(profile)
        loaded = self.store.load_profile("AGENT_A")
        assert "技能A" in loaded.skill_matrix
        assert loaded.skill_matrix["技能A"].level == SkillLevel.ADVANCED

    def test_save_and_load_sla_targets(self):
        profile = self._make_profile()
        profile.record_task(score=0.85, duration_sec=10.0)
        self.store.save_profile(profile)
        loaded = self.store.load_profile("AGENT_A")
        assert len(loaded.sla_targets) == 1
        assert loaded.sla_targets[0].metric_name == "avg_score"
        assert loaded.sla_targets[0].current_value == pytest.approx(0.85)

    def test_record_performance(self):
        snap = PerformanceSnapshot(
            date=datetime.date.today().isoformat(),
            tasks_completed=3,
            avg_score=0.8,
            success_rate=0.9,
            avg_response_time_sec=12.0,
            tokens_used=300,
        )
        self.store.record_performance("AGENT_A", snap)
        loaded = self.store.load_profile("AGENT_A")
        # Profile doesn't exist yet, but history is stored
        # After saving profile separately, history loads
        profile = self._make_profile()
        self.store.save_profile(profile)
        loaded = self.store.load_profile("AGENT_A")
        assert len(loaded.performance_history) == 1
        assert loaded.performance_history[0].avg_score == pytest.approx(0.8)

    def test_cost_tracking(self):
        cost = CostRecord(
            date=datetime.date.today().isoformat(),
            llm_provider="anthropic",
            tokens_used=1000,
            estimated_cost_usd=0.05,
        )
        self.store.record_cost("AGENT_A", cost)

        # Verify via fleet summary (cost tracked in DB)
        profile = self._make_profile()
        self.store.save_profile(profile)
        summary = self.store.get_fleet_summary()
        assert summary["total_cost_today_usd"] == pytest.approx(0.05)

    def test_fleet_summary(self):
        for name, profile in DEFAULT_PROFILES.items():
            # Reset accumulated data for clean test
            new_profile = AgentProfile(
                agent_name=profile.agent_name,
                role=profile.role,
                department=profile.department,
                sla_targets=profile.sla_targets,
                skill_matrix=profile.skill_matrix,
            )
            self.store.save_profile(new_profile)

        summary = self.store.get_fleet_summary()
        assert summary["total_agents"] == 4
        assert "agents" in summary
        assert len(summary["agents"]) == 4
        agent_names = {a["agent_name"] for a in summary["agents"]}
        assert "KM_AGENT" in agent_names
        assert "PROCESS_AGENT" in agent_names
        assert "TALENT_AGENT" in agent_names
        assert "DECISION_AGENT" in agent_names

    def test_update_existing_profile(self):
        profile = self._make_profile()
        self.store.save_profile(profile)
        profile.record_task(score=0.9, duration_sec=5.0)
        self.store.save_profile(profile)
        loaded = self.store.load_profile("AGENT_A")
        assert loaded.total_tasks_completed == 1


class TestDefaultProfiles:
    def test_all_four_agents_have_profiles(self):
        assert "KM_AGENT" in DEFAULT_PROFILES
        assert "PROCESS_AGENT" in DEFAULT_PROFILES
        assert "TALENT_AGENT" in DEFAULT_PROFILES
        assert "DECISION_AGENT" in DEFAULT_PROFILES

    def test_km_agent_profile(self):
        p = DEFAULT_PROFILES["KM_AGENT"]
        assert p.role == "知識萃取專家"
        assert p.department == "知識管理部"
        assert len(p.sla_targets) == 3
        assert "文件解析" in p.skill_matrix
        assert p.skill_matrix["文件解析"].level == SkillLevel.EXPERT

    def test_each_agent_has_sla_and_skills(self):
        for name, profile in DEFAULT_PROFILES.items():
            assert len(profile.sla_targets) > 0, f"{name} 缺少 SLA 目標"
            assert len(profile.skill_matrix) > 0, f"{name} 缺少技能矩陣"
