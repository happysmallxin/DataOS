"""下游组件代理服务 — 统一调用各开源组件 API.

对标 DataLeap 的开放接入框架：每个下游组件封装为独立 Client，
统一的错误处理、超时控制、健康检查。
"""

import httpx
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


@dataclass
class HealthResult:
    healthy: bool
    message: str


class ComponentClient:
    """下游组件 HTTP 客户端基类."""

    def __init__(self, base_url: str, name: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.timeout = timeout

    async def health(self) -> HealthResult:
        """健康检查 (子类按需覆盖)."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/health")
                if resp.status_code < 500:
                    return HealthResult(healthy=True, message=f"HTTP {resp.status_code}")
                return HealthResult(healthy=False, message=f"HTTP {resp.status_code}")
        except Exception as e:
            return HealthResult(healthy=False, message=str(e))

    async def get(self, path: str, **kwargs) -> httpx.Response:
        """GET 请求."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.get(f"{self.base_url}{path}", **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        """POST 请求."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.post(f"{self.base_url}{path}", **kwargs)


# 全局组件客户端实例
dolphinscheduler = ComponentClient(settings.DOLPHINSCHEDULER_URL, "DolphinScheduler")
openmetadata = ComponentClient(settings.OPENMETADATA_URL, "OpenMetadata")
seatunnel = ComponentClient(settings.SEATUNNEL_URL, "SeaTunnel")
crawlab = ComponentClient(settings.CRAWLAB_URL, "Crawlab")
datavines = ComponentClient(settings.DATAVINES_URL, "Datavines")
directus = ComponentClient(settings.DIRECTUS_URL, "Directus")

# 按启动顺序排列
ALL_COMPONENTS: list[ComponentClient] = [
    dolphinscheduler,
    openmetadata,
    seatunnel,
    crawlab,
    datavines,
    directus,
]
