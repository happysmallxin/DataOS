"""清洗 Pipeline 持久化模型 — P1: 项目级 Pipeline 存储.

对标 DataWorks 数据开发中的节点配置持久化.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CleaningPipeline(Base):
    """项目级数据清洗 Pipeline — 持久化存储, project_id 隔离."""

    __tablename__ = "cleaning_pipelines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Pipeline 描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 阶段定义 JSON: [{"type": "standardize", "config": {...}}, ...]
    stages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 状态: draft / active / archived
    status: Mapped[str] = mapped_column(String(32), default="draft")
    # 版本号 (每次更新递增)
    version: Mapped[int] = mapped_column(default=1)
    # 最后执行时间
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 创建者
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_pipeline_project_name"),
    )

    def __repr__(self) -> str:
        return f"<CleaningPipeline(id={self.id}, name='{self.name}', version={self.version})>"
