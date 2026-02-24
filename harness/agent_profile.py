"""
Agent 員工檔案系統
每個 AI Agent 的完整履歷：技能矩陣、績效歷史、SLA 目標、成本追蹤。
資料儲存於 SQLite（data/agent_profiles.db）。
"""

import json
import os
import sqlite3
import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SkillLevel(Enum):
    BEGINNER = 1      # 入門
    INTERMEDIATE = 2  # 熟練
    ADVANCED = 3      # 精通
    EXPERT = 4        # 專家


@dataclass
class SkillEntry:
    skill_name: str
    level: SkillLevel
    last_used: str
    usage_count: int = 0


@dataclass
class PerformanceSnapshot:
    date: str                    # YYYY-MM-DD
    tasks_completed: int
    avg_score: float
    success_rate: float          # 0.0~1.0
    avg_response_time_sec: float
    tokens_used: int = 0         # LLM token 用量


@dataclass
class SLATarget:
    metric_name: str
    target_value: float
    current_value: float
    unit: str  # "seconds" | "percent" | "score"

    @property
    def is_meeting_sla(self) -> bool:
        if self.unit == "seconds":
            # For response time, lower is better
            return self.current_value <= self.target_value if self.current_value > 0 else False
        return self.current_value >= self.target_value


@dataclass
class CostRecord:
    date: str
    llm_provider: str
    tokens_used: int
    estimated_cost_usd: float  # 估算成本


class AgentProfile:
    """AI Agent 的完整員工檔案"""

    def __init__(self, agent_name: str, role: str, department: str,
                 sla_targets: Optional[List[SLATarget]] = None,
                 skill_matrix: Optional[Dict[str, SkillEntry]] = None):
        self.agent_name = agent_name
        self.role = role
        self.department = department
        self.hired_date = datetime.date.today().isoformat()
        self.skill_matrix: Dict[str, SkillEntry] = skill_matrix or {}
        self.performance_history: List[PerformanceSnapshot] = []
        self.sla_targets: List[SLATarget] = sla_targets or []
        self.cost_history: List[CostRecord] = []
        self.total_tasks_completed: int = 0
        self.total_tokens_used: int = 0

        # Running accumulators for today's snapshot
        self._today_scores: List[float] = []
        self._today_durations: List[float] = []
        self._today_tokens: int = 0
        self._today_successes: int = 0

    def update_skill(self, skill_name: str, level: SkillLevel):
        """更新或新增技能條目"""
        today = datetime.date.today().isoformat()
        if skill_name in self.skill_matrix:
            entry = self.skill_matrix[skill_name]
            entry.level = level
            entry.last_used = today
            entry.usage_count += 1
        else:
            self.skill_matrix[skill_name] = SkillEntry(
                skill_name=skill_name,
                level=level,
                last_used=today,
                usage_count=1,
            )

    def record_task(self, score: float, duration_sec: float, tokens: int = 0):
        """記錄一次任務執行，更新統計數據"""
        self.total_tasks_completed += 1
        self.total_tokens_used += tokens
        self._today_scores.append(score)
        self._today_durations.append(duration_sec)
        self._today_tokens += tokens
        if score >= 0.5:
            self._today_successes += 1

        # Update SLA current values
        n = len(self._today_scores)
        avg_score = sum(self._today_scores) / n
        success_rate = self._today_successes / n
        avg_resp = sum(self._today_durations) / n

        for sla in self.sla_targets:
            if sla.metric_name == "avg_score":
                sla.current_value = avg_score
            elif sla.metric_name == "success_rate":
                sla.current_value = success_rate
            elif sla.metric_name == "avg_response_time":
                sla.current_value = avg_resp

    def get_today_snapshot(self) -> PerformanceSnapshot:
        """取得今日績效快照"""
        today = datetime.date.today().isoformat()
        n = len(self._today_scores)
        if n == 0:
            return PerformanceSnapshot(
                date=today,
                tasks_completed=0,
                avg_score=0.0,
                success_rate=0.0,
                avg_response_time_sec=0.0,
                tokens_used=0,
            )
        return PerformanceSnapshot(
            date=today,
            tasks_completed=n,
            avg_score=sum(self._today_scores) / n,
            success_rate=self._today_successes / n,
            avg_response_time_sec=sum(self._today_durations) / n,
            tokens_used=self._today_tokens,
        )

    def get_performance_trend(self, days: int = 7) -> List[PerformanceSnapshot]:
        """取得最近 N 天的績效趨勢"""
        return self.performance_history[-days:]

    def calculate_sla_compliance(self) -> float:
        """計算整體 SLA 達標率 (0.0~1.0)"""
        if not self.sla_targets:
            return 1.0
        met = sum(1 for s in self.sla_targets if s.is_meeting_sla)
        return met / len(self.sla_targets)

    def to_dict(self) -> Dict:
        """序列化為字典"""
        today_snap = self.get_today_snapshot()
        return {
            "agent_name": self.agent_name,
            "role": self.role,
            "department": self.department,
            "hired_date": self.hired_date,
            "total_tasks_completed": self.total_tasks_completed,
            "total_tokens_used": self.total_tokens_used,
            "sla_compliance": self.calculate_sla_compliance(),
            "skill_matrix": {
                name: {
                    "skill_name": e.skill_name,
                    "level": e.level.name,
                    "level_value": e.level.value,
                    "last_used": e.last_used,
                    "usage_count": e.usage_count,
                }
                for name, e in self.skill_matrix.items()
            },
            "sla_targets": [
                {
                    "metric_name": s.metric_name,
                    "target_value": s.target_value,
                    "current_value": s.current_value,
                    "unit": s.unit,
                    "is_meeting_sla": s.is_meeting_sla,
                }
                for s in self.sla_targets
            ],
            "performance_history": [
                {
                    "date": p.date,
                    "tasks_completed": p.tasks_completed,
                    "avg_score": p.avg_score,
                    "success_rate": p.success_rate,
                    "avg_response_time_sec": p.avg_response_time_sec,
                    "tokens_used": p.tokens_used,
                }
                for p in self.performance_history
            ],
            "today_snapshot": {
                "date": today_snap.date,
                "tasks_completed": today_snap.tasks_completed,
                "avg_score": today_snap.avg_score,
                "success_rate": today_snap.success_rate,
                "avg_response_time_sec": today_snap.avg_response_time_sec,
                "tokens_used": today_snap.tokens_used,
            },
        }


