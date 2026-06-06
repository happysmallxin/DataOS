"""FastAPI 依赖注入 — JWT 认证 + RBAC 权限守卫.

权限模型:
  用户最终权限 = 全局角色权限 (user_roles) ∪ 项目角色权限 (project_members)

守卫类型:
  get_current_user              — 解析 JWT, 返回 User
  get_current_active_superuser  — 要求 is_superuser
  require_permission(perm)      — 要求特定 resource:action 权限
  require_project_role(*roles)  — 要求特定项目角色 (admin 全局穿透)
"""

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.role import Role, Permission, RolePermission
from app.models.project_member import ProjectMember, UserRole

# Bearer Token 提取器
bearer_scheme = HTTPBearer(auto_error=False)

# ============================================================
# 角色层级常量
# ============================================================
ROLE_LEVEL: dict[str, int] = {
    "viewer": 1,
    "editor": 2,
    "project_owner": 3,
    "admin": 4,
    "super_admin": 5,
}
GLOBAL_ADMIN_ROLES: set[str] = {"super_admin", "admin"}


# ============================================================
# 认证依赖
# ============================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Token 解析当前用户 (所有受保护接口的依赖).

    用法:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            ...
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )

    user_id = int(payload.get("sub", 0))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户不存在或已被禁用",
        )

    return user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求超级用户权限."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


# ============================================================
# RBAC 权限查询
# ============================================================

async def get_user_global_roles(
    user_id: int, db: AsyncSession
) -> list[Role]:
    """获取用户全局角色列表."""
    result = await db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_user_permissions(
    user_id: int,
    db: AsyncSession,
    project_id: int | None = None,
) -> set[str]:
    """获取用户最终权限集合 = 全局角色权限 ∪ 项目角色权限.

    合并逻辑:
      1. 查 user_roles → 全局 roles → role_permissions → 权限名集合
      2. 如果指定 project_id: 查 project_members.role_id → 权限名集合
      3. 取并集
    """
    perm_names: set[str] = set()

    # 1. 全局角色权限
    global_perms = await db.execute(
        select(Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    perm_names.update(p[0] for p in global_perms.all())

    # 2. 项目级角色权限
    if project_id:
        project_perms = await db.execute(
            select(Permission.name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(ProjectMember, ProjectMember.role_id == RolePermission.role_id)
            .where(
                ProjectMember.user_id == user_id,
                ProjectMember.project_id == project_id,
            )
        )
        perm_names.update(p[0] for p in project_perms.all())

    return perm_names


# ============================================================
# 权限守卫工厂
# ============================================================

def require_permission(permission: str):
    """权限守卫工厂 — 检查当前用户是否拥有指定权限.

    用法:
      @router.post("/projects")
      async def create_project(
          req: ProjectCreate,
          current_user: User = Depends(require_permission("project:create")),
          db: AsyncSession = Depends(get_db),
      ):
          ...
    """
    async def checker(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        perms = await get_user_permissions(current_user.id, db)
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要权限: {permission}",
            )
        return current_user

    return checker


def require_project_role(*min_roles: str):
    """项目角色守卫工厂 — 需要特定项目角色才能访问.

    P0 修复: 先查全局角色 (admin/super_admin 直接放行), 再查项目成员.

    用法:
      @router.delete("/projects/{project_id}")
      async def delete_project(
          project_id: int,
          member: ProjectMember = Depends(require_project_role("project_owner")),
          db: AsyncSession = Depends(get_db),
      ):
          ...
    """
    async def checker(
        project_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        # ✅ 先查全局角色 — admin/super_admin 直接放行
        global_roles = await get_user_global_roles(current_user.id, db)
        global_role_names = {r.name for r in global_roles}
        if global_role_names & GLOBAL_ADMIN_ROLES:
            return None  # 全局管理员, 不需要项目成员记录

        # ✅ 再查项目成员身份
        result = await db.execute(
            select(ProjectMember, Role)
            .join(Role, Role.id == ProjectMember.role_id)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="你不是该项目成员",
            )

        member, role = row
        min_level = min(ROLE_LEVEL.get(r, 0) for r in min_roles)
        user_level = ROLE_LEVEL.get(role.name, 0)

        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 {'/'.join(min_roles)} 角色, 当前: {role.display_name}",
            )
        return member

    return checker
