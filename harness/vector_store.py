"""
向量資料庫（支援磁碟持久化、遠端 Qdrant Server 及 in-memory 模式）
預設使用本地磁碟持久化模式（./data/qdrant）。
可透過環境變數切換模式：
  VECTOR_STORE_MODE=memory  → in-memory（測試用）
  QDRANT_HOST / QDRANT_PORT → 遠端 Qdrant Server
  QDRANT_PATH               → 本地磁碟路徑（預設 ./data/qdrant）
"""

import os
import hashlib
from typing import Any, Dict, List, Optional


class VectorStore:
    """
    向量資料庫封裝。
    - 有 qdrant-client 時：依環境變數選擇磁碟/遠端/in-memory 模式
    - 無 qdrant-client 時：fallback 到簡單的關鍵字搜尋
    """

    def __init__(self, collection_name: str = "knowledge_base"):
        self.collection_name = collection_name
        self._client = None
        self._embedding_fn = None
        self._docs: List[Dict] = []  # fallback 用
        self._init_backend()

    def _init_backend(self):
        """初始化向量資料庫後端"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import (
                VectorParams, Distance, PointStruct
            )

            mode = os.getenv("VECTOR_STORE_MODE", "disk")
            qdrant_host = os.getenv("QDRANT_HOST", "")
            qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
            qdrant_path = os.getenv("QDRANT_PATH", "./data/qdrant")

            if qdrant_host:
                # 遠端 Qdrant Server
                self._client = QdrantClient(host=qdrant_host, port=qdrant_port)
            elif mode == "memory":
                # 強制 in-memory（測試用）
                self._client = QdrantClient(":memory:")
            else:
                # 預設：本地磁碟持久化
                os.makedirs(qdrant_path, exist_ok=True)
                self._client = QdrantClient(path=qdrant_path)
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,  # sentence-transformers 預設維度
                    distance=Distance.COSINE,
                ),
            )
            self._qdrant_models = {
                "PointStruct": PointStruct,
            }

            # 嘗試載入 embedding 模型
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_fn = SentenceTransformer(
                    "all-MiniLM-L6-v2"
                ).encode
            except ImportError:
                self._embedding_fn = self._simple_embedding

        except ImportError:
            self._client = None

    @property
    def is_vector_mode(self) -> bool:
        return self._client is not None

    @property
    def backend_name(self) -> str:
        if self._client is not None:
            mode = os.getenv("VECTOR_STORE_MODE", "disk")
            qdrant_host = os.getenv("QDRANT_HOST", "")
            if qdrant_host:
                return "Qdrant (remote)"
            if mode == "memory":
                return "Qdrant (in-memory)"
            return "Qdrant (disk)"
        return "Keyword Search (fallback)"

    def _simple_embedding(self, text: str) -> List[float]:
        """簡易的確定性 embedding（無 sentence-transformers 時）"""
        import struct
        # 使用 SHA-384 hash 產生 384 維向量
        h = hashlib.sha384(text.encode("utf-8")).digest()
        # 將 48 bytes 拆成 384 個值（每個 1 byte → 映射到 -1~1）
        vec = [(b / 127.5) - 1.0 for b in h]
        # 擴展到 384 維
        while len(vec) < 384:
            extra = hashlib.sha384(
                text.encode("utf-8") + len(vec).to_bytes(4, "big")
            ).digest()
            vec.extend([(b / 127.5) - 1.0 for b in extra])
        return vec[:384]

    def add_document(self, doc_id: str, content: str,
                     metadata: Optional[Dict] = None) -> bool:
        """新增文件到向量資料庫"""
        metadata = metadata or {}

        if self._client is not None:
            try:
                embedding = self._embedding_fn(content)
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                point_id = int(hashlib.md5(doc_id.encode()).hexdigest()[:8], 16)
                PointStruct = self._qdrant_models["PointStruct"]
                self._client.upsert(
                    collection_name=self.collection_name,
                    points=[PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "doc_id": doc_id,
                            "content": content[:2000],
                            "title": metadata.get("title", ""),
                            **metadata,
                        },
                    )],
                )
                return True
            except Exception as e:
                print(f"  [VectorStore] Qdrant 寫入失敗: {e}")

        # Fallback: 儲存到記憶體列表
        self._docs.append({
            "doc_id": doc_id,
            "content": content,
            "metadata": metadata,
        })
        return True

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """語意搜尋"""
        if self._client is not None:
            try:
                embedding = self._embedding_fn(query)
                if hasattr(embedding, 'tolist'):
                    embedding = embedding.tolist()
                # Qdrant v1.10+ 使用 query_points
                try:
                    from qdrant_client.models import QueryRequest
                    result = self._client.query_points(
                        collection_name=self.collection_name,
                        query=embedding,
                        limit=top_k,
                    )
                    return [
                        {
                            "doc_id": p.payload.get("doc_id", ""),
                            "title": p.payload.get("title", ""),
                            "content": p.payload.get("content", ""),
                            "score": p.score,
                        }
                        for p in result.points
                    ]
                except (ImportError, AttributeError, TypeError):
                    # Fallback to legacy search API
                    results = self._client.search(
                        collection_name=self.collection_name,
                        query_vector=embedding,
                        limit=top_k,
                    )
                    return [
                        {
                            "doc_id": r.payload.get("doc_id", ""),
                            "title": r.payload.get("title", ""),
                            "content": r.payload.get("content", ""),
                            "score": r.score,
                        }
                        for r in results
                    ]
            except Exception as e:
                print(f"  [VectorStore] Qdrant 搜尋失敗: {e}")

        # Fallback: 關鍵字搜尋
        query_lower = query.lower()
        results = []
        for doc in self._docs:
            content = doc["content"].lower()
            if query_lower in content:
                score = content.count(query_lower) / max(len(content.split()), 1)
                results.append({
                    "doc_id": doc["doc_id"],
                    "title": doc.get("metadata", {}).get("title", ""),
                    "content": doc["content"][:500],
                    "score": min(score, 1.0),
                })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def index_directory(self, directory: str) -> int:
        """掃描目錄中的 Markdown 檔案並索引"""
        count = 0
        if not os.path.exists(directory):
            return 0

        for filename in os.listdir(directory):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                title = content.split("\n")[0].replace("#", "").strip()
                self.add_document(
                    doc_id=filename,
                    content=content,
                    metadata={"title": title, "path": filepath},
                )
                count += 1
            except Exception:
                pass
        return count

    @property
    def document_count(self) -> int:
        if self._client is not None:
            try:
                info = self._client.get_collection(self.collection_name)
                return info.points_count
            except Exception:
                pass
        return len(self._docs)

    def get_status(self) -> Dict[str, Any]:
        return {
            "backend": self.backend_name,
            "collection": self.collection_name,
            "documents": self.document_count,
            "is_vector": self.is_vector_mode,
        }
