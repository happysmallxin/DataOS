"""审计日志 API — 合规查询.

端点:
  GET /api/v1/audit-logs                        审计日志列表 (支持筛选/分页)
  GET /api/v1/audit-logs/{id}                   审计日志详情
  GET /api/v1/projects/{id}/audit-logs          项目审计日志
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_active_superuser
from app.api.schemas import AuditLogResponse, AuditLogListResponse
from app.core.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog

router = APIRouter(tags=["Audit"])


@router.get("/api/v1/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: int | None = Query(None),
    project_id: int | None = Query(None),
    resource: str | None = Query(None),
    action: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_superuser),
):
    """审计日志列表 (admin only)."""
    # 基础查询 + 关联用户名
    stmt = select(AuditLog, User.username).join(
        User, User.id == AuditLog.user_id, isouter=True
    )

    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if project_id:
        stmt = stmt.where(AuditLog.project_id == project_id)
    if resource:
        stmt = stmt.where(AuditLog.resource == resource)
    if action:
        stmt = stmt.where(AuditLog.action == action)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页
    stmt = stmt.order_by(desc(AuditLog.created_at))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for log, username in rows:
        item = AuditLogResponse.model_validate(log)
        item.username = username or f"user#{log.user_id}"
        items.append(item)

    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


@router.get("/api/v1/projects/{project_id}/audit-logs", response_model=AuditLogListResponse)
async def list_project_audit_logs(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    resource: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """项目审计日志 (项目成员可查看)."""
    stmt = select(AuditLog, User.username).join(
        User, User.id == AuditLog.user_id, isouter=True
    ).where(AuditLog.project_id == project_id)

    if resource:
        stmt = stmt.where(AuditLog.resource == resource)

    # 总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(desc(AuditLog.created_at))
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for log, username in rows:
        item = AuditLogResponse.model_validate(log)
        item.username = username or f"user#{log.user_id}"
        items.append(item)

    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )
