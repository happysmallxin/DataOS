"""清洗规则模板模型 — 可复用的 Pipeline stage 集合 (对齐 DataWorks 规则模板)."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, DateTime, func, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CleaningTemplate(Base):
    """清洗规则模板 — 创建一次, 多表复用."""

    __tablename__ = "cleaning_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 规则列表 JSON: [{"type":"not_null","column":"id"},{"type":"range","column":"temp","config":{"min":0,"max":100}}]
    stages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 自动排除的列名 (全局)
    exclude_columns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True,
        default=["hashed_password","password","secret","token","api_key","is_superuser"])
    created_by: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
