"""数据域与业务过程模型 — Phase 3: 数据建模 (对齐 Dataphin OneData)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataDomain(Base):
    """数据域 — 树形层级, project 隔离."""

    __tablename__ = "data_domains"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_domains.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_domain_project_name"),)


class BusinessProcess(Base):
    """业务过程 — 归属于数据域, project 隔离."""

    __tablename__ = "business_processes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("data_domains.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source_tables: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    target_tables: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    table_type: Mapped[str] = mapped_column(String(32), default="DWD")  # DIM/FACT/DWD/DWS/ADS
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_process_project_name"),)
