"""数据源管理 API — 对标 DataWorks 全域数据集成.

RBAC 权限: 所有操作需要对应项目的成员角色 + resource:action 权限.
配置加密: 入库前加密敏感字段, 出库时解密 (需权限校验).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    require_permission,
    require_project_role,
    GLOBAL_ADMIN_ROLES,
    get_user_global_roles,
)
from app.api.schemas import DataSourceCreate, DataSourceResponse
from app.core.database import get_db
from app.core.crypto import encrypt_config, decrypt_config
from app.models.user import User
from app.models.datasource import DataSource
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/api/v1/datasources", tags=["DataSources"])


@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(
    project_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据源列表，可按项目筛选."""
    stmt = select(DataSource)
    if project_id:
        stmt = stmt.where(DataSource.project_id == project_id)
    stmt = stmt.order_by(DataSource.created_at.desc())
    result = await db.execute(stmt)
    datasources = result.scalars().all()

    # 脱敏: 返回时移除敏感字段的明文
    responses = []
    for ds in datasources:
        safe_config = {**ds.config}
        for key in ("password", "secret", "token", "access_key", "private_key", "api_key"):
            if key in safe_config:
                safe_config[key] = "***"
        responses.append(DataSourceResponse(
            id=ds.id,
            project_id=ds.project_id,
            name=ds.name,
            source_type=ds.source_type,
            config=safe_config,
            status=ds.status,
            last_sync_at=ds.last_sync_at,
            created_at=ds.created_at,
        ))
    return responses


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(
    req: DataSourceCreate,
    current_user: User = Depends(get_current_user),
    _: User | None = Depends(require_project_role("project_owner", "editor")),
    db: AsyncSession = Depends(get_db),
):
    """注册新数据源 — 自动加密敏感配置."""
    # 加密敏感字段
    encrypted_config = encrypt_config(req.config)

    ds = DataSource(
        project_id=req.project_id,
        name=req.name,
        source_type=req.source_type,
        config=encrypted_config,
        description=req.description,
    )
    db.add(ds)
    await db.flush()
    await db.refresh(ds)

    # 审计日志
    db.add(AuditLog(
        user_id=current_user.id,
        project_id=req.project_id,
        resource="datasource",
        action="create",
        target_id=ds.id,
        target_name=ds.name,
        detail={"source_type": req.source_type},
    ))

    await db.commit()

    # 返回时脱敏
    safe_config = {**ds.config}
    for key in ("password", "secret", "token", "access_key", "private_key", "api_key"):
        if key in safe_config:
            safe_config[key] = "***"

    return DataSourceResponse(
        id=ds.id,
        project_id=ds.project_id,
        name=ds.name,
        source_type=ds.source_type,
        config=safe_config,
        status=ds.status,
        last_sync_at=ds.last_sync_at,
        created_at=ds.created_at,
    )


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除数据源 — 需要 datasource:delete 权限 + project_owner 角色."""
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 权限校验: 检查用户是否有 datasource:delete 权限
    from app.api.deps import get_user_permissions
    perms = await get_user_permissions(current_user.id, db)
    if "datasource:delete" not in perms:
        raise HTTPException(status_code=403, detail="需要权限: datasource:delete")

    # 角色校验: 检查项目中的角色
    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        from app.models.role import Role
        member_result = await db.execute(
            select(PM, Role)
            .join(Role, Role.id == PM.role_id)
            .where(
                PM.project_id == ds.project_id,
                PM.user_id == current_user.id,
            )
        )
        row = member_result.one_or_none()
        if not row:
            raise HTTPException(status_code=403, detail="你不是该项目成员")
        _, role = row
        if role.name not in ("project_owner",):
            raise HTTPException(status_code=403, detail="需要 project_owner 角色才能删除数据源")

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=ds.project_id,
        resource="datasource",
        action="delete",
        target_id=ds_id,
        target_name=ds.name,
    ))

    await db.delete(ds)
    await db.commit()
    return {"message": "数据源已删除"}


# 支持的数据源类型 (对标 DataWorks 50+ 连接器)
SUPPORTED_SOURCE_TYPES = [
    {"type": "mysql", "label": "MySQL", "category": "关系型数据库"},
    {"type": "postgresql", "label": "PostgreSQL", "category": "关系型数据库"},
    {"type": "mongodb", "label": "MongoDB", "category": "NoSQL"},
    {"type": "redis", "label": "Redis", "category": "NoSQL"},
    {"type": "kafka", "label": "Kafka", "category": "消息队列"},
    {"type": "elasticsearch", "label": "Elasticsearch", "category": "搜索引擎"},
    {"type": "s3", "label": "S3/MinIO", "category": "对象存储"},
    {"type": "hdfs", "label": "HDFS", "category": "大数据存储"},
    {"type": "hive", "label": "Hive", "category": "数据仓库"},
    {"type": "clickhouse", "label": "ClickHouse", "category": "OLAP"},
    {"type": "doris", "label": "Doris/StarRocks", "category": "OLAP"},
    {"type": "api", "label": "REST API", "category": "外部接口"},
    {"type": "crawler", "label": "网页爬虫", "category": "数据采集"},
    {"type": "file", "label": "文件上传 (CSV/Excel/JSON)", "category": "本地文件"},
]


@router.get("/types", response_model=list[dict])
async def get_source_types():
    """获取支持的数据源类型列表."""
    return SUPPORTED_SOURCE_TYPES
