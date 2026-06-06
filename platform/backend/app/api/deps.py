"""FastAPI 依赖注入 — JWT 认证 + RBAC 权限守卫.

权限模型:
  用户最终权限 = 全局角色权限 (user_roles) ∪ 项目角色权限 (project_members)

守卫类型:
  get_current_user              — 解析 JWT, 返回 User
  get_current_active_superuser  — 要求 is_superuser
  require_permission(perm)      — 要求特定 resource:action 权限
  require_project_role(*roles)  — 要求特定项目角色 (admin 全局穿透)

v1.5 新增:
  PermissionCache              — Redis 权限缓存, 角色变更时主动失效
  get_redis                    — Redis 客户端依赖注入
"""

import logging
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

logger = logging.getLogger(__name__)

# Bearer Token 提取器
bearer_scheme = HTTPBearer(auto_error=False)

# ============================================================
# 角色层级常量 (v2.0 对齐 DataWorks 专业版)
# ============================================================
ROLE_LEVEL: dict[str, float] = {
    "viewer": 1,
    "editor": 1.5,
    "operator": 2,
    "developer": 2.5,
    "project_admin": 3,
    "project_owner": 4,
    "admin": 5,
    "super_admin": 6,
}
GLOBAL_ADMIN_ROLES: set[str] = {"super_admin", "admin"}


# ============================================================
# Redis 客户端 (v1.5 新增)
# ============================================================

_redis_client = None


async def get_redis():
    """获取 Redis 客户端 (惰性初始化, 连接失败时返回 None)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis_client.ping()
        logger.info("Redis 权限缓存已连接")
    except Exception as e:
        logger.warning(f"Redis 不可用, 权限缓存禁用: {e}")
        _redis_client = None

    return _redis_client


# ============================================================
# 权限缓存 (v1.5 新增: Redis 缓存避免每次请求 DB JOIN)
# ============================================================

class PermissionCache:
    """权限结果缓存 — 角色变更时主动失效.

    Key 设计:
      perm:user:{user_id}              → Set<permission_name>   (全局权限, TTL 30min)
      perm:user:{user_id}:proj:{pid}   → Set<permission_name>   (项目权限, TTL 15min)

    失效时机:
      - 用户全局角色变更 → invalidate_user(uid)
      - 项目成员增删/角色变更 → invalidate_project_member(uid, pid)
      - 角色权限绑定变更 → 短 TTL 自然过期
    """

    GLOBAL_TTL = 1800   # 30 分钟
    PROJECT_TTL = 900   # 15 分钟

    def __init__(self, redis_client):
        self.redis = redis_client

    @staticmethod
    def _global_key(user_id: int) -> str:
        return f"perm:user:{user_id}"

    @staticmethod
    def _project_key(user_id: int, project_id: int) -> str:
        return f"perm:user:{user_id}:proj:{project_id}"

    async def get(self, user_id: int, project_id: int | None = None) -> set[str] | None:
        """从缓存获取权限集合, 未命中返回 None."""
        if self.redis is None:
            return None
        try:
            key = self._project_key(user_id, project_id) if project_id else self._global_key(user_id)
            data = await self.redis.get(key)
            if data:
                return set(data.split(","))
        except Exception:
            pass
        return None

    async def set(self, user_id: int, permissions: set[str], project_id: int | None = None):
        """回填权限缓存."""
        if self.redis is None:
            return
        try:
            key = self._project_key(user_id, project_id) if project_id else self._global_key(user_id)
            ttl = self.PROJECT_TTL if project_id else self.GLOBAL_TTL
            await self.redis.setex(key, ttl, ",".join(sorted(permissions)))
        except Exception:
            pass

    async def invalidate_user(self, user_id: int):
        """删除用户所有权限缓存 (全局角色变更时调用)."""
        if self.redis is None:
            return
        try:
            keys = await self.redis.keys(f"perm:user:{user_id}*")
            if keys:
                await self.redis.delete(*keys)
        except Exception:
            pass

    async def invalidate_project_member(self, user_id: int, project_id: int):
        """删除用户在特定项目的权限缓存."""
        if self.redis is None:
            return
        try:
            await self.redis.delete(self._project_key(user_id, project_id))
        except Exception:
            pass


# 全局缓存实例 (惰性初始化)
_perm_cache: PermissionCache | None = None


async def get_perm_cache() -> PermissionCache | None:
    """获取权限缓存实例."""
    global _perm_cache
    if _perm_cache is None:
        redis = await get_redis()
        _perm_cache = PermissionCache(redis)
    return _perm_cache if _perm_cache.redis else None


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
      1. 优先从 Redis 缓存读取
      2. 未命中: 查 user_roles + project_members → 权限名集合
      3. 回填缓存

    v1.5: Redis 缓存加速, 角色变更时主动失效.
    """
    # 1. 尝试缓存命中
    perm_cache = await get_perm_cache()
    if perm_cache:
        cached = await perm_cache.get(user_id, project_id)
        if cached is not None:
            return cached

    # 2. 缓存未命中, 查 DB
    perm_names: set[str] = set()

    # 2a. 全局角色权限
    global_perms = await db.execute(
        select(Permission.name)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    perm_names.update(p[0] for p in global_perms.all())

    # 2b. 项目级角色权限
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

    # 3. 回填缓存
    if perm_cache:
        await perm_cache.set(user_id, perm_names, project_id)

    return perm_names


async def invalidate_user_permission_cache(user_id: int, project_id: int | None = None):
    """失效用户权限缓存 (角色变更后调用)."""
    perm_cache = await get_perm_cache()
    if perm_cache:
        if project_id:
            await perm_cache.invalidate_project_member(user_id, project_id)
        else:
            await perm_cache.invalidate_user(user_id)


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
