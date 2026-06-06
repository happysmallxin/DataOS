"""审计日志模型 — 合规核心，记录所有敏感操作.

对标 DataWorks 操作审计:
  - 谁 (user_id) 在什么时间 (created_at) 从哪 (ip_address)
  - 对什么资源 (resource) 做了什么操作 (action)
  - 操作前后的变化 (detail JSON)
"""

from datetime import datetime

from sqlalchemy import (
    String, Text, DateTime, func, ForeignKey, JSON, Integer
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """操作审计日志."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resource: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # project / datasource / member / role / permission
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # create / update / delete / grant / revoke / transfer
    target_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 操作对象 ID
    target_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )  # 操作对象名称 (冗余便于查询)
    detail: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # 变更详情 (before/after diff)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(user={self.user_id}, {self.resource}:{self.action}, "
            f"target={self.target_id})>"
        )
