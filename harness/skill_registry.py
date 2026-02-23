"""
Skill 管理系統
Agent 可動態載入、查詢、執行的能力模組。
"""

import os
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Skill:
    """可重用的能力模組"""
    name: str
    description: str
    category: str
    execute_fn: Callable
    tags: List[str] = field(default_factory=list)


class SkillRegistry:
    """
    Skill 管理中心。
    Agent 可以動態查詢和使用技能，而不是 hardcode 在自身邏輯裡。
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._register_builtins()

    def register(self, skill: Skill):
        """註冊新技能"""
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        """取得指定技能"""
        return self._skills.get(name)

    def search(self, keyword: str) -> List[Skill]:
        """搜尋相關技能"""
        keyword_lower = keyword.lower()
        return [
            s for s in self._skills.values()
            if keyword_lower in s.name.lower()
            or keyword_lower in s.description.lower()
            or any(keyword_lower in t.lower() for t in s.tags)
        ]

    def list_all(self) -> List[Skill]:
        """列出所有技能"""
        return list(self._skills.values())

    def execute(self, skill_name: str, **kwargs) -> Any:
        """執行指定技能"""
        skill = self._skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' 不存在")
        return skill.execute_fn(**kwargs)

    def _register_builtins(self):
        """註冊內建技能"""
        self.register(Skill(
            name="file_read",
            description="讀取本地檔案內容",
            category="IO",
            tags=["檔案", "讀取", "file", "read"],
            execute_fn=self._skill_file_read,
        ))
        self.register(Skill(
            name="file_write",
            description="寫入內容到本地檔案",
            category="IO",
            tags=["檔案", "寫入", "file", "write"],
            execute_fn=self._skill_file_write,
        ))
        self.register(Skill(
            name="knowledge_search",
            description="搜尋知識庫（docs/sops/）中的知識卡片",
            category="知識管理",
            tags=["知識", "搜尋", "search", "sop"],
            execute_fn=self._skill_knowledge_search,
        ))
        self.register(Skill(
            name="report_list",
            description="列出所有已生成的分析報告",
            category="報告",
            tags=["報告", "list", "report"],
            execute_fn=self._skill_report_list,
        ))
        self.register(Skill(
            name="summarize",
            description="對文字內容進行摘要",
            category="分析",
            tags=["摘要", "summarize", "summary"],
            execute_fn=self._skill_summarize,
        ))

    # === 內建技能實作 ===

    @staticmethod
    def _skill_file_read(filepath: str) -> str:
        """讀取檔案"""
        if not os.path.exists(filepath):
            return f"檔案不存在: {filepath}"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"讀取失敗: {e}"

    @staticmethod
    def _skill_file_write(filepath: str, content: str) -> str:
        """寫入檔案"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"已寫入: {filepath}"
        except Exception as e:
            return f"寫入失敗: {e}"

    @staticmethod
    def _skill_knowledge_search(keyword: str = "",
                                base_dir: str = "") -> List[Dict]:
        """搜尋知識庫"""
        if not base_dir:
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "docs", "sops"
            )
        results = []
        if not os.path.exists(base_dir):
            return results
        for filename in os.listdir(base_dir):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(base_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                if not keyword or keyword.lower() in content.lower():
                    # 取第一行作為標題
                    title = content.split("\n")[0].replace("#", "").strip()
                    results.append({
                        "file": filename,
                        "title": title,
                        "path": filepath,
                        "size": len(content),
                    })
            except Exception:
                pass
        return results

    @staticmethod
    def _skill_report_list(base_dir: str = "") -> List[Dict]:
        """列出所有報告"""
        if not base_dir:
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "docs", "reports"
            )
        results = []
        if not os.path.exists(base_dir):
            return results
        for filename in os.listdir(base_dir):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(base_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    first_line = f.readline().replace("#", "").strip()
                results.append({
                    "file": filename,
                    "title": first_line,
                    "path": filepath,
                })
            except Exception:
                pass
        return results

    @staticmethod
    def _skill_summarize(text: str, max_length: int = 200) -> str:
        """簡易文字摘要（離線版，取前 N 字元）"""
        if len(text) <= max_length:
            return text
        # 找最近的句號或換行
        truncated = text[:max_length]
        last_period = max(truncated.rfind("。"), truncated.rfind("\n"))
        if last_period > max_length // 2:
            return truncated[:last_period + 1] + "..."
        return truncated + "..."

    def get_report(self) -> str:
        """產出技能清單報告"""
        lines = ["=== Skill Registry ==="]
        categories: Dict[str, List[Skill]] = {}
        for skill in self._skills.values():
            categories.setdefault(skill.category, []).append(skill)

        for category, skills in sorted(categories.items()):
            lines.append(f"\n  [{category}]")
            for s in skills:
                lines.append(f"    • {s.name}: {s.description}")
        lines.append(f"\n  共 {len(self._skills)} 個技能")
        return "\n".join(lines)
