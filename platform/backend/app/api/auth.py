"""认证 API — 登录/注册/Token 刷新.

P1 增强: 登录接口直接返回用户权限列表和可访问项目，避免前端多次请求.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_user_permissions,
    get_user_global_roles,
    GLOBAL_ADMIN_ROLES,
)
from app.api.schemas import (
    LoginRequest,
    TokenResponse,
    LoginUserInfo,
    UserInfo,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    verify_password,
    hash_password,
)
from app.models.user import User
from app.models.project import Project
from app.models.role import Role
from app.models.project_member import ProjectMember

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录 — 返回 JWT Token + 用户权限信息."""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁用",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    # P1 增强: 获取用户全局角色和权限
    global_roles = await get_user_global_roles(user.id, db)
    permissions = await get_user_permissions(user.id, db)
    is_global_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)

    # 获取可访问的项目列表
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
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .join(Role, Role.id == ProjectMember.role_id)
            .where(
                ProjectMember.user_id == user.id,
                Project.status == "active",
            )
        )
        accessible_projects = [
            {"id": p.id, "name": p.name, "display_name": p.display_name, "role": role_name}
            for p, role_name in proj_result.all()
        ]

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
        user=LoginUserInfo(
            id=user.id,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            is_superuser=user.is_superuser,
            global_roles=[r.name for r in global_roles],
            permissions=sorted(permissions),
            accessible_projects=accessible_projects,
        ),
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取当前登录用户信息."""
    return current_user


@router.post("/register", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
async def register(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户."""
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    user = User(
        username=req.username,
        email=f"{req.username}@dataos.local",
        hashed_password=hash_password(req.password),
        display_name=req.username,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
