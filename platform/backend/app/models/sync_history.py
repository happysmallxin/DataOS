"""数据同步历史模型 — 记录每次数据源同步操作."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SyncHistory(Base):
    """数据源同步记录."""

    __tablename__ = "sync_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    datasource_id: Mapped[int] = mapped_column(
        ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 同步的表名
    table_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 同步模式: full / incremental
    sync_mode: Mapped[str] = mapped_column(String(32), default="full")
    # 同步状态: running / success / failed
    status: Mapped[str] = mapped_column(String(32), default="running")
    # 同步结果
    total_rows: Mapped[int] = mapped_column(default=0)
    total_bytes: Mapped[int] = mapped_column(default=0)
    # MinIO 存储路径
    storage_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 耗时 (秒)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    # 增量同步: 跟踪列 + 上次同步到的值
    sync_column: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_sync_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    # 操作人
    triggered_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return f"<SyncHistory(ds={self.datasource_id}, table={self.table_name}, rows={self.total_rows})>"
