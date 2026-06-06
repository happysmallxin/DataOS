"""Pydantic 请求/响应 Schemas — 对标 DataWorks API 设计."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Auth
# ============================================================
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str = ""       # v1.5: refresh token for token rotation
    token_type: str = "bearer"
    expires_in: int
    user: Optional["LoginUserInfo"] = None  # P1 增强: 登录直接返回权限信息


class RefreshTokenRequest(BaseModel):
    """Token 刷新请求 (v1.5 新增)."""
    refresh_token: str = Field(..., description="refresh token")


class LoginUserInfo(BaseModel):
    """登录时返回的用户信息 + 权限."""
    id: int
    username: str
    email: str
    display_name: Optional[str] = None
    is_superuser: bool
    global_roles: list[str] = []
    permissions: list[str] = []
    accessible_projects: list[dict] = []


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
    name: str = Field(..., min_length=2, max_length=128, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(..., max_length=256)
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class ProjectUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    owner_id: int
    status: str
    tags: Optional[list[str]] = None
    member_count: int = 0
    datasource_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedProjectResponse(BaseModel):
    """分页项目列表响应 (v1.5 新增)."""
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProjectTransferRequest(BaseModel):
    """项目转让请求."""
    new_owner_id: int = Field(..., description="新负责人的用户 ID (必须已是项目成员)")


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


# ============================================================
# RBAC — Role & Permission
# ============================================================
class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z_]+$")
    display_name: str = Field(..., max_length=128)
    description: Optional[str] = None
    scope: str = Field(default="project")  # global / project


class RoleUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    scope: str
    is_system: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PermissionResponse(BaseModel):
    id: int
    name: str
    resource: str
    action: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ============================================================
# RBAC — Project Member
# ============================================================
class ProjectMemberAdd(BaseModel):
    user_id: int
    role_id: int  # FK → roles.id


class ProjectMemberUpdate(BaseModel):
    role_id: int  # FK → roles.id


class ProjectMemberResponse(BaseModel):
    id: int
    user_id: int
    username: str
    email: str = ""
    role_id: int
    role_name: str       # 冗余: "project_owner" / "editor" / "viewer"
    role_display: str     # 冗余: "项目负责人" / "编辑者" / "查看者"
    joined_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# RBAC — User Role & Permissions
# ============================================================
class UserRoleAssign(BaseModel):
    role_id: int = Field(..., description="全局角色 ID")


class UserPermissionsResponse(BaseModel):
    user_id: int
    username: str
    global_roles: list[str]
    permissions: list[str]
    accessible_projects: list[dict] = []


# ============================================================
# Audit Log
# ============================================================
class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    username: str = ""
    project_id: Optional[int] = None
    resource: str
    action: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    detail: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditLogResponse]


# ============================================================
# User Search (v1.5 新增)
# ============================================================
class UserSearchResult(BaseModel):
    """用户搜索结果 (成员管理自动完成)."""
    id: int
    username: str
    email: str
    display_name: Optional[str] = None


# ============================================================
# Quality Check (复用)
# ============================================================
class QualityCheckRequest(BaseModel):
    """质量检查请求."""
    data: list[dict] = Field(..., description="待检查的数据 (JSON 行)")
    rules: list[dict] = Field(..., description="质量规则列表")


class QualityCheckResponse(BaseModel):
    """质量检查响应."""
    total_rules: int
    passed_rules: int
    failed_rules: int
    overall_pass_rate: float
    results: list[dict]


# ============================================================
# Quality Rule (P1: 持久化存储)
# ============================================================
class QualityRuleCreate(BaseModel):
    project_id: int
    name: str = Field(..., max_length=128)
    rule_type: str = Field(..., max_length=32, description="not_null/range/regex/unique/custom_sql")
    target_column: Optional[str] = None
    config: dict = Field(default_factory=dict)
    description: Optional[str] = None


class QualityRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    target_column: Optional[str] = None
    config: Optional[dict] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class QualityRuleResponse(BaseModel):
    id: int
    project_id: int
    name: str
    rule_type: str
    target_column: Optional[str] = None
    config: dict
    description: Optional[str] = None
    is_enabled: bool
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# Cleaning Pipeline (P1: 持久化存储)
# ============================================================
class PipelineCreate(BaseModel):
    project_id: int
    datasource_id: Optional[int] = None       # 关联数据源
    source_table: Optional[str] = None         # 源表名
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    stages: list[dict] = Field(default_factory=list, description="阶段定义列表")
    target_table: Optional[str] = None         # 输出目标 PG 表名


class PipelineUpdate(BaseModel):
    datasource_id: Optional[int] = None
    source_table: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    stages: Optional[list[dict]] = None
    target_table: Optional[str] = None
    status: Optional[str] = None


class PipelineResponse(BaseModel):
    id: int
    project_id: int
    datasource_id: Optional[int] = None
    source_table: Optional[str] = None
    name: str
    description: Optional[str] = None
    stages: list[dict]
    status: str
    version: int
    target_table: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_output_rows: int = 0
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PipelineListResponse(BaseModel):
    items: list[PipelineResponse]
    total: int


# ============================================================
# Sync / Datasource Usage (数据源使用)
# ============================================================
class TableInfo(BaseModel):
    """表信息."""
    name: str
    rows_estimate: Optional[int] = None
    columns: list[dict] = []


class SyncRequest(BaseModel):
    """同步请求."""
    table_name: str = Field(..., description="要同步的表名")
    sync_mode: str = Field(default="full", description="full / incremental")


class SyncHistoryResponse(BaseModel):
    id: int
    datasource_id: int
    project_id: int
    table_name: str
    sync_mode: str
    status: str
    total_rows: int
    total_bytes: int
    storage_path: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}
