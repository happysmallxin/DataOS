"""数据源模型 — 对标 DataWorks 全域数据集成."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from app.core.database import Base


class DataSource(Base):
    """数据源注册信息."""

    __tablename__ = "datasources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 数据源类型: mysql, postgresql, mongodb, kafka, api, s3, crawler, file 等
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # 连接配置 (加密存储)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    # Sync / Error / Disabled
    status: Mapped[str] = mapped_column(String(32), default="active")
    # 最后同步时间
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_datasource_project_name"),
    )

    def __repr__(self) -> str:
        return f"<DataSource(id={self.id}, name='{self.name}', type='{self.source_type}')>"
