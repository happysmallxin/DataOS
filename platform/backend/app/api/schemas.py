"""Pydantic 请求/响应 Schemas — 对标 DataWorks API 设计."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# Auth
# ============================================================
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    is_superuser: bool

    model_config = {"from_attributes": True}


# ============================================================
# Project
# ============================================================
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    display_name: str = Field(..., max_length=256)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    owner_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# DataSource
# ============================================================
class DataSourceCreate(BaseModel):
    project_id: int = Field(default=1)
    name: str = Field(..., max_length=128)
    source_type: str = Field(..., max_length=64)
    config: dict
    description: Optional[str] = None


class DataSourceResponse(BaseModel):
    id: int
    project_id: int
    name: str
    source_type: str
    config: dict
    status: str
    last_sync_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# Platform Status (统一下游服务健康检查)
# ============================================================
class ComponentStatus(BaseModel):
    name: str
    url: str
    healthy: bool
    message: Optional[str] = None


class PlatformHealthResponse(BaseModel):
    status: str  # healthy / degraded / down
    version: str
    components: list[ComponentStatus]
