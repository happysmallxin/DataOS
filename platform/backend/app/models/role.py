"""RBAC 角色与权限模型 — 对标 DataWorks 工作空间角色体系.

三表联动:
  roles ← role_permissions → permissions
  roles ← user_roles → users (全局角色)
  roles ← project_members → users (项目角色)
"""

from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, func, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Role(Base):
    """角色定义 — 系统预置 + 用户自定义."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )  # super_admin / admin / project_owner / editor / viewer
    display_name: Mapped[str] = mapped_column(
        String(128), nullable=False
    )  # 超级管理员 / 平台管理员 / 项目负责人
    description: Mapped[str | None] = mapped_column(String(256))
    scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="project"
    )  # global (平台级) / project (项目级)
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # True=系统预置不可删除
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}', scope='{self.scope}')>"


class Permission(Base):
    """权限定义 — resource:action 粒度."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )  # project:create / datasource:delete
    resource: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # user / role / project / datasource / crawler / quality / api / platform
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # create / read / update / delete / manage / execute / start / stop / publish
    description: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name='{self.name}')>"


class RolePermission(Base):
    """角色-权限关联 (M:N 中间表)."""

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )

    def __repr__(self) -> str:
        return f"<RolePermission(role={self.role_id}, perm={self.permission_id})>"
