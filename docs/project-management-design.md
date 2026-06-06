# DataOS 项目管理模块 — 技术详细设计文档

> 对标: DataWorks 工作空间 + DataLeap 项目中心  
> 版本: v1.0  
> 日期: 2026-06-06

---

## 一、模块定位

项目管理是 DataOS 的**顶层组织单元和权限边界**。所有数据资产（数据源、爬虫任务、清洗 Pipeline、质量规则、API 发布）都归属到一个项目下，实现资源隔离和权限控制。

**一句话**: 项目 = 一个隔离的数据治理工作空间。

---

## 二、整体业务流程

```
                              ┌─────────────────────────┐
                              │      ① 创建项目          │
                              │                         │
                              │  管理员创建项目           │
                              │  name: "smart-factory"  │
                              │  display: "智能制造项目"  │
                              │  自动成为 Project Owner   │
                              └───────────┬─────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────┐
                              │     ② 邀请成员           │
                              │                         │
                              │  添加团队成员            │
                              │  分配角色:               │
                              │  Admin / Editor / Viewer│
                              └───────────┬─────────────┘
                                          │
          ┌───────────────────────────────┼───────────────────────────────┐
          │                               │                               │
          ▼                               ▼                               ▼
┌───────────────────┐          ┌───────────────────┐          ┌───────────────────┐
│ ③ 注册数据源       │          │ ④ 配置爬虫         │          │ ⑤ 上传文件         │
│                   │          │                   │          │                   │
│ 项目下添加 MySQL/  │          │ Crawlab 中         │          │ MinIO bucket      │
│ PG/Mongo/API/     │          │ 创建爬虫任务        │          │ 按项目隔离存储     │
│ Kafka 等数据源     │          │ Scrapy/Crawlee      │          │ CSV/Excel/JSON    │
└─────────┬─────────┘          └─────────┬─────────┘          └─────────┬─────────┘
          │                               │                               │
          └───────────────────────────────┼───────────────────────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────┐
                              │    ⑥ 数据清洗           │
                              │                         │
                              │  Pipeline 7 阶段执行    │
                              │  数据标准化 → 去重 →    │
                              │  异常处理 → 质量门控     │
                              └───────────┬─────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────┐
                              │    ⑦ 数据 API 发布       │
                              │                         │
                              │  Directus 中             │
                              │  按项目创建 API 集合     │
                              │  限流/鉴权/RBAC          │
                              └───────────┬─────────────┘
                                          │
                        ┌─────────────────┴─────────────────┐
                        │                                   │
                        ▼                                   ▼
              ┌─────────────────┐                 ┌─────────────────┐
              │  ⑧ 外部消费      │                 │  ⑨ RelOS 入图    │
              │                 │                 │                 │
              │  第三方系统      │                 │  标准化数据      │
              │  BI/数据分析     │                 │  → Neo4j 关系图   │
              └─────────────────┘                 └─────────────────┘
```

---

## 三、功能清单

### 3.1 核心功能 (Phase 1-2)

| # | 功能 | 优先级 | 说明 |
|---|------|:---:|------|
| 1 | 创建项目 | P0 ✅ | POST /projects，重名校验 |
| 2 | 查看项目列表 | P0 ✅ | GET /projects，按时间倒序 |
| 3 | 查看项目详情 | P0 ✅ | GET /projects/{id} |
| 4 | 更新项目信息 | P0 🔜 | PUT /projects/{id}，修改名称/描述/状态 |
| 5 | 归档/删除项目 | P1 🔜 | 归档后数据保留但不能新建资源；删除需二次确认 |
| 6 | 项目成员管理 | P1 🔜 | 添加/移除成员，分配角色 |
| 7 | 角色权限控制 | P1 🔜 | Admin 全部权限 / Editor 编辑 / Viewer 只读 |
| 8 | 项目资源统计 | P2 | 数据源数/爬虫数/API数/质量规则数 |
| 9 | 项目克隆 | P2 | 复制项目配置到新项目（不含数据） |

### 3.2 权限矩阵 (对标 DataWorks 角色)

