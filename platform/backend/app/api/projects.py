"""项目管理 API — 对标 DataWorks 工作空间.

端点:
  POST   /api/v1/projects                    创建项目
  GET    /api/v1/projects                    项目列表
  GET    /api/v1/projects/{id}               项目详情
  PUT    /api/v1/projects/{id}               更新项目
  DELETE /api/v1/projects/{id}               软删除项目
  POST   /api/v1/projects/{id}/transfer      转让项目
  POST   /api/v1/projects/{id}/freeze        冻结项目
  POST   /api/v1/projects/{id}/unfreeze      解冻项目

  # 成员管理
  GET    /api/v1/projects/{id}/members       成员列表
  POST   /api/v1/projects/{id}/members       添加成员
  PUT    /api/v1/projects/{id}/members/{uid} 修改成员角色
  DELETE /api/v1/projects/{id}/members/{uid} 移除成员
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_user_global_roles,
    require_permission,
    require_project_role,
    GLOBAL_ADMIN_ROLES,
)
from app.api.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectTransferRequest,
    ProjectMemberAdd,
    ProjectMemberUpdate,
    ProjectMemberResponse,
)
from app.core.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.role import Role
from app.models.project_member import ProjectMember
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


# ============================================================
# 项目 CRUD
# ============================================================

@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    req: ProjectCreate,
    current_user: User = Depends(require_permission("project:create")),
    db: AsyncSession = Depends(get_db),
):
    """创建项目 — 自动将创建者设为 project_owner."""
    # 重名校验
    existing = await db.execute(select(Project).where(Project.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"项目 '{req.name}' 已存在")

    # 获取 project_owner 角色 ID
    owner_role_result = await db.execute(
        select(Role).where(Role.name == "project_owner")
    )
    owner_role = owner_role_result.scalar_one_or_none()
    if not owner_role:
        raise HTTPException(status_code=500, detail="系统角色未初始化")

    project = Project(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.flush()

    # 自动添加创建者为 project_owner
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role_id=owner_role.id,
    )
    db.add(member)

    # 审计日志
    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project.id,
        resource="project",
        action="create",
        target_id=project.id,
        target_name=project.name,
        detail={"name": project.name, "display_name": project.display_name},
    ))

    await db.commit()
    await db.refresh(project)

    return ProjectResponse(
        id=project.id,
        name=project.name,
        display_name=project.display_name,
        description=project.description,
        owner_id=project.owner_id,
        status=project.status,
        member_count=1,
        datasource_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """项目列表 — 只返回当前用户有权限的项目."""
    global_roles = await get_user_global_roles(current_user.id, db)
    is_global_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)

    if is_global_admin:
        stmt = select(Project)
    else:
        stmt = (
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == current_user.id)
        )

    if search:
        stmt = stmt.where(
            Project.name.contains(search) | Project.display_name.contains(search)
        )
    if status:
        stmt = stmt.where(Project.status == status)

    stmt = stmt.order_by(Project.updated_at.desc())
    stmt = stmt.distinct()
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    projects = result.scalars().all()

    responses = []
    for p in projects:
        # 统计成员数
        member_count_result = await db.execute(
            select(func.count()).select_from(ProjectMember).where(
                ProjectMember.project_id == p.id
            )
        )
        member_count = member_count_result.scalar() or 0

        responses.append(ProjectResponse(
            id=p.id,
            name=p.name,
            display_name=p.display_name,
            description=p.description,
            owner_id=p.owner_id,
            status=p.status,
            member_count=member_count,
            datasource_count=0,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))

    return responses


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目详情."""
    # 先检查是否是全局 admin
    global_roles = await get_user_global_roles(current_user.id, db)
    is_global_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)

    stmt = select(Project).where(Project.id == project_id)
    if not is_global_admin:
        stmt = stmt.join(
            ProjectMember,
            (ProjectMember.project_id == Project.id)
            & (ProjectMember.user_id == current_user.id),
        )

    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 统计成员数
    member_count_result = await db.execute(
        select(func.count()).select_from(ProjectMember).where(
            ProjectMember.project_id == project_id
        )
    )
    member_count = member_count_result.scalar() or 0

    return ProjectResponse(
        id=project.id,
        name=project.name,
        display_name=project.display_name,
        description=project.description,
        owner_id=project.owner_id,
        status=project.status,
        member_count=member_count,
        datasource_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    req: ProjectUpdate,
    _: ProjectMember | None = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """更新项目信息."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if req.display_name is not None:
        project.display_name = req.display_name
    if req.description is not None:
        project.description = req.description
    if req.status is not None:
        project.status = req.status

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    _: ProjectMember | None = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """软删除项目."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.status = "deleted"

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="project",
        action="delete",
        target_id=project_id,
        target_name=project.name,
        detail={"previous_status": project.status},
    ))

    await db.commit()
    return {"message": "项目已删除"}


# ============================================================
# 项目生命周期
# ============================================================

