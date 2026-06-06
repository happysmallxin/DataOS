"""RBAC 权限管理 API — 角色 CRUD + 权限查询 + 用户角色分配.

端点:
  # 角色管理 (admin only)
  GET    /api/v1/roles                          角色列表 (支持 ?scope=project 筛选)
  POST   /api/v1/roles                          创建自定义角色
  PUT    /api/v1/roles/{id}                     更新角色
  DELETE /api/v1/roles/{id}                     删除角色 (is_system=false 才可删)
  GET    /api/v1/roles/{id}/permissions         查看角色绑定的权限

  # 权限查询
  GET    /api/v1/permissions                    权限列表 (支持 ?resource= 筛选)
  GET    /api/v1/users/me/permissions           当前用户权限
  GET    /api/v1/users/{id}/permissions         查询某用户权限

  # 用户全局角色
  POST   /api/v1/users/{id}/roles               分配全局角色
  DELETE /api/v1/users/{id}/roles/{role_id}     撤销全局角色
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_active_superuser,
    get_user_permissions,
    get_user_global_roles,
    GLOBAL_ADMIN_ROLES,
)
from app.api.schemas import (
    RoleResponse,
    RoleCreate,
    RoleUpdate,
    PermissionResponse,
    UserRoleAssign,
    UserPermissionsResponse,
)
from app.core.database import get_db
from app.models.user import User
from app.models.role import Role, Permission, RolePermission
from app.models.project_member import UserRole

router = APIRouter(tags=["Permissions"])


# ============================================================
# 角色 CRUD
# ============================================================

@router.get("/api/v1/roles", response_model=list[RoleResponse])
async def list_roles(
    scope: str | None = Query(None, description="筛选作用域: global / project"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取角色列表."""
    stmt = select(Role).order_by(Role.scope, Role.id)
    if scope:
        stmt = stmt.where(Role.scope == scope)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/api/v1/roles", response_model=RoleResponse, status_code=201)
async def create_role(
    req: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_superuser),
):
    """创建自定义角色 (admin only)."""
    existing = await db.execute(select(Role).where(Role.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"角色 '{req.name}' 已存在")

    role = Role(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
        scope=req.scope,
        is_system=False,
    )
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return role


@router.put("/api/v1/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    req: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_superuser),
):
    """更新角色信息."""
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if req.display_name is not None:
        role.display_name = req.display_name
    if req.description is not None:
        role.description = req.description

    await db.flush()
    await db.refresh(role)
    return role


@router.delete("/api/v1/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_superuser),
):
    """删除角色 — is_system 角色不可删除."""
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统预置角色不可删除")

    await db.delete(role)
    await db.commit()
    return {"message": f"角色 '{role.name}' 已删除"}


@router.get("/api/v1/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """查看角色绑定的权限列表."""
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    result = await db.execute(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
        .order_by(Permission.resource, Permission.action)
    )
    perms = result.scalars().all()

    return {
        "role": RoleResponse.model_validate(role),
        "permissions": [PermissionResponse.model_validate(p) for p in perms],
    }


# ============================================================
# 权限查询
# ============================================================

@router.get("/api/v1/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    resource: str | None = Query(None, description="按资源筛选"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取权限列表 (所有用户可查看)."""
    stmt = select(Permission).order_by(Permission.resource, Permission.action)
    if resource:
        stmt = stmt.where(Permission.resource == resource)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/api/v1/users/me/permissions", response_model=UserPermissionsResponse)
async def get_my_permissions(
    project_id: int | None = Query(None, description="项目 ID, 传入则合并项目权限"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的权限列表 (前端据此渲染菜单/按钮)."""
    perms = await get_user_permissions(current_user.id, db, project_id)
    global_roles = await get_user_global_roles(current_user.id, db)

    # 获取可访问的项目
    is_global_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    from app.models.project import Project
    from app.models.project_member import ProjectMember as PM

    if is_global_admin:
        proj_result = await db.execute(
            select(Project).where(Project.status == "active")
        )
        accessible_projects = [
            {"id": p.id, "name": p.name, "display_name": p.display_name, "role": "admin"}
            for p in proj_result.scalars().all()
        ]
    else:
        proj_result = await db.execute(
            select(Project, Role.name)
            .join(PM, PM.project_id == Project.id)
            .join(Role, Role.id == PM.role_id)
            .where(PM.user_id == current_user.id, Project.status == "active")
        )
        accessible_projects = [
            {"id": p.id, "name": p.name, "display_name": p.display_name, "role": role_name}
            for p, role_name in proj_result.all()
        ]

    return UserPermissionsResponse(
        user_id=current_user.id,
        username=current_user.username,
        global_roles=[r.name for r in global_roles],
        permissions=sorted(perms),
        accessible_projects=accessible_projects,
    )


# ============================================================
# 用户全局角色分配
# ============================================================

@router.post("/api/v1/users/{user_id}/roles")
async def assign_user_role(
    user_id: int,
    req: UserRoleAssign,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_superuser),
):
    """分配全局角色给用户 (admin only)."""
    # 校验用户存在
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 校验角色存在且为 global scope
    role = await db.get(Role, req.role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.scope != "global":
        raise HTTPException(status_code=400, detail="只能分配全局角色")

    # 检查是否已有该角色
    existing = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == req.role_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户已有该角色")

    ur = UserRole(user_id=user_id, role_id=req.role_id)
    db.add(ur)
    await db.commit()
    return {"message": f"已为用户分配角色: {role.display_name}"}


@router.delete("/api/v1/users/{user_id}/roles/{role_id}")
async def revoke_user_role(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_superuser),
):
    """撤销用户全局角色 (admin only)."""
    result = await db.execute(
        delete(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == role_id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="用户没有该角色")
    await db.commit()
    return {"message": "角色已撤销"}
