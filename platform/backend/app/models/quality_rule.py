"""质量规则持久化模型 — P1: 项目级质量规则存储.

对标 DataWorks 数据质量规则管理.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func, ForeignKey, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QualityRule(Base):
    """项目级数据质量规则 — 持久化存储, project_id 隔离."""

    __tablename__ = "quality_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 规则类型: not_null / range / regex / unique / custom_sql
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # 目标列名 (可选, not_null 等不需要)
    target_column: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 规则配置 JSON: {"min": 0, "max": 100} 或 {"pattern": "^[A-Z]+$"} 或 {"condition": "col > 0"}
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 规则描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 是否启用
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
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
        UniqueConstraint("project_id", "name", name="uq_quality_rule_project_name"),
    )

    def __repr__(self) -> str:
        return f"<QualityRule(id={self.id}, name='{self.name}', type='{self.rule_type}')>"
