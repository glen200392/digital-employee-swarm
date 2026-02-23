"""
Git-based Memory 模組
實作 Anthropic 建議的 Git-based Memory，確保 Agent 每次 Session 結束後
都有完整的進度記錄，下次 Session 可以無縫接手。
"""

import os
import subprocess
import datetime
from typing import List, Optional


class GitMemory:
    """
    Agent 記憶基礎設施。
    透過檔案日誌 + Git Commit 實現持久化記憶。
    """

    def __init__(self, repo_path: Optional[str] = None):
        if repo_path is None:
            repo_path = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        self.repo_path = repo_path
        self._ensure_dirs()

    def _ensure_dirs(self):
        """確保必要的目錄存在"""
        dirs = [
            os.path.join(self.repo_path, "docs"),
            os.path.join(self.repo_path, "docs", "sops"),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    @property
    def log_file(self) -> str:
        return os.path.join(self.repo_path, "docs", "progress.log")

    @property
    def progress_md(self) -> str:
        return os.path.join(self.repo_path, "PROGRESS.md")

    def commit_progress(self, agent_name: str, task_id: str, message: str):
        """
        將 Agent 的工作進度寫入日誌並嘗試 Git Commit。
        這是 Anthropic「每個 Session 結束必須提交 Git commit」原則的實作。
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{agent_name}] Task-{task_id}: {message}"

        # 1. 寫入文字日誌
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

        # 2. 更新 PROGRESS.md
        self._update_progress_md(agent_name, task_id, message, timestamp)

        print(f"  [Memory] {agent_name} 記憶已更新: {message}")

        # 3. 嘗試 Git Commit
        self._try_git_commit(agent_name, task_id)

    def _update_progress_md(self, agent_name: str, task_id: str,
                            message: str, timestamp: str):
        """更新 PROGRESS.md 進度追蹤文件"""
        entry = f"| {timestamp} | {agent_name} | {task_id} | {message} |\n"

        if not os.path.exists(self.progress_md):
            header = (
                "# Agent Fleet Progress Tracker\n\n"
                "| 時間 | Agent | Task ID | 狀態 |\n"
                "|------|-------|---------|------|\n"
            )
            with open(self.progress_md, "w", encoding="utf-8") as f:
                f.write(header + entry)
        else:
            with open(self.progress_md, "a", encoding="utf-8") as f:
                f.write(entry)

    def _try_git_commit(self, agent_name: str, task_id: str):
        """在 Git 環境下自動提交"""
        git_dir = os.path.join(self.repo_path, ".git")
        if not os.path.exists(git_dir):
            return

        try:
            subprocess.run(
                ["git", "add", "."],
                cwd=self.repo_path, check=True, capture_output=True
            )
            commit_msg = f"feat({agent_name}): update task {task_id}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.repo_path, check=True, capture_output=True
            )
        except subprocess.CalledProcessError:
            pass  # 忽略非 git 環境或無變更的情況

    def get_last_context(self, agent_name: str, max_entries: int = 5) -> List[str]:
        """
        讀取指定 Agent 最近 N 條記憶記錄。
        這是 Initializer Agent「重建上下文」的核心。
        """
        if not os.path.exists(self.log_file):
            return []

        results = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                if f"[{agent_name}]" in line:
                    results.append(line.strip())
                    if len(results) >= max_entries:
                        break
        except Exception:
            pass

        return results

    def get_all_progress(self) -> List[str]:
        """讀取全部進度日誌"""
        if not os.path.exists(self.log_file):
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return [line.strip() for line in f.readlines() if line.strip()]
        except Exception:
            return []