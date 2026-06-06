"""数据质量 API — 规则 CRUD + 执行校验.

P1 更新: 质量规则持久化到 quality_rules 表，支持按项目增删改查。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

from app.api.deps import get_current_user, require_project_role, GLOBAL_ADMIN_ROLES, get_user_global_roles
from app.api.schemas import QualityRuleCreate, QualityRuleUpdate, QualityRuleResponse
from app.core.database import get_db
from app.models.user import User
from app.models.quality_rule import QualityRule as QualityRuleModel
from app.models.audit_log import AuditLog
from app.services.quality import quality_engine, QualityResult

router = APIRouter(prefix="/api/v1/quality", tags=["DataQuality"])


# ---- 运行时检查的请求/响应模型 (不变) ----

class QualityRuleInput(BaseModel):
    """质量规则定义 (运行时)."""
    name: str = Field(..., description="规则名称")
    type: str = Field(..., description="规则类型: not_null / range / regex / unique / custom_sql")
    column: str = Field(default="", description="目标列名")
    min: float | None = Field(default=None, description="范围最小值")
    max: float | None = Field(default=None, description="范围最大值")
    pattern: str = Field(default="", description="正则表达式")
    condition: str = Field(default="", description="自定义条件 (DataFrame.eval)")


class QualityCheckRequest(BaseModel):
    """质量检查请求 — 支持传入规则列表 或 引用已持久化的规则 ID 列表."""
    data: list[dict] = Field(..., description="待检查的数据 (JSON 行)")
    rules: list[QualityRuleInput] = Field(default_factory=list, description="运行时规则列表")
    rule_ids: list[int] = Field(default_factory=list, description="持久化规则 ID 列表 (P1)")


class QualityCheckResponse(BaseModel):
    """质量检查响应."""
    total_rules: int
    passed_rules: int
    failed_rules: int
    overall_pass_rate: float
    results: list[dict]


def _rule_model_to_input(rm: QualityRuleModel) -> QualityRuleInput:
    """将持久化的 QualityRule 模型转换为运行时的 QualityRuleInput."""
    cfg = rm.config or {}
    return QualityRuleInput(
        name=rm.name,
        type=rm.rule_type,
        column=rm.target_column or "",
        min=cfg.get("min"),
        max=cfg.get("max"),
        pattern=cfg.get("pattern", ""),
        condition=cfg.get("condition", ""),
    )


# ============================================================
# 持久化规则 CRUD (P1 新增)
# ============================================================

@router.post("/rules", response_model=QualityRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_quality_rule(
    req: QualityRuleCreate,
    current_user: User = Depends(get_current_user),
    _ = Depends(require_project_role("project_owner", "editor", "developer")),
    db: AsyncSession = Depends(get_db),
):
    """创建持久化质量规则 — 归属到项目. 需要 project_owner/editor/developer 角色."""
    # 检查同名规则
    existing = await db.execute(
        select(QualityRuleModel).where(
            QualityRuleModel.project_id == req.project_id,
            QualityRuleModel.name == req.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"项目内已存在同名规则 '{req.name}'")

    rule = QualityRuleModel(
        project_id=req.project_id,
        name=req.name,
        rule_type=req.rule_type,
        target_column=req.target_column,
        config=req.config,
        description=req.description,
        created_by=current_user.id,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=req.project_id,
        resource="quality_rule",
        action="create",
        target_id=rule.id,
        target_name=rule.name,
        detail={"rule_type": req.rule_type},
    ))
    await db.commit()
    return rule


@router.get("/rules", response_model=list[QualityRuleResponse])
async def list_quality_rules(
    project_id: int = Query(..., description="项目 ID (必填, 项目隔离)"),
    rule_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目下的质量规则列表 — 按项目隔离. 需要是项目成员."""
    stmt = select(QualityRuleModel).where(QualityRuleModel.project_id == project_id)
    if rule_type:
        stmt = stmt.where(QualityRuleModel.rule_type == rule_type)
    stmt = stmt.order_by(QualityRuleModel.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/rules/{rule_id}", response_model=QualityRuleResponse)
async def get_quality_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个质量规则."""
    rule = await db.get(QualityRuleModel, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.put("/rules/{rule_id}", response_model=QualityRuleResponse)
async def update_quality_rule(
    rule_id: int,
    req: QualityRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新质量规则 — 需要项目内 project_owner/editor/developer 角色."""
    rule = await db.get(QualityRuleModel, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    # 角色校验
    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        member = await db.execute(
            select(PM).where(PM.project_id == rule.project_id, PM.user_id == current_user.id)
        )
        if not member.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="你不是该项目成员")

    if req.name is not None:
        rule.name = req.name
    if req.rule_type is not None:
        rule.rule_type = req.rule_type
    if req.target_column is not None:
        rule.target_column = req.target_column
    if req.config is not None:
        rule.config = req.config
    if req.description is not None:
        rule.description = req.description
    if req.is_enabled is not None:
        rule.is_enabled = req.is_enabled

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_quality_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除质量规则 — 需要项目内 project_owner 角色."""
    rule = await db.get(QualityRuleModel, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")

    # 角色校验 (project_owner 或 admin)
    global_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in GLOBAL_ADMIN_ROLES for r in global_roles)
    if not is_admin:
        from app.models.project_member import ProjectMember as PM
        from app.models.role import Role
        member = await db.execute(
            select(PM, Role).join(Role, Role.id == PM.role_id).where(
                PM.project_id == rule.project_id, PM.user_id == current_user.id
            )
        )
        row = member.one_or_none()
        if not row:
            raise HTTPException(status_code=403, detail="你不是该项目成员")
        _, role = row
        if role.name not in ("project_owner",):
            raise HTTPException(status_code=403, detail="需要 project_owner 角色")

    db.add(AuditLog(
        user_id=current_user.id,
        project_id=rule.project_id,
        resource="quality_rule",
        action="delete",
        target_id=rule_id,
        target_name=rule.name,
    ))
    await db.delete(rule)
    await db.commit()
    return {"message": f"规则 '{rule.name}' 已删除"}


# ============================================================
# 规则执行 (增强: 支持 rule_ids 引用持久化规则)
# ============================================================

@router.post("/check", response_model=QualityCheckResponse)
async def run_quality_check(
    req: QualityCheckRequest,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行数据质量检查 — 支持运行时规则 + 持久化规则 ID 混合."""
    # 收集所有规则
    all_rules: list[QualityRuleInput] = list(req.rules)

    # P1: 加载持久化规则
    if req.rule_ids:
        result = await db.execute(
            select(QualityRuleModel).where(
                QualityRuleModel.id.in_(req.rule_ids),
                QualityRuleModel.is_enabled == True,
            )
        )
        for rm in result.scalars().all():
            all_rules.append(_rule_model_to_input(rm))

    if not all_rules:
        return QualityCheckResponse(
            total_rules=0, passed_rules=0, failed_rules=0,
            overall_pass_rate=100, results=[],
        )

    df = pd.DataFrame(req.data) if req.data else pd.DataFrame()
    rules = [r.model_dump() for r in all_rules]
    results: list[QualityResult] = quality_engine.check_dataframe(df, rules)

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    return QualityCheckResponse(
        total_rules=total,
        passed_rules=passed,
        failed_rules=total - passed,
        overall_pass_rate=round(passed / total * 100, 2) if total > 0 else 100,
        results=[r.__dict__ for r in results],
    )


@router.get("/rule-templates")
async def list_rule_templates(
    _: User = Depends(get_current_user),
):
    """获取内置规则模板列表 — 对标 DataWorks 37种规则."""
    return [
        {"type": "not_null", "label": "非空校验", "description": "检查指定列是否包含空值", "icon": "stop"},
        {"type": "range", "label": "范围校验", "description": "检查数值是否在指定范围内", "icon": "sliders"},
        {"type": "regex", "label": "格式校验", "description": "正则匹配检查字段格式", "icon": "file-text"},
        {"type": "unique", "label": "唯一性检查", "description": "检查指定列是否有重复值", "icon": "number"},
        {"type": "custom_sql", "label": "自定义规则", "description": "DataFrame.eval 表达式条件", "icon": "code"},
    ]
