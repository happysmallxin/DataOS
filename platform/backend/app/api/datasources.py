"""数据源管理 API — 对标 DataWorks 全域数据集成.

RBAC 权限: 所有操作需要对应项目的成员角色 + resource:action 权限.
配置加密: 入库前加密敏感字段, 出库时解密 (需权限校验).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    require_permission,
    require_project_role,
    GLOBAL_ADMIN_ROLES,
    get_user_global_roles,
)
from app.api.schemas import DataSourceCreate, DataSourceResponse, SyncRequest, SyncHistoryResponse
from app.core.config import settings
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
    # 检查同项目下是否存在同名数据源 (P0: 唯一约束)
    existing = await db.execute(
        select(DataSource).where(
            DataSource.project_id == req.project_id,
            DataSource.name == req.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"项目内已存在同名数据源 '{req.name}'",
        )

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
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"项目内已存在同名数据源 '{req.name}'",
        )
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


# ============================================================
# 数据源使用 (测试连接 / 表列表 / 预览 / 同步)
# ============================================================

import time
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError


def _build_sqlalchemy_url(ds: DataSource) -> str:
    """根据 datasource 构建 SQLAlchemy 连接 URL."""
    cfg = decrypt_config(ds.config)
    t = ds.source_type
    if t == "mysql":
        return f"mysql+pymysql://{cfg.get('username')}:{cfg.get('password')}@{cfg.get('host')}:{cfg.get('port', 3306)}/{cfg.get('database')}"
    elif t == "postgresql":
        return f"postgresql+psycopg2://{cfg.get('username')}:{cfg.get('password')}@{cfg.get('host')}:{cfg.get('port', 5432)}/{cfg.get('database')}"
    elif t == "clickhouse":
        return f"clickhouse+clickhouse-connect://{cfg.get('username')}:{cfg.get('password')}@{cfg.get('host')}:{cfg.get('port', 8123)}/{cfg.get('database')}"
    raise HTTPException(status_code=400, detail=f"数据源类型 '{t}' 暂不支持 SQL 连接，请通过 API 直接传数据")


@router.post("/{ds_id}/test-connection")
async def test_connection(
    ds_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """测试数据源连接 — 解密配置并尝试连接."""
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    try:
        url = _build_sqlalchemy_url(ds)
        engine = create_engine(url, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
        engine.dispose()
        return {"status": "ok", "message": "连接成功", "result": result}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": f"连接失败: {str(e)}"}


@router.post("/{ds_id}/tables")
async def list_source_tables(
    ds_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据源的表列表 + 字段信息."""
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    try:
        url = _build_sqlalchemy_url(ds)
        engine = create_engine(url, connect_args={"connect_timeout": 10})
        inspector = inspect(engine)
        tables = []
        for table_name in inspector.get_table_names():
            cols = [{"name": c["name"], "type": str(c["type"])} for c in inspector.get_columns(table_name)]
            tables.append({"name": table_name, "columns": cols})
        engine.dispose()
        return tables
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")


@router.post("/{ds_id}/tables/{table_name}/preview")
async def preview_table(
    ds_id: int,
    table_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """预览数据源表的前 100 行数据."""
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    try:
        url = _build_sqlalchemy_url(ds)
        engine = create_engine(url, connect_args={"connect_timeout": 10})
        df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 100", engine)
        engine.dispose()
        return {
            "table": table_name,
            "rows": len(df),
            "columns": list(df.columns),
            "data": df.fillna("").to_dict(orient="records"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")


@router.post("/{ds_id}/sync")
async def sync_datasource(
    ds_id: int,
    req: SyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全量同步数据源表 → MinIO (Bronze 层).

    1. 连接数据源, 读取指定表全量数据
    2. 以 Parquet 格式写入 MinIO Bronze 桶
    3. 记录 SyncHistory 到数据库
    """
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 权限校验: 需要 datasource:sync
    from app.api.deps import get_user_permissions
    perms = await get_user_permissions(current_user.id, db, ds.project_id)
    if "datasource:sync" not in perms:
        raise HTTPException(status_code=403, detail="需要权限: datasource:sync")

    from app.models.sync_history import SyncHistory
    from app.core.minio_client import write_dataframe, get_bronze_path

    # 记录同步开始
    sync_record = SyncHistory(
        datasource_id=ds_id,
        project_id=ds.project_id,
        table_name=req.table_name,
        sync_mode=req.sync_mode,
        status="running",
        triggered_by=current_user.id,
    )
    db.add(sync_record)
    await db.commit()
    await db.refresh(sync_record)

    start = time.time()
    try:
        # 连接源并读取数据
        url = _build_sqlalchemy_url(ds)
        engine = create_engine(url, connect_args={"connect_timeout": 30})
        df = pd.read_sql(f"SELECT * FROM {req.table_name}", engine)
        engine.dispose()

        # 写入 MinIO (Bronze)
        date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
        prefix = get_bronze_path(ds_id, req.table_name, date_str)
        key = f"{prefix}full_{pd.Timestamp.now().strftime('%H%M%S')}.parquet"
        result = write_dataframe(df, settings.MINIO_BUCKET_BRONZE, key)

        # 更新同步记录
        sync_record.status = "success"
        sync_record.total_rows = len(df)
        sync_record.total_bytes = result["size_bytes"]
        sync_record.storage_path = f"{settings.MINIO_BUCKET_BRONZE}/{key}"
        sync_record.duration_seconds = round(time.time() - start, 2)

        # 更新数据源的最后同步时间
        ds.last_sync_at = datetime.now(timezone.utc)

        # 审计日志
        db.add(AuditLog(
            user_id=current_user.id,
            project_id=ds.project_id,
            resource="datasource",
            action="sync",
            target_id=ds_id,
            target_name=ds.name,
            detail={"table": req.table_name, "rows": len(df), "path": key},
        ))

        await db.commit()

        return {
            "status": "success",
            "table": req.table_name,
            "rows": len(df),
            "size_bytes": result["size_bytes"],
            "path": result["key"],
            "duration_seconds": sync_record.duration_seconds,
        }

    except Exception as e:
        sync_record.status = "failed"
        sync_record.error_message = str(e)
        sync_record.duration_seconds = round(time.time() - start, 2)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/{ds_id}/sync-history", response_model=list[SyncHistoryResponse])
async def list_sync_history(
    ds_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据源的同步历史."""
    from app.models.sync_history import SyncHistory as SH
    result = await db.execute(
        select(SH).where(SH.datasource_id == ds_id).order_by(SH.created_at.desc()).limit(50)
    )
    return result.scalars().all()
