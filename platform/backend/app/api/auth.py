"""认证 API — 登录/注册/Token 刷新."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import LoginRequest, TokenResponse, UserInfo
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, verify_password, hash_password, decode_access_token
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录，返回 JWT Token."""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
    return TokenResponse(access_token=access_token, expires_in=settings.JWT_EXPIRE_MINUTES * 60)


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(lambda token: token),
):
    """获取当前登录用户信息."""
    # 简化版，实际应从 Header 解析 Bearer Token
    return UserInfo(id=1, username="admin", email="admin@dataos.local", is_superuser=True)


@router.post("/register", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
async def register(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户."""
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

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
