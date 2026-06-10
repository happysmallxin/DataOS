"""数据集模型 — 版本化数据资产 (对齐 MES 文档 §6)."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Dataset(Base):
    """数据集定义."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_domains.id", ondelete="SET NULL"), nullable=True)
    model_table_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # 包含的模型表ID列表
    output_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)     # 输出字段配置
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    update_cycle: Mapped[str] = mapped_column(String(64), default="once")  # daily/weekly/monthly/once
    export_format: Mapped[str] = mapped_column(String(64), default="parquet")
    storage_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    total_rows: Mapped[int] = mapped_column(default=0)
    total_size_bytes: Mapped[int] = mapped_column(default=0)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class DatasetVersion(Base):
    """数据集版本."""

    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    total_rows: Mapped[int] = mapped_column(default=0)
    total_size_bytes: Mapped[int] = mapped_column(default=0)
    storage_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    quality_report: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    changelog: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
