"""Skill Registry 測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from harness.skill_registry import SkillRegistry, Skill


class TestSkillRegistry:
    """SkillRegistry 測試"""

    def setup_method(self):
        self.registry = SkillRegistry()

    def test_has_builtins(self):
        """應有 5 個內建技能"""
        skills = self.registry.list_all()
        assert len(skills) >= 5

    def test_get_existing_skill(self):
        skill = self.registry.get("file_read")
        assert skill is not None
        assert skill.name == "file_read"

    def test_get_nonexistent_skill(self):
        assert self.registry.get("nonexistent") is None

    def test_search_by_keyword(self):
        results = self.registry.search("檔案")
        assert len(results) >= 1

    def test_search_by_tag(self):
        results = self.registry.search("sop")
        assert len(results) >= 1

    def test_register_custom_skill(self):
        custom = Skill(
            name="custom_test",
            description="Test skill",
            category="Test",
            execute_fn=lambda: "hello",
        )
        self.registry.register(custom)
        assert self.registry.get("custom_test") is not None

    def test_execute_skill(self):
        custom = Skill(
            name="test_exec",
            description="exec test",
            category="Test",
            execute_fn=lambda x: f"got {x}",
        )
        self.registry.register(custom)
        result = self.registry.execute("test_exec", x="hello")
        assert result == "got hello"

    def test_execute_nonexistent_raises(self):
        try:
            self.registry.execute("nonexistent")
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_file_read_skill(self):
        """真實檔案讀取測試"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                          delete=False, encoding="utf-8") as f:
            f.write("test content")
            f.flush()
            filepath = f.name

        try:
            result = self.registry.execute("file_read", filepath=filepath)
            assert result == "test content"
        finally:
            os.unlink(filepath)

    def test_file_write_skill(self):
        """真實檔案寫入測試"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.md")
            result = self.registry.execute(
                "file_write", filepath=filepath, content="hello world"
            )
            assert "已寫入" in result
            assert os.path.exists(filepath)
            with open(filepath, "r") as f:
                assert f.read() == "hello world"

    def test_knowledge_search_empty(self):
        """空目錄搜尋測試"""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = self.registry.execute(
                "knowledge_search", keyword="test", base_dir=tmpdir
            )
            assert results == []

    def test_knowledge_search_finds_files(self):
        """有檔案時搜尋測試"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "sop_test.md")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# 採購 SOP\n\n步驟一...")
            results = self.registry.execute(
                "knowledge_search", keyword="採購", base_dir=tmpdir
            )
            assert len(results) == 1
            assert results[0]["title"] == "採購 SOP"

    def test_summarize_short_text(self):
        result = self.registry.execute("summarize", text="短文字")
        assert result == "短文字"

    def test_summarize_long_text(self):
        long = "A" * 500
        result = self.registry.execute("summarize", text=long, max_length=100)
        assert len(result) < len(long)
        assert result.endswith("...")

    def test_get_report(self):
        report = self.registry.get_report()
        assert "Skill Registry" in report
        assert "file_read" in report