| 操作 | Admin | Editor | Viewer |
|------|:---:|:---:|:---:|
| 查看项目 | ✅ | ✅ | ✅ |
| 修改项目信息 | ✅ | ❌ | ❌ |
| 管理成员 | ✅ | ❌ | ❌ |
| 注册/编辑数据源 | ✅ | ✅ | ❌ |
| 创建/编辑爬虫 | ✅ | ✅ | ❌ |
| 执行清洗 Pipeline | ✅ | ✅ | ❌ |
| 创建/发布 API | ✅ | ✅ | ❌ |
| 查看数据地图 | ✅ | ✅ | ✅ |
| 删除资源 | ✅ | ❌ | ❌ |
| 归档项目 | ✅ | ❌ | ❌ |

---

## 四、数据库表设计

### 4.1 ER 关系

```
┌──────────┐         ┌──────────────────┐
│  users   │         │  project_members │
│          │ 1    N  │                  │          ┌──────────┐
│ id (PK)  ├────────→│ user_id  (FK)    │          │ projects │
│ username │         │ project_id (FK)  │ N    1   │          │
│ email    │         │ role             ├─────────→│ id (PK)  │
│ ...      │         │ joined_at        │          │ name     │
└──────────┘         └──────────────────┘          │ display  │
                                                   │ ...      │
                                                   └────┬─────┘
                                                        │ 1
                                                        │
                          ┌─────────────────────────────┼──────────────────────┐
                          │ N                           │ N                    │ N
                   ┌──────┴──────┐              ┌──────┴──────┐      ┌───────┴──────┐
                   │ datasources │              │  pipelines  │      │  data_apis    │
                   │             │              │             │      │               │
                   │ project_id  │              │ project_id  │      │ project_id    │
                   │ name        │              │ name        │      │ name          │
                   │ source_type │              │ stages_json │      │ endpoint      │
                   │ config      │              │ status      │      │ method        │
                   └─────────────┘              └─────────────┘      └───────────────┘
```

### 4.2 表结构

#### projects (已有，扩展)

```sql
-- 当前已实现
CREATE TABLE projects (
    id            INTEGER PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(128) NOT NULL UNIQUE,     -- 唯一标识: "smart-factory"
    display_name  VARCHAR(256) NOT NULL,             -- 显示名称: "智能制造项目"
    description   TEXT,                              -- 项目描述
    owner_id      INTEGER NOT NULL,                  -- 创建者 FK → users.id
    status        VARCHAR(32) NOT NULL DEFAULT 'active',  -- active / archived / deleted
    created_at    DATETIME NOT NULL DEFAULT (now()),
    updated_at    DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_owner (owner_id),
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

-- 扩展: 待新增字段
ALTER TABLE projects ADD COLUMN icon      VARCHAR(64) DEFAULT 'project';  -- 项目图标
ALTER TABLE projects ADD COLUMN tags      JSON;                            -- 标签: ["生产","华东"]
ALTER TABLE projects ADD COLUMN config    JSON;                            -- 项目级配置
```

#### project_members (新增)

```sql
CREATE TABLE project_members (
    id            INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id    INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    role          VARCHAR(32) NOT NULL DEFAULT 'viewer',  -- admin / editor / viewer
    joined_at     DATETIME NOT NULL DEFAULT (now()),
    invited_by    INTEGER,                                -- 邀请人 FK → users.id

    UNIQUE KEY uq_project_user (project_id, user_id),
    INDEX idx_project (project_id),
    INDEX idx_user (user_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (invited_by) REFERENCES users(id)
);
```

#### project_stats (新增, 物化视图)

```sql
-- 项目资源统计快照 (定时刷新，避免每次查询 COUNT)
CREATE TABLE project_stats (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL UNIQUE,
    datasource_count INTEGER DEFAULT 0,
    pipeline_count   INTEGER DEFAULT 0,
    api_count        INTEGER DEFAULT 0,
    crawler_count    INTEGER DEFAULT 0,
    quality_rule_count INTEGER DEFAULT 0,
    total_rows       BIGINT DEFAULT 0,        -- 项目总数据量
    last_sync_at     DATETIME,
    updated_at       DATETIME NOT NULL DEFAULT (now()),

    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

### 4.3 Pydantic Schema

```python
# schemas.py

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128, pattern=r"^[a-z0-9-]+$")
    display_name: str = Field(..., max_length=256)
    description: Optional[str] = None
    tags: Optional[list[str]] = None

class ProjectUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    status: Optional[str] = None  # admin only

class ProjectMemberAdd(BaseModel):
    user_id: int
    role: str = "viewer"  # admin / editor / viewer

class ProjectMemberUpdate(BaseModel):
    role: str  # admin / editor / viewer

class ProjectResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    owner_id: int
    status: str
    tags: Optional[list[str]]
    member_count: int = 0
    datasource_count: int = 0
    created_at: datetime
    updated_at: datetime
```

---

## 五、API 设计

### 完整端点

```
POST   /api/v1/projects                             创建项目
GET    /api/v1/projects                             项目列表 (支持分页/搜索/筛选)
GET    /api/v1/projects/{id}                        项目详情 (含成员+统计)
PUT    /api/v1/projects/{id}                        更新项目
DELETE /api/v1/projects/{id}                        软删除/归档

# 成员管理
GET    /api/v1/projects/{id}/members                成员列表
POST   /api/v1/projects/{id}/members                添加成员
PUT    /api/v1/projects/{id}/members/{user_id}      修改成员角色
DELETE /api/v1/projects/{id}/members/{user_id}      移除成员

# 资源概览
GET    /api/v1/projects/{id}/stats                  资源统计
GET    /api/v1/projects/{id}/datasources            项目下数据源 (复用 /datasources?project_id=)
GET    /api/v1/projects/{id}/pipelines              项目下清洗 Pipeline
```

---

## 六、关键代码设计

### 6.1 项目创建 (含事务 + 重名校验 + 自动加 Owner)

```python
# api/projects.py

@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    req: ProjectCreate,
    current_user: User = Depends(get_current_user),  # JWT 认证
    db: AsyncSession = Depends(get_db),
):
    """创建项目 — 自动将创建者设为 Admin 成员."""
    # 重名校验
    existing = await db.execute(select(Project).where(Project.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"项目 '{req.name}' 已存在")

    # 事务: 创建项目 + 添加 Owner 成员 + 初始化统计
    project = Project(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
        owner_id=current_user.id,
        tags=req.tags or [],
    )
    db.add(project)
    await db.flush()  # 获取 project.id

    # 自动添加创建者为 Admin
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role="admin",
    )
    db.add(member)

    # 初始化统计
    stats = ProjectStats(project_id=project.id)
    db.add(stats)

    await db.commit()
    await db.refresh(project)
    return _to_response(project)
```

### 6.2 权限守卫装饰器

```python
# api/deps.py 追加

async def get_project_member(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectMember:
    """获取当前用户在项目中的成员身份 (404=项目不存在, 403=不是成员)."""
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=403, detail="你不是该项目成员")
    return member


def require_role(*roles: str):
    """角色守卫工厂 — 要求特定角色才能访问.

    使用: @router.delete("/{id}", dependencies=[Depends(require_role("admin"))])
    """
    async def checker(member: ProjectMember = Depends(get_project_member)):
        if member.role not in roles:
            raise HTTPException(status_code=403, detail=f"需要 {'/'.join(roles)} 权限")
        return member
    return checker
```

### 6.3 成员管理

```python
# api/projects.py

@router.post("/{project_id}/members", status_code=201)
async def add_member(
    project_id: int,
    req: ProjectMemberAdd,
    admin: ProjectMember = Depends(require_role("admin")),  # 只有 Admin 能加人
    db: AsyncSession = Depends(get_db),
):
    """添加项目成员."""
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
        role=req.role,
        invited_by=admin.user_id,
    )
    db.add(member)
    await db.commit()
    return {"message": "成员添加成功"}