@router.post("/{project_id}/transfer")
async def transfer_project(
    project_id: int,
    req: ProjectTransferRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """转让项目 — 修改 project_members 角色, owner_id 保持不变."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 权限校验
    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)

    if not is_admin:
        owner_member = await db.execute(
            select(ProjectMember).join(Role, Role.id == ProjectMember.role_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
                Role.name == "project_owner",
            )
        )
        if not owner_member.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="只有项目负责人可以转让项目")

    # 新 owner 必须是项目成员
    new_member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == req.new_owner_id,
        )
    )
    new_member = new_member_result.scalar_one_or_none()
    if not new_member:
        raise HTTPException(status_code=400, detail="新负责人必须是项目成员")

    # 获取 project_owner 角色
    owner_role = await db.execute(select(Role).where(Role.name == "project_owner"))
    owner_role = owner_role.scalar_one()

    # 旧 owner 降级
    if not is_admin:
        old_member_result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
        old_member = old_member_result.scalar_one_or_none()
        if old_member:
            editor_role = await db.execute(select(Role).where(Role.name == "editor"))
            editor_role = editor_role.scalar_one()
            old_member.role_id = editor_role.id

    # 新 owner 升级
    new_member.role_id = owner_role.id

    # 审计日志
    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="project",
        action="transfer",
        target_id=project_id,
        target_name=project.name,
        detail={"old_owner_id": current_user.id, "new_owner_id": req.new_owner_id},
    ))

    await db.commit()
    return {"message": "项目转让成功", "new_owner_id": req.new_owner_id}


@router.post("/{project_id}/freeze")
async def freeze_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    _: ProjectMember | None = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """冻结项目."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status != "active":
        raise HTTPException(status_code=400, detail="只能冻结活跃状态的项目")

    project.status = "frozen"
    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="project",
        action="update",
        target_id=project_id,
        target_name=project.name,
        detail={"status": "active → frozen"},
    ))
    await db.commit()
    return {"message": "项目已冻结"}


@router.post("/{project_id}/unfreeze")
async def unfreeze_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    _: ProjectMember | None = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """解冻项目."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.status != "frozen":
        raise HTTPException(status_code=400, detail="只能解冻已冻结的项目")

    project.status = "active"
    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="project",
        action="update",
        target_id=project_id,
        target_name=project.name,
        detail={"status": "frozen → active"},
    ))
    await db.commit()
    return {"message": "项目已解冻"}


# ============================================================
# 成员管理
# ============================================================

@router.get("/{project_id}/members", response_model=list[ProjectMemberResponse])
async def list_members(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目成员列表."""
    # 先检查是否有查看权限
    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)

    if not is_admin:
        member_check = await db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
            )
        )
        if not member_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="你不是该项目成员")

    result = await db.execute(
        select(ProjectMember, User, Role)
        .join(User, User.id == ProjectMember.user_id)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at)
    )
    members = []
    for pm, user, role in result.all():
        members.append(ProjectMemberResponse(
            id=pm.id,
            user_id=user.id,
            username=user.username,
            email=user.email,
            role_id=role.id,
            role_name=role.name,
            role_display=role.display_name,
            joined_at=pm.joined_at,
        ))
    return members


@router.post("/{project_id}/members", status_code=201)
async def add_member(
    project_id: int,
    req: ProjectMemberAdd,
    current_user: User = Depends(get_current_user),
    _: ProjectMember | None = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """添加项目成员."""
    # 校验角色是 project scope
    role = await db.get(Role, req.role_id)
    if not role:
        raise HTTPException(status_code=400, detail="角色不存在")
    if role.scope != "project":
        raise HTTPException(status_code=400, detail="只能分配项目级角色")

    # 检查用户存在
    user = await db.get(User, req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否已是成员
    existing = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == req.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户已是项目成员")

    member = ProjectMember(
        project_id=project_id,
        user_id=req.user_id,
        role_id=req.role_id,
        invited_by=current_user.id,
    )
    db.add(member)

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="member",
        action="grant",
        target_id=req.user_id,
        target_name=user.username,
        detail={"role": role.name},
    ))

    await db.commit()
    return {"message": "成员添加成功"}


@router.put("/{project_id}/members/{user_id}")
async def update_member_role(
    project_id: int,
    user_id: int,
    req: ProjectMemberUpdate,
    current_user: User = Depends(get_current_user),
    _: ProjectMember | None = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """修改成员角色."""
    role = await db.get(Role, req.role_id)
    if not role or role.scope != "project":
        raise HTTPException(status_code=400, detail="角色不存在或不是项目级角色")

    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="该用户不是项目成员")

    old_role_id = member.role_id
    member.role_id = req.role_id

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="member",
        action="update",
        target_id=user_id,
        detail={"old_role_id": old_role_id, "new_role_id": req.role_id, "new_role_name": role.name},
    ))

    await db.commit()
    return {"message": "成员角色已更新"}


@router.delete("/{project_id}/members/{user_id}")
async def remove_member(
    project_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    _: ProjectMember | None = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """移除成员."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if user_id == project.owner_id:
        raise HTTPException(status_code=400, detail="不能移除项目创建者")

    result = await db.execute(
        delete(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="该用户不是项目成员")

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="member",
        action="revoke",
        target_id=user_id,
    ))

    await db.commit()
    return {"message": "成员已移除"}
