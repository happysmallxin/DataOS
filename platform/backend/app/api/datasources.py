"""数据源管理 API — 对标 DataWorks 全域数据集成."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import DataSourceCreate, DataSourceResponse
from app.core.database import get_db
from app.models.datasource import DataSource

router = APIRouter(prefix="/api/v1/datasources", tags=["DataSources"])


@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(project_id: int | None = None, db: AsyncSession = Depends(get_db)):
    """获取数据源列表，可按项目筛选."""
    stmt = select(DataSource)
    if project_id:
        stmt = stmt.where(DataSource.project_id == project_id)
    stmt = stmt.order_by(DataSource.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(req: DataSourceCreate, db: AsyncSession = Depends(get_db)):
    """注册新数据源."""
    ds = DataSource(project_id=1, name=req.name, source_type=req.source_type, config=req.config, description=req.description)
    db.add(ds)
    await db.flush()
    await db.refresh(ds)
    return ds


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
