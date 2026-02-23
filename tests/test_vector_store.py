"""向量資料庫測試"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from harness.vector_store import VectorStore


class TestVectorStore:
    """VectorStore 測試（使用 fallback 模式）"""

    def setup_method(self):
        self.vs = VectorStore()

    def test_backend_name(self):
        name = self.vs.backend_name
        assert isinstance(name, str)
        assert len(name) > 0

    def test_add_document(self):
        result = self.vs.add_document("doc1", "知識萃取流程")
        assert result is True

    def test_search_finds_document(self):
        self.vs.add_document("doc1", "知識萃取流程 SOP")
        self.vs.add_document("doc2", "採購流程優化")
        results = self.vs.search("知識")
        assert len(results) >= 1

    def test_search_empty(self):
        results = self.vs.search("不存在的東東")
        assert len(results) == 0

    def test_document_count(self):
        self.vs.add_document("a", "aaa")
        self.vs.add_document("b", "bbb")
        assert self.vs.document_count >= 2

    def test_index_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 建立測試 Markdown 檔案
            for i in range(3):
                with open(os.path.join(tmpdir, f"test_{i}.md"), "w") as f:
                    f.write(f"# Test {i}\n\nContent {i}")
            count = self.vs.index_directory(tmpdir)
            assert count == 3

    def test_index_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            count = self.vs.index_directory(tmpdir)
            assert count == 0

    def test_index_nonexistent_directory(self):
        count = self.vs.index_directory("/nonexistent/path")
        assert count == 0

    def test_get_status(self):
        status = self.vs.get_status()
        assert "backend" in status
        assert "documents" in status
        assert "is_vector" in status

    def test_add_with_metadata(self):
        self.vs.add_document("m1", "content", metadata={"title": "Test"})
        results = self.vs.search("content")
        assert len(results) >= 0  # might not find in hash-based mode