class AgentProfileStore:
    """Agent 員工檔案的 SQLite 持久化儲存"""

    def __init__(self, db_path: str = "data/agent_profiles.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """建立資料表（若不存在）"""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agent_profiles (
                    agent_name   TEXT PRIMARY KEY,
                    role         TEXT NOT NULL,
                    department   TEXT NOT NULL,
                    hired_date   TEXT NOT NULL,
                    skill_matrix TEXT NOT NULL DEFAULT '{}',
                    sla_targets  TEXT NOT NULL DEFAULT '[]',
                    total_tasks_completed INTEGER NOT NULL DEFAULT 0,
                    total_tokens_used     INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS performance_history (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name   TEXT NOT NULL,
                    date         TEXT NOT NULL,
                    tasks_completed       INTEGER NOT NULL DEFAULT 0,
                    avg_score            REAL NOT NULL DEFAULT 0.0,
                    success_rate         REAL NOT NULL DEFAULT 0.0,
                    avg_response_time_sec REAL NOT NULL DEFAULT 0.0,
                    tokens_used          INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS cost_history (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name          TEXT NOT NULL,
                    date                TEXT NOT NULL,
                    llm_provider        TEXT NOT NULL,
                    tokens_used         INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd  REAL NOT NULL DEFAULT 0.0
                );
            """)

    def save_profile(self, profile: AgentProfile):
        """儲存或更新 Agent 檔案（不含歷史記錄）"""
        skill_json = json.dumps({
            name: {
                "skill_name": e.skill_name,
                "level": e.level.name,
                "last_used": e.last_used,
                "usage_count": e.usage_count,
            }
            for name, e in profile.skill_matrix.items()
        }, ensure_ascii=False)

        sla_json = json.dumps([
            {
                "metric_name": s.metric_name,
                "target_value": s.target_value,
                "current_value": s.current_value,
                "unit": s.unit,
            }
            for s in profile.sla_targets
        ], ensure_ascii=False)

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO agent_profiles
                    (agent_name, role, department, hired_date,
                     skill_matrix, sla_targets,
                     total_tasks_completed, total_tokens_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_name) DO UPDATE SET
                    role=excluded.role,
                    department=excluded.department,
                    skill_matrix=excluded.skill_matrix,
                    sla_targets=excluded.sla_targets,
                    total_tasks_completed=excluded.total_tasks_completed,
                    total_tokens_used=excluded.total_tokens_used
            """, (
                profile.agent_name, profile.role, profile.department,
                profile.hired_date, skill_json, sla_json,
                profile.total_tasks_completed, profile.total_tokens_used,
            ))

    def load_profile(self, agent_name: str) -> Optional[AgentProfile]:
        """從 SQLite 載入 Agent 檔案"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_profiles WHERE agent_name=?", (agent_name,)
            ).fetchone()
            if not row:
                return None

            # Reconstruct skill_matrix
            raw_skills = json.loads(row["skill_matrix"])
            skill_matrix = {}
            for name, data in raw_skills.items():
                skill_matrix[name] = SkillEntry(
                    skill_name=data["skill_name"],
                    level=SkillLevel[data["level"]],
                    last_used=data["last_used"],
                    usage_count=data.get("usage_count", 0),
                )

            # Reconstruct sla_targets
            raw_slas = json.loads(row["sla_targets"])
            sla_targets = [
                SLATarget(
                    metric_name=s["metric_name"],
                    target_value=s["target_value"],
                    current_value=s["current_value"],
                    unit=s["unit"],
                )
                for s in raw_slas
            ]

            profile = AgentProfile(
                agent_name=row["agent_name"],
                role=row["role"],
                department=row["department"],
                sla_targets=sla_targets,
                skill_matrix=skill_matrix,
            )
            profile.hired_date = row["hired_date"]
            profile.total_tasks_completed = row["total_tasks_completed"]
            profile.total_tokens_used = row["total_tokens_used"]

            # Load performance history
            rows = conn.execute(
                "SELECT * FROM performance_history WHERE agent_name=? ORDER BY date",
                (agent_name,),
            ).fetchall()
            profile.performance_history = [
                PerformanceSnapshot(
                    date=r["date"],
                    tasks_completed=r["tasks_completed"],
                    avg_score=r["avg_score"],
                    success_rate=r["success_rate"],
                    avg_response_time_sec=r["avg_response_time_sec"],
                    tokens_used=r["tokens_used"],
                )
                for r in rows
            ]

            return profile

    def record_performance(self, agent_name: str, snapshot: PerformanceSnapshot):
        """記錄績效快照到資料庫"""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO performance_history
                    (agent_name, date, tasks_completed, avg_score,
                     success_rate, avg_response_time_sec, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_name, snapshot.date, snapshot.tasks_completed,
                snapshot.avg_score, snapshot.success_rate,
                snapshot.avg_response_time_sec, snapshot.tokens_used,
            ))

    def record_cost(self, agent_name: str, cost_record: CostRecord):
        """記錄成本到資料庫"""
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO cost_history
                    (agent_name, date, llm_provider, tokens_used, estimated_cost_usd)
                VALUES (?, ?, ?, ?, ?)
            """, (
                agent_name, cost_record.date, cost_record.llm_provider,
                cost_record.tokens_used, cost_record.estimated_cost_usd,
            ))

    def get_fleet_summary(self) -> Dict:
        """返回整個 Agent Fleet 的統計摘要"""
        today = datetime.date.today().isoformat()
        with self._connect() as conn:
            agents_rows = conn.execute(
                "SELECT agent_name, role, department, total_tasks_completed FROM agent_profiles"
            ).fetchall()

            today_perf = conn.execute("""
                SELECT agent_name,
                       SUM(tasks_completed) as tasks,
                       AVG(avg_score) as score
                FROM performance_history
                WHERE date=?
                GROUP BY agent_name
            """, (today,)).fetchall()

            today_cost = conn.execute("""
                SELECT SUM(estimated_cost_usd) as total_cost
                FROM cost_history
                WHERE date=?
            """, (today,)).fetchone()

        perf_map = {r["agent_name"]: r for r in today_perf}
        total_tasks_today = sum(r["tasks"] or 0 for r in today_perf)
        scores = [r["score"] for r in today_perf if r["score"] is not None]
        fleet_avg_score = sum(scores) / len(scores) if scores else 0.0
        total_cost = (today_cost["total_cost"] or 0.0) if today_cost else 0.0

        agent_summaries = []
        for row in agents_rows:
            name = row["agent_name"]
            p = perf_map.get(name)
            agent_summaries.append({
                "agent_name": name,
                "role": row["role"],
                "department": row["department"],
                "total_tasks_completed": row["total_tasks_completed"],
                "tasks_today": p["tasks"] if p else 0,
                "avg_score_today": p["score"] if p else 0.0,
            })

        return {
            "total_agents": len(agents_rows),
            "total_tasks_today": total_tasks_today,
            "fleet_avg_score": round(fleet_avg_score, 4),
            "total_cost_today_usd": round(total_cost, 6),
            "agents": agent_summaries,
        }
