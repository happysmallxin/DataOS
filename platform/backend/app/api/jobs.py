"""任务状态 API — 异步任务轮询."""

from fastapi import APIRouter, HTTPException
from app.core.job_queue import get_job_status

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get("/{job_id}")
async def get_job(job_id: str):
    """查询异步任务状态."""
    status = await get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return status
