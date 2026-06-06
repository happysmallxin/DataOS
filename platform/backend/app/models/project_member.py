"""项目成员与用户全局角色模型.

双维度角色分配:
  UserRole        — 全局角色 (平台级, scope=global)
  ProjectMember   — 项目角色 (项目级, scope=project)
"""

from datetime import datetime

from sqlalchemy import String, DateTime, func, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectMember(Base):
    """项目成员 — 用户在某项目中的角色.

    owner_id (projects 表) 仅记录创建者, 不可变, 用于审计溯源.
    项目权限完全由此表决定.
    """

    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"), nullable=False, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    invited_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectMember(project={self.project_id}, user={self.user_id}, "
            f"role={self.role_id})>"
        )


class UserRole(Base):
    """用户全局角色 — 平台级角色分配 (scope=global 的 role)."""

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )

    def __repr__(self) -> str:
        return f"<UserRole(user={self.user_id}, role={self.role_id})>"
