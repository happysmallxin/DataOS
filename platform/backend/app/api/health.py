"""平台健康检查 — 统一展示所有下游组件状态.

对标 DataLeap 治理门户：一个接口看清全平台健康度。
"""

import asyncio
from fastapi import APIRouter

from app.api.schemas import PlatformHealthResponse, ComponentStatus
from app.core.config import settings
from app.services.component_proxy import ALL_COMPONENTS

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=PlatformHealthResponse)
async def health_check():
    """全平台健康检查 — 检查所有下游组件."""
    # 并行检查所有组件
    results = await asyncio.gather(
        *[c.health() for c in ALL_COMPONENTS],
        return_exceptions=True,
    )

    components = []
    all_healthy = True
    for comp, result in zip(ALL_COMPONENTS, results):
        if isinstance(result, Exception):
            components.append(ComponentStatus(name=comp.name, url=comp.base_url, healthy=False, message=str(result)))
            all_healthy = False
        else:
            components.append(ComponentStatus(name=comp.name, url=comp.base_url, healthy=result.healthy, message=result.message))
            if not result.healthy:
                all_healthy = False

    db_healthy = True  # 后续接入 DB ping
    overall = "healthy" if all_healthy and db_healthy else "degraded"

    return PlatformHealthResponse(status=overall, version=settings.APP_VERSION, components=components)
