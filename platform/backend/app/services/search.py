"""搜索服务抽象层 — 开发用 Meilisearch，生产可切 ES.

切换方法:
  1. 实现 ESSearchService 类 (相同接口)
  2. 修改工厂函数 create_search_service()
  3. 从同一数据源重建索引

半天完成迁移，其他代码无感知。
"""

from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.core.config import settings


class SearchResult:
    """搜索结果统一模型."""
    hits: list[dict]
    total: int
    query: str

    def __init__(self, hits: list[dict], total: int, query: str):
        self.hits = hits
        self.total = total
        self.query = query


class BaseSearchService(ABC):
    """搜索引擎抽象接口 — 所有实现必须遵循此契约."""

    @abstractmethod
    async def search(
        self,
        index: str,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResult:
        """全文搜索."""
        ...

    @abstractmethod
    async def index_documents(self, index: str, documents: list[dict]) -> int:
        """批量写入文档, 返回 task_id."""
        ...

    @abstractmethod
    async def delete_index(self, index: str) -> bool:
        """删除索引."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """健康检查."""
        ...


# ============================================================
# Meilisearch 实现 (Phase 1 默认)
# ============================================================
class MeilisearchService(BaseSearchService):
    """Meilisearch REST API 封装.

    文档: https://docs.meilisearch.com/reference/api
    """

    def __init__(self, base_url: str = settings.MEILI_URL, master_key: str = settings.MEILI_MASTER_KEY):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {master_key}", "Content-Type": "application/json"}

    async def search(
        self,
        index: str,
        query: str,
        filters: Optional[dict] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResult:
        """全文搜索 — 支持中文分词、容错、过滤."""
        body: dict = {"q": query, "limit": limit, "offset": offset}
        if filters:
            body["filter"] = " AND ".join(f"{k} = {v}" for k, v in filters.items())

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/indexes/{index}/search",
                headers=self.headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return SearchResult(
                hits=data.get("hits", []),
                total=data.get("estimatedTotalHits", 0),
                query=data.get("query", query),
            )

    async def index_documents(self, index: str, documents: list[dict]) -> int:
        """批量写入文档 — Meilisearch 自动推断字段类型."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/indexes/{index}/documents",
                headers=self.headers,
                json=documents,
            )
            resp.raise_for_status()
            return resp.json().get("taskUid", 0)

    async def delete_index(self, index: str) -> bool:
        """删除索引 (用于重建)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(f"{self.base_url}/indexes/{index}", headers=self.headers)
            return resp.status_code in (200, 202, 204)

    async def health(self) -> bool:
        """健康检查."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.json().get("status") == "available"
        except Exception:
            return False


# ============================================================
# ES 实现 (Phase 3 生产环境, 需要时取消注释)
# ============================================================
# class ESSearchService(BaseSearchService):
#     """Elasticsearch 实现 — x86_64 Linux 生产环境使用."""
#
#     def __init__(self, base_url: str = "http://localhost:9200"):
#         self.base_url = base_url.rstrip("/")
#
#     async def search(self, index, query, filters=None, limit=20, offset=0):
#         body = {"query": {"match": {"_all": query}}, "size": limit, "from": offset}
#         if filters:
#             must = [{"term": {k: v}} for k, v in filters.items()]
#             body["query"] = {"bool": {"must": [{"match": {"_all": query}}] + must}}
#         async with httpx.AsyncClient(timeout=10) as client:
#             resp = await client.post(f"{self.base_url}/{index}/_search", json=body)
#             resp.raise_for_status()
#             data = resp.json()
#             return SearchResult(
#                 hits=[h["_source"] for h in data["hits"]["hits"]],
#                 total=data["hits"]["total"]["value"],
#                 query=query,
#             )
#
#     async def index_documents(self, index, documents):
#         # ES bulk API ...
#         pass
#
#     async def delete_index(self, index):
#         async with httpx.AsyncClient(timeout=10) as client:
#             resp = await client.delete(f"{self.base_url}/{index}")
#             return resp.status_code in (200, 202)
#
#     async def health(self):
#         try:
#             async with httpx.AsyncClient(timeout=5) as client:
#                 resp = await client.get(f"{self.base_url}/_cluster/health")
#                 return resp.json().get("status") in ("green", "yellow")
#         except Exception:
#             return False


# ============================================================
# 工厂函数 — 切换搜索引擎在这里改一行
# ============================================================
def create_search_service() -> BaseSearchService:
    """工厂函数: 返回搜索引擎实现.

    切 ES: return ESSearchService()
    切 Meilisearch: return MeilisearchService() (默认)
    """
    return MeilisearchService()


# 全局单例
search_service: BaseSearchService = create_search_service()