@router.delete("/{project_id}/members/{user_id}")
async def remove_member(
    project_id: int,
    user_id: int,
    _: ProjectMember = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """移除成员 — 不能移除项目 Owner."""
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
    await db.commit()
    return {"message": "成员已移除"}
```

### 6.4 项目列表（含统计聚合）

```python
@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """项目列表 — 只返回当前用户有权限的项目."""
    # 基础查询: 用户是成员的项目
    stmt = (
        select(Project, ProjectMember.role, ProjectStats)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .outerjoin(ProjectStats, ProjectStats.project_id == Project.id)
        .where(ProjectMember.user_id == current_user.id)
    )

    if search:
        stmt = stmt.where(
            or_(
                Project.name.contains(search),
                Project.display_name.contains(search),
            )
        )
    if status:
        stmt = stmt.where(Project.status == status)

    stmt = stmt.order_by(Project.updated_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        ProjectResponse(
            id=p.id, name=p.name, display_name=p.display_name,
            description=p.description, owner_id=p.owner_id,
            status=p.status, tags=p.tags,
            my_role=role,
            datasource_count=s.datasource_count if s else 0,
            member_count=await _count_members(db, p.id),
            created_at=p.created_at, updated_at=p.updated_at,
        )
        for p, role, s in rows
    ]
```

### 6.5 资源归属校验 (其他模块复用)

```python
# 数据源创建时校验项目成员身份
@router.post("/api/v1/datasources", response_model=DataSourceResponse, status_code=201)
async def create_datasource(
    req: DataSourceCreate,
    member: ProjectMember = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
):
    """创建数据源 — 自动归属到当前项目."""
    ds = DataSource(
        project_id=member.project_id,  # 从成员身份自动获取
        name=req.name,
        source_type=req.source_type,
        config=req.config,
        description=req.description,
    )
    db.add(ds)
    await db.commit()
    return ds
```

---

## 七、前端页面设计

### 7.1 项目列表页

```
┌─────────────────────────────────────────────────────────┐
│  项目管理                                    [+ 新建项目] │
├─────────────────────────────────────────────────────────┤
│  🔍 搜索项目...                    状态: [全部 ▼]       │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────┐ ┌─────────────────────┐        │
│ │ 🏭 智能制造项目       │ │ 💰 财务分析项目       │        │
│ │ smart-factory       │ │ finance-analysis    │        │
│ │                     │ │                     │        │
│ │ 数据源: 5  成员: 3   │ │ 数据源: 2  成员: 2   │        │
│ │ Pipeline: 2  API: 8 │ │ Pipeline: 0  API: 3 │        │
│ │ 创建者: 管理员        │ │ 创建者: 张三          │        │
│ │                     │ │                     │        │
│ │ [进入] [设置]        │ │ [进入] [设置]        │        │
│ └─────────────────────┘ └─────────────────────┘        │
└─────────────────────────────────────────────────────────┘
```

### 7.2 项目详情/设置页

```
┌─────────────────────────────────────────────────────────┐
│  ← 返回    智能制造项目                                   │
├─────────────────────────────────────────────────────────┤
│  [基本信息] [成员管理] [资源] [设置]                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  项目标识: smart-factory                                 │
│  显示名称: 智能制造项目                                    │
│  描述: 华东工厂产线数据治理                                  │
│  创建者: 管理员                                           │
│  创建时间: 2026-06-01                                    │
│                                                         │
│  ── 成员 (3) ──────────────────────────────────────       │
│  👤 管理员  Admin    创建者                               │
│  👤 张三    Editor   2026-06-03 加入                      │
│  👤 李四    Viewer   2026-06-05 加入                      │
│  [+ 邀请成员]                                            │
│                                                         │
│  ── 资源概览 ────────────────────────────────────         │
│  数据源: 5   爬虫: 3   Pipeline: 2   API: 8              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 八、实施计划

| 序号 | 功能 | 工作量 | 依赖 |
|------|------|--------|------|
| 1 | Project 模型扩展 (tags/config) + migration | 0.3天 | — |
| 2 | ProjectMember 表 + CRUD API | 0.5天 | #1 |
| 3 | ProjectStats 表 + 统计刷新 | 0.3天 | #1 |
| 4 | 权限守卫 (require_role) | 0.3天 | #2 |
| 5 | PUT/DELETE 项目 API | 0.2天 | #1 |
| 6 | 数据源/清洗模块接入项目权限 | 0.3天 | #4 |
| 7 | 前端项目列表页 | 0.5天 | #1-5 |
| 8 | 前端项目详情/成员管理页 | 0.5天 | #1-5 |
| 9 | 集成测试 | 0.3天 | #1-8 |
| | **合计** | **~3 天** | |
