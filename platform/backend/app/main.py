"""DataOS Platform — 统一平台层入口.

对标 DataWorks + DataLeap 架构：
- 统一入口，路由分发到各 API 模块
- 健康检查串联所有下游组件
- JWT 认证 + RBAC 权限守卫
- 启动时自动建表 + 种子数据
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, projects, datasources, quality, cleaning, permissions, audit, crawlers, jobs, domains, standards
from app.core.config import settings
from app.core.database import engine, Base, AsyncSessionLocal


# 确保所有模型被导入 (触发 table metadata 注册)
import app.models.user              # noqa: F401
import app.models.project           # noqa: F401
import app.models.datasource        # noqa: F401
import app.models.role              # noqa: F401
import app.models.project_member    # noqa: F401
import app.models.audit_log         # noqa: F401
import app.models.quality_rule      # noqa: F401 — P1: 质量规则持久化
import app.models.pipeline          # noqa: F401 — P1: Pipeline 持久化
import app.models.crawler           # noqa: F401 — P2: 爬虫任务映射
import app.models.sync_history      # noqa: F401 — 数据同步历史
import app.models.data_domain       # noqa: F401 — 数据域+业务过程
import app.models.data_standard     # noqa: F401 — 数据标准+字段映射+编码字典
import app.models.cleaning_template # noqa: F401 — 清洗规则模板


# ============================================================
# 种子数据: 预置角色和权限
# ============================================================
SEED_ROLES = [
    # 全局角色
    {"name": "super_admin",   "display_name": "超级管理员", "description": "平台最高权限，管理所有资源和用户",                    "scope": "global",  "is_system": True},
    {"name": "admin",         "display_name": "平台管理员", "description": "管理用户和全局配置，可穿透所有项目",                  "scope": "global",  "is_system": True},
    # 项目角色 — v2.0 对齐 DataWorks 专业版角色粒度
    {"name": "project_owner", "display_name": "项目负责人", "description": "项目最高权限，管理所有资源和成员，可转让和删除项目",   "scope": "project", "is_system": True},
    {"name": "project_admin", "display_name": "项目管理员", "description": "管理项目成员和资源，不可删除项目和转让所有权",        "scope": "project", "is_system": True},
    {"name": "developer",     "display_name": "开发者",     "description": "创建/修改/运行数据开发任务，不可删除资源和发布上线",  "scope": "project", "is_system": True},
    {"name": "operator",      "display_name": "运维者",     "description": "启停/执行/监控任务和数据源，不可创建和修改任务",      "scope": "project", "is_system": True},
    {"name": "editor",        "display_name": "编辑者",     "description": "创建和修改数据源配置，不可删除和运行任务",            "scope": "project", "is_system": True},
    {"name": "viewer",        "display_name": "查看者",     "description": "只读查看项目内所有资源",                            "scope": "project", "is_system": True},
]

SEED_PERMISSIONS = [
    # 用户管理
    ("user:create",   "user", "create", "创建用户"),
    ("user:read",     "user", "read",   "查看用户"),
    ("user:update",   "user", "update", "修改用户"),
    ("user:delete",   "user", "delete", "删除用户"),
    # 角色管理
    ("role:create",   "role", "create", "创建角色"),
    ("role:read",     "role", "read",   "查看角色"),
    ("role:update",   "role", "update", "修改角色"),
    ("role:delete",   "role", "delete", "删除角色"),
    ("role:assign",   "role", "assign", "分配角色给用户"),
    # 项目管理
    ("project:create",          "project", "create",          "创建项目"),
    ("project:read",            "project", "read",            "查看项目"),
    ("project:update",          "project", "update",          "修改项目信息"),
    ("project:delete",          "project", "delete",          "删除/归档项目"),
    ("project:manage_members",  "project", "manage_members",  "管理项目成员"),
    # 数据源
    ("datasource:create",          "datasource", "create",           "注册数据源"),
    ("datasource:read",            "datasource", "read",             "查看数据源"),
    ("datasource:update",          "datasource", "update",           "修改数据源配置"),
    ("datasource:delete",          "datasource", "delete",           "删除数据源"),
    ("datasource:test_connection", "datasource", "test_connection",  "测试数据源连接"),
    ("datasource:sync",            "datasource", "sync",             "执行数据同步"),
    # 爬虫管理
    ("crawler:create",  "crawler", "create", "创建爬虫任务"),
    ("crawler:read",    "crawler", "read",   "查看爬虫任务"),
    ("crawler:update",  "crawler", "update", "修改爬虫任务"),
    ("crawler:delete",  "crawler", "delete", "删除爬虫任务"),
    ("crawler:start",   "crawler", "start",  "启动爬虫"),
    ("crawler:stop",    "crawler", "stop",   "停止爬虫"),
    # 数据质量
    ("quality:create",  "quality", "create",  "创建质量规则"),
    ("quality:read",    "quality", "read",    "查看质量规则"),
    ("quality:update",  "quality", "update",  "修改质量规则"),
    ("quality:delete",  "quality", "delete",  "删除质量规则"),
    ("quality:execute", "quality", "execute", "执行质量检查"),
    # 数据 API
    ("api:create",  "api", "create",  "创建数据 API"),
    ("api:read",    "api", "read",    "查看数据 API"),
    ("api:update",  "api", "update",  "修改数据 API"),
    ("api:delete",  "api", "delete",  "删除数据 API"),
    ("api:publish", "api", "publish", "发布/下线 API"),
    # 平台管理
    ("platform:health",   "platform", "health",   "查看平台健康状态"),
    ("platform:settings", "platform", "settings", "修改平台配置"),
    ("platform:audit",    "platform", "audit",    "查看审计日志"),
]

# 角色-权限映射: role_name → [permission_names] (super_admin 拥有全部)
ROLE_PERMISSION_MAP = {
    "admin": [
        "user:create", "user:read", "user:update", "user:delete",
        "role:create", "role:read", "role:update", "role:delete", "role:assign",
        "project:create", "project:read", "project:update", "project:delete",
        "project:manage_members",
        "datasource:read", "datasource:delete",
        "crawler:read", "crawler:delete",
        "quality:read", "quality:delete",
        "api:read", "api:delete",
        "platform:health", "platform:settings", "platform:audit",
    ],
    "project_owner": [
        "project:read", "project:update", "project:delete", "project:manage_members",
        "datasource:create", "datasource:read", "datasource:update", "datasource:delete",
        "datasource:test_connection", "datasource:sync",
        "crawler:create", "crawler:read", "crawler:update", "crawler:delete",
        "crawler:start", "crawler:stop",
        "quality:create", "quality:read", "quality:update", "quality:delete", "quality:execute",
        "api:create", "api:read", "api:update", "api:delete", "api:publish",
        "platform:health",
        "role:assign",
    ],
    "editor": [
        "project:read",
        "datasource:create", "datasource:read", "datasource:update",
        "datasource:test_connection", "datasource:sync",
        "crawler:create", "crawler:read", "crawler:update",
        "crawler:start", "crawler:stop",
        "quality:create", "quality:read", "quality:update", "quality:execute",
        "api:create", "api:read", "api:update", "api:publish",
        "platform:health",
    ],
    "project_admin": [
        # 类似 project_owner 但无 project:delete 和 role:assign
        "project:read", "project:update", "project:manage_members",
        "datasource:create", "datasource:read", "datasource:update", "datasource:delete",
        "datasource:test_connection", "datasource:sync",
        "crawler:create", "crawler:read", "crawler:update", "crawler:delete",
        "crawler:start", "crawler:stop",
        "quality:create", "quality:read", "quality:update", "quality:delete", "quality:execute",
        "api:create", "api:read", "api:update", "api:delete", "api:publish",
        "platform:health",
    ],
    "developer": [
        # 可创建/修改/运行任务，不可删除资源和管成员
        "project:read",
        "datasource:create", "datasource:read", "datasource:update",
        "datasource:test_connection", "datasource:sync",
        "crawler:create", "crawler:read", "crawler:update",
        "crawler:start", "crawler:stop",
        "quality:create", "quality:read", "quality:update", "quality:execute",
        "api:create", "api:read", "api:update", "api:publish",
        "platform:health",
    ],
    "operator": [
        # 可启停/执行/监控，不可创建和修改资源
        "project:read",
        "datasource:read", "datasource:test_connection",
        "crawler:read", "crawler:start", "crawler:stop",
        "quality:read", "quality:execute",
        "api:read",
        "platform:health",
    ],
    "viewer": [
        "project:read",
        "datasource:read",
        "crawler:read",
        "quality:read",
        "api:read",
        "platform:health",
    ],
}


# 内置清洗规则模板 — 行业标准规则
# MES 文档定义 6 种清洗类型: 结构检查/主键检查/编码映射/状态标准化/时间逻辑/数量合理性
BUILTIN_TEMPLATES = [
    {
        "name": "mes_structure_check",
        "display_name": "结构检查",
        "description": "检查字段是否存在、字段类型是否符合标准、字段长度是否满足要求。输出结构差异清单和字段修正建议",
        "stages": [
            {"rule_type": "structure_check", "rule_name": "字段存在性检查", "target": "all_columns", "severity": "error", "action": "check", "config": {}},
        ],
    },
    {
        "name": "mes_primary_key",
        "display_name": "主键检查",
        "description": "检查关键单据编码是否唯一、是否为空。工单号、订单号、派工单号、检测单号不可为空且应唯一",
        "stages": [
            {"rule_type": "primary_key", "rule_name": "主键非空检查", "target": "primary_keys", "severity": "error", "action": "check_null", "config": {}},
            {"rule_type": "primary_key", "rule_name": "主键唯一检查", "target": "primary_keys", "severity": "error", "action": "check_unique", "config": {}},
            {"rule_type": "primary_key", "rule_name": "重复记录处理", "target": "primary_keys", "severity": "warning", "action": "dedup_keep_last", "config": {}},
        ],
    },
    {
        "name": "mes_code_mapping",
        "display_name": "编码映射",
        "description": "将不同项目中的编码字段映射到标准字段：产品编码、物料编码、工作中心编码、工序编码",
        "stages": [
            {"rule_type": "code_mapping", "rule_name": "产品编码映射", "target": "product_code", "severity": "error", "action": "map_to_standard", "config": {"standard_field": "MRL_CODE"}},
            {"rule_type": "code_mapping", "rule_name": "物料编码映射", "target": "material_code", "severity": "error", "action": "map_to_standard", "config": {"standard_field": "MATERIAL_CODE"}},
            {"rule_type": "code_mapping", "rule_name": "工序编码映射", "target": "route_code", "severity": "warning", "action": "map_to_standard", "config": {"standard_field": "ROUTE_CODE"}},
        ],
    },
    {
        "name": "mes_status_standardize",
        "display_name": "状态标准化",
        "description": "将数值状态、文本状态统一转换为标准状态字典。0/1/2/3→未发布/部分发布/已发布/完工",
        "stages": [
            {"rule_type": "status_standardize", "rule_name": "工单状态标准化", "target": "order_status", "severity": "error", "action": "map_values", "config": {"mapping": {"0": "未发布", "1": "部分发布", "2": "已发布", "3": "完工"}}},
            {"rule_type": "status_standardize", "rule_name": "质检结果标准化", "target": "quality_result", "severity": "error", "action": "map_values", "config": {"mapping": {"0": "未检测", "1": "合格", "2": "不合格", "PASS": "合格", "FAIL": "不合格"}}},
            {"rule_type": "status_standardize", "rule_name": "删除标识过滤", "target": "is_deleted", "severity": "warning", "action": "filter", "config": {"filter_value": 1, "action": "exclude"}},
        ],
    },
    {
        "name": "mes_time_logic",
        "display_name": "时间逻辑校验",
        "description": "检查计划、排程、实际时间之间的先后关系。计划开始不应晚于计划结束；采集时间应在合理周期内",
        "stages": [
            {"rule_type": "time_logic", "rule_name": "计划时间校验", "target": "plan_start_time|plan_end_time", "severity": "error", "action": "check_order", "config": {"rule": "start < end"}},
            {"rule_type": "time_logic", "rule_name": "实际时间校验", "target": "actual_start_time|actual_end_time", "severity": "error", "action": "check_order", "config": {"rule": "start < end"}},
            {"rule_type": "time_logic", "rule_name": "采集时间合理性", "target": "collect_time", "severity": "warning", "action": "check_range", "config": {"max_days_ago": 365}},
        ],
    },
    {
        "name": "mes_quantity_validity",
        "display_name": "数量合理性校验",
        "description": "检查数量字段非负、合计关系、异常极值。良品+不良品+报废=报工总数",
        "stages": [
            {"rule_type": "quantity_check", "rule_name": "数量非负检查", "target": "plan_qty|complete_qty", "severity": "error", "action": "check_non_negative", "config": {}},
            {"rule_type": "quantity_check", "rule_name": "良品报废合计", "target": "qualified_qty|defect_qty|scrap_qty", "severity": "error", "action": "check_sum", "config": {"expected_sum_field": "complete_qty"}},
            {"rule_type": "quantity_check", "rule_name": "超计划检查", "target": "complete_qty", "severity": "warning", "action": "check_lte", "config": {"compare_field": "plan_qty"}},
        ],
    },
    {
        "name": "mes_field_standardize",
        "display_name": "字段标准化",
        "description": "将MES字段名称统一：去空格、转小写、日期解析、空值填充",
        "stages": [
            {"rule_type": "structure_check", "rule_name": "字段trim标准化", "target": "all_text_columns", "severity": "warning", "action": "trim", "config": {}},
            {"rule_type": "structure_check", "rule_name": "字段小写标准化", "target": "all_text_columns", "severity": "warning", "action": "lowercase", "config": {}},
            {"rule_type": "structure_check", "rule_name": "日期字段解析", "target": "date_columns", "severity": "warning", "action": "parse_date", "config": {}},
            {"rule_type": "structure_check", "rule_name": "空值默认填充", "target": "nullable_columns", "severity": "info", "action": "fill_default", "config": {}},
        ],
    },
]

async def seed_cleaning_templates(session):
    """初始化内置清洗规则模板 (幂等)."""
    from app.models.cleaning_template import CleaningTemplate
    from sqlalchemy import select as sa_select

    existing = (await session.execute(sa_select(CleaningTemplate))).scalars().all()
    existing_names = {t.name for t in existing}

    for tpl in BUILTIN_TEMPLATES:
        if tpl["name"] not in existing_names:
            session.add(CleaningTemplate(**tpl, created_by=1))
            print(f"  📋 清洗模板: {tpl['display_name']} ({len(tpl['stages'])} 规则)")

    await session.flush()
    if not existing:
        print(f"  ✅ {len(BUILTIN_TEMPLATES)} 个内置清洗模板已创建")

async def seed_rbac(session):
    """初始化 RBAC 种子数据 (幂等)."""
    from sqlalchemy import select as sa_select
    from app.models.role import Role, Permission, RolePermission
    from app.models.project_member import UserRole

    # 1. 创建角色 (幂等)
    existing_roles = (await session.execute(sa_select(Role))).scalars().all()
    existing_role_names = {r.name for r in existing_roles}
    role_map: dict[str, Role] = {r.name: r for r in existing_roles}

    for role_data in SEED_ROLES:
        if role_data["name"] not in existing_role_names:
            role = Role(**role_data)
            session.add(role)
            await session.flush()
            role_map[role.name] = role
            print(f"  ✅ 角色: {role.display_name} ({role.name})")

    # 2. 创建权限 (幂等)
    existing_perms = (await session.execute(sa_select(Permission))).scalars().all()
    existing_perm_names = {p.name for p in existing_perms}
    perm_map: dict[str, Permission] = {p.name: p for p in existing_perms}

    for perm_name, resource, action, desc in SEED_PERMISSIONS:
        if perm_name not in existing_perm_names:
            perm = Permission(name=perm_name, resource=resource, action=action, description=desc)
            session.add(perm)
            await session.flush()
            perm_map[perm.name] = perm

    await session.flush()

    # 3. 创建角色-权限关联 (幂等)
    # ✅ 使用 role_map/perm_map (已包含新创建的数据), 而非 existing_roles/existing_perms (首次运行时空列表)
    if role_map and perm_map:
        existing_rp = (await session.execute(
            sa_select(RolePermission)
        )).scalars().all()
        existing_rp_set = {(rp.role_id, rp.permission_id) for rp in existing_rp}

        # super_admin: 所有权限
        for perm_name in perm_map:
            rp = (role_map["super_admin"].id, perm_map[perm_name].id)
            if rp not in existing_rp_set:
                session.add(RolePermission(role_id=rp[0], permission_id=rp[1]))
                existing_rp_set.add(rp)

        # 其他角色: 按映射表
        for role_name, perm_names in ROLE_PERMISSION_MAP.items():
            if role_name not in role_map:
                continue
            for perm_name in perm_names:
                if perm_name not in perm_map:
                    continue
                rp = (role_map[role_name].id, perm_map[perm_name].id)
                if rp not in existing_rp_set:
                    session.add(RolePermission(role_id=rp[0], permission_id=rp[1]))
                    existing_rp_set.add(rp)

        await session.flush()
        if not existing_roles or not existing_perms:
            print(f"  ✅ 角色-权限关联已创建")

    # 4. 给默认 admin 用户分配 super_admin 角色
    from app.models.user import User
    admin_user = (await session.execute(
        sa_select(User).where(User.username == "admin")
    )).scalar_one_or_none()

    if admin_user and role_map.get("super_admin"):
        existing_ur = (await session.execute(
            sa_select(UserRole).where(
                UserRole.user_id == admin_user.id,
                UserRole.role_id == role_map["super_admin"].id,
            )
        )).scalar_one_or_none()
        if not existing_ur:
            session.add(UserRole(
                user_id=admin_user.id,
                role_id=role_map["super_admin"].id,
            ))
            print(f"  👤 admin → super_admin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理."""
    # 启动时 — 自动建表 + 种子数据
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select as sa_select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 创建默认管理员 + RBAC 种子数据
    async with AsyncSessionLocal() as session:
        result = await session.execute(sa_select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            session.add(User(
                username="admin",
                email="admin@dataos.local",
                hashed_password=hash_password("admin123"),
                display_name="管理员",
                is_active=True,
                is_superuser=True,
            ))
            await session.commit()
            print("👤 默认管理员已创建 (admin / admin123)")

        # 种子清洗规则模板
        await seed_cleaning_templates(session)

        # 种子 RBAC 数据
        await seed_rbac(session)
        await session.commit()

    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"   API Docs: http://0.0.0.0:8001/docs")
    yield
    # 关闭时
    await engine.dispose()
    print("👋 DataOS shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="DataOS — 企业级数据治理平台统一接入层",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS — 允许前端开发服务器
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 注册路由 ----
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(datasources.router)
app.include_router(quality.router)
app.include_router(cleaning.router)
app.include_router(permissions.router)
app.include_router(audit.router)
app.include_router(crawlers.router)
app.include_router(jobs.router)
app.include_router(domains.router)
app.include_router(standards.router)

# 注册 Worker 处理函数 + 启动后台线程
from app.workers import init_handlers
from app.core.job_queue import start_worker
init_handlers()
start_worker()


@app.get("/")
async def root():
    """根路径 — 平台基本信息."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


# 健康检查 (API v1 前缀，适配前端 /api/* Vite proxy)
@app.get("/api/v1/health")
async def api_v1_health():
    """API v1 健康检查 — 代理前端 /api/* 路径."""
    from app.api.health import health_check
    return await health_check()
