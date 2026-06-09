"""模型表 + 模型字段 + 模型版本 — 数据建模核心 (对齐 MES 文档 §5)."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, UniqueConstraint, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ModelTable(Base):
    """模型表定义 — DIM/FACT/DWD/DWS/ADS."""

    __tablename__ = "model_tables"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    process_id: Mapped[Optional[int]] = mapped_column(ForeignKey("business_processes.id", ondelete="SET NULL"), nullable=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("data_domains.id", ondelete="RESTRICT"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    table_type: Mapped[str] = mapped_column(String(32), default="DIM")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_key_field: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_gold_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    target_gold_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    relation_data: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_model_code"),)


class ModelField(Base):
    """模型字段字典."""

    __tablename__ = "model_fields"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_table_id: Mapped[int] = mapped_column(ForeignKey("model_tables.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(String(64), default="VARCHAR")
    length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False)
    ref_table: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ref_field: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_field: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="dimension")
    quality_rule: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    standard_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_standards.id", ondelete="SET NULL"), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
