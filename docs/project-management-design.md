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
| 6 | 项目成员管理 | P1 🔜 | 添加/移除成员，分配角色 (通过 role_id) |
| 7 | RBAC 角色权限控制 | P1 🔜 | roles + permissions + role_permissions 三表联动 |
| 8 | 项目资源统计 | P2 | 数据源数/爬虫数/API数/质量规则数 |
| 9 | 项目克隆 | P2 | 复制项目配置到新项目（不含数据） |

### 3.2 权限矩阵 (RBAC 模型)

#### 角色定义

| 角色 | scope | 级别 | 说明 |
|------|-------|:---:|------|
| `super_admin` | global | L5 | 超级管理员，拥有全部权限，管理所有资源和用户 |
| `admin` | global | L4 | 平台管理员，管理用户和全局配置 |
| `project_owner` | project | L3 | 项目负责人，管理项目内所有资源和成员 |
| `editor` | project | L2 | 编辑者，可创建和修改资源，不可删除和管成员 |
| `viewer` | project | L1 | 查看者，只读所有资源 |

#### 权限矩阵 (resource:action)

| 权限项 | super_admin | admin | project_owner | editor | viewer |
|--------|:--:|:--:|:--:|:--:|:--:|
| **用户管理** | | | | | |
| user:create/read/update/delete | ✅ | ✅ | - | - | - |
| **角色管理** | | | | | |
| role:create/read/update/delete | ✅ | ✅ | - | - | - |
| role:assign (分配角色) | ✅ | ✅ | ✅ (项目内) | - | - |
| **项目管理** | | | | | |
| project:create | ✅ | ✅ | - | - | - |
| project:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| project:update | ✅ | ✅ | ✅ | - | - |
| project:delete | ✅ | ✅ | ✅ | - | - |
| project:manage_members | ✅ | ✅ | ✅ | - | - |
| **数据源** | | | | | |
| datasource:create/update | ✅ | ✅ | ✅ | ✅ | - |
| datasource:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| datasource:delete | ✅ | ✅ | ✅ | - | - |
| datasource:test_connection | ✅ | ✅ | ✅ | ✅ | - |
| datasource:sync | ✅ | ✅ | ✅ | ✅ | - |
| **爬虫管理** | | | | | |
| crawler:create/update | ✅ | ✅ | ✅ | ✅ | - |
| crawler:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| crawler:delete | ✅ | ✅ | ✅ | - | - |
| crawler:start/stop | ✅ | ✅ | ✅ | ✅ | - |
| **数据质量** | | | | | |
| quality:create/update | ✅ | ✅ | ✅ | ✅ | - |
| quality:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| quality:delete | ✅ | ✅ | ✅ | - | - |
| quality:execute | ✅ | ✅ | ✅ | ✅ | - |
| **数据 API** | | | | | |
| api:create/update | ✅ | ✅ | ✅ | ✅ | - |
| api:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| api:delete | ✅ | ✅ | ✅ | - | - |
| api:publish | ✅ | ✅ | ✅ | ✅ | - |
| **平台管理** | | | | | |
| platform:health | ✅ | ✅ | ✅ | ✅ | ✅ |
| platform:settings | ✅ | ✅ | - | - | - |
| platform:audit | ✅ | ✅ | - | - | - |

---

## 四、数据库表设计

### 4.1 ER 关系 — 完整 RBAC 模型

```
                          ┌──────────────────────────────────────────────────────┐
                          │                   RBAC 权限体系                       │
                          │                                                      │
                          │  ┌──────────┐     ┌──────────────────┐              │
                          │  │   roles  │     │ role_permissions │              │
                          │  │          │ 1 N │                  │ N 1 ┌─────────────────┐
                          │  │ id (PK)  ├────→│ role_id   (FK)   ├────→│  permissions    │
                          │  │ name     │     │ permission_id(FK) │     │                 │
                          │  │ scope    │     └──────────────────┘     │ id (PK)         │
                          │  │ is_system│                              │ name            │
                          │  └────┬─────┘                              │ resource        │
                          │       │                                    │ action          │
                          │       │ 1                                  │ description     │
                          │       │ N                                  └─────────────────┘
                          │  ┌────┴──────────┐
                          │  │  user_roles    │  ← 全局角色 (平台级)
                          │  │  user_id (FK)  │
                          │  │  role_id (FK)  │
                          │  └────────────────┘
                          │
┌──────────┐         ┌──────────────────┐
│  users   │         │ project_members  │
│          │ 1    N  │                  │          ┌──────────┐
│ id (PK)  ├────────→│ user_id  (FK)    │          │ projects │
│ username │         │ project_id (FK)  │ N    1   │          │
│ email    │         │ role_id   (FK)   ├─────────→│ id (PK)  │
│ ...      │         │ joined_at        │          │ name     │
└──────────┘         └────────┬─────────┘          │ display  │
                              │                    │ ...      │
                              │ N (FK → roles)     └────┬─────┘
                              │                         │ 1
                              ▼                         │
                         ┌──────────┐                   │
                         │  roles   │ (project scope)   │
                         └──────────┘                   │
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

> **⚠️ P0 修复**: `owner_id` 重新定义为"项目创建者"（不可变，仅用于审计溯源），项目权限完全由 `project_members` 中的角色决定。转让项目时修改 `project_members` 角色，不修改 `owner_id`。

```sql
-- 当前已实现
CREATE TABLE projects (
    id            INTEGER PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(128) NOT NULL UNIQUE,     -- 唯一标识: "smart-factory"
    display_name  VARCHAR(256) NOT NULL,             -- 显示名称: "智能制造项目"
    description   TEXT,                              -- 项目描述
    owner_id      INTEGER NOT NULL,                  -- 创建者 FK → users.id (不可变, 仅审计)
    status        VARCHAR(32) NOT NULL DEFAULT 'active',
    -- P0 修复: 状态机扩展
    -- active / creating / freezing / frozen / suspended / archived / deleted
    created_at    DATETIME NOT NULL DEFAULT (now()),
    updated_at    DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_owner (owner_id),
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

-- 扩展: 待新增字段
ALTER TABLE projects ADD COLUMN icon               VARCHAR(64) DEFAULT 'project';  -- 项目图标
ALTER TABLE projects ADD COLUMN tags               JSON;                            -- 标签: ["生产","华东"]
ALTER TABLE projects ADD COLUMN config             JSON;                            -- 项目级配置
-- P1 新增: 数据安全等级
ALTER TABLE projects ADD COLUMN data_classification VARCHAR(16) DEFAULT 'internal';
-- internal / confidential / sensitive / restricted
```

> **项目状态机** (P1 扩展):
> ```
> creating → active → freezing → frozen → archived → deleted(软删除, 30天后清理)
>                ↓          ↓
>             suspended   (不可逆)
> ```
> | 状态 | 说明 | 允许操作 |
> |------|------|---------|
> | `creating` | 项目初始化中（基础设施创建） | 仅管理员可见 |
> | `active` | 正常运行 | 全部操作 |
> | `freezing` | 冻结中 | 禁止新建资源，已有资源可读 |
> | `frozen` | 已冻结 | 完全只读 |
> | `suspended` | 异常暂停（欠费/违规等） | 仅管理员可操作 |
> | `archived` | 归档 | 长期保留，只读 |
> | `deleted` | 软删除 | 不可见，30天后自动清理 |

#### roles (新增) — RBAC 角色表

```sql
CREATE TABLE roles (
    id            INTEGER PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(64) NOT NULL UNIQUE,    -- super_admin / admin / project_owner / editor / viewer
    display_name  VARCHAR(128) NOT NULL,          -- 超级管理员 / 平台管理员 / 项目负责人 / 编辑者 / 查看者
    description   VARCHAR(256),
    scope         VARCHAR(32) NOT NULL DEFAULT 'project',  -- global (平台级) / project (项目级)
    is_system     BOOLEAN NOT NULL DEFAULT FALSE,          -- TRUE=系统预置不可删除, FALSE=用户自定义
    created_at    DATETIME NOT NULL DEFAULT (now())
);

-- 预置角色
INSERT INTO roles (name, display_name, description, scope, is_system) VALUES
('super_admin',   '超级管理员',   '平台最高权限，管理所有资源和用户',         'global',  TRUE),
('admin',         '平台管理员',   '管理用户和全局配置',                     'global',  TRUE),
('project_owner', '项目负责人',   '管理项目内所有资源和成员',               'project', TRUE),
('editor',        '编辑者',       '创建和修改数据源、爬虫、质量规则、API',  'project', TRUE),
('viewer',        '查看者',       '只读查看项目内所有资源',                 'project', TRUE);
```

#### permissions (新增) — 权限表

```sql
CREATE TABLE permissions (
    id            INTEGER PRIMARY KEY AUTO_INCREMENT,
    name          VARCHAR(128) NOT NULL UNIQUE,  -- project:create / datasource:delete / crawler:start
    resource      VARCHAR(64) NOT NULL,          -- user / role / project / datasource / crawler / quality / api / platform
    action        VARCHAR(64) NOT NULL,          -- create / read / update / delete / manage / execute / start / stop / publish
    description   VARCHAR(256),
    created_at    DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_resource (resource),
    INDEX idx_action (action)
);

-- 预置权限 (资源:动作 粒度)
INSERT INTO permissions (name, resource, action, description) VALUES
-- 用户管理
('user:create',   'user', 'create', '创建用户'),
('user:read',     'user', 'read',   '查看用户'),
('user:update',   'user', 'update', '修改用户'),
('user:delete',   'user', 'delete', '删除用户'),

-- 角色管理
('role:create',   'role', 'create', '创建角色'),
('role:read',     'role', 'read',   '查看角色'),
('role:update',   'role', 'update', '修改角色'),
('role:delete',   'role', 'delete', '删除角色'),
('role:assign',   'role', 'assign', '分配角色给用户'),

-- 项目管理
('project:create',          'project', 'create',          '创建项目'),
('project:read',            'project', 'read',            '查看项目'),
('project:update',          'project', 'update',          '修改项目信息'),
('project:delete',          'project', 'delete',          '删除/归档项目'),
('project:manage_members',  'project', 'manage_members',  '管理项目成员'),

-- 数据源
('datasource:create',         'datasource', 'create',          '注册数据源'),
('datasource:read',           'datasource', 'read',            '查看数据源'),
('datasource:update',         'datasource', 'update',          '修改数据源配置'),
('datasource:delete',         'datasource', 'delete',          '删除数据源'),
('datasource:test_connection','datasource', 'test_connection', '测试数据源连接'),
('datasource:sync',           'datasource', 'sync',            '执行数据同步'),

-- 爬虫管理
('crawler:create',  'crawler', 'create', '创建爬虫任务'),
('crawler:read',    'crawler', 'read',   '查看爬虫任务'),
('crawler:update',  'crawler', 'update', '修改爬虫任务'),
('crawler:delete',  'crawler', 'delete', '删除爬虫任务'),
('crawler:start',   'crawler', 'start',  '启动爬虫'),
('crawler:stop',    'crawler', 'stop',   '停止爬虫'),

-- 数据质量
('quality:create',  'quality', 'create',  '创建质量规则'),
('quality:read',    'quality', 'read',    '查看质量规则'),
('quality:update',  'quality', 'update',  '修改质量规则'),
('quality:delete',  'quality', 'delete',  '删除质量规则'),
('quality:execute', 'quality', 'execute', '执行质量检查'),

-- 数据 API
('api:create',  'api', 'create',  '创建数据 API'),
('api:read',    'api', 'read',    '查看数据 API'),
('api:update',  'api', 'update',  '修改数据 API'),
('api:delete',  'api', 'delete',  '删除数据 API'),
('api:publish', 'api', 'publish', '发布/下线 API'),

-- 平台管理
('platform:health',  'platform', 'health',  '查看平台健康状态'),
('platform:settings','platform', 'settings','修改平台配置'),
('platform:audit',   'platform', 'audit',   '查看审计日志');
```

#### role_permissions (新增) — 角色-权限关联

```sql
CREATE TABLE role_permissions (
    role_id       INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,

    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

-- super_admin: 拥有所有权限 (插入全部 permission_id)
-- admin: 用户管理 + 角色管理 + 查看所有项目
-- project_owner: 项目内所有资源 CRUD + 成员管理
-- editor: 项目内所有资源 CRUD (除 delete + manage_members)
-- viewer: 只读所有资源

-- 示例: project_owner 权限
-- INSERT INTO role_permissions (role_id, permission_id)
-- SELECT r.id, p.id FROM roles r, permissions p
-- WHERE r.name = 'project_owner'
--   AND p.resource IN ('project', 'datasource', 'crawler', 'quality', 'api', 'platform');
```

#### user_roles (新增) — 用户全局角色

```sql
CREATE TABLE user_roles (
    user_id   INTEGER NOT NULL,
    role_id   INTEGER NOT NULL,

    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);

-- 初始管理员: INSERT INTO user_roles (user_id, role_id)
--   SELECT 1, id FROM roles WHERE name = 'super_admin';
```

#### project_members (改造) — 项目级成员

```sql
CREATE TABLE project_members (
    id            INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id    INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    role_id       INTEGER NOT NULL,                         -- FK → roles.id (替代原 role 字符串)
    joined_at     DATETIME NOT NULL DEFAULT (now()),
    invited_by    INTEGER,                                  -- 邀请人 FK → users.id

    UNIQUE KEY uq_project_user (project_id, user_id),
    INDEX idx_project (project_id),
    INDEX idx_user (user_id),
    INDEX idx_role (role_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id),
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

> **刷新策略**: 通过 DolphinScheduler 定时任务每 5 分钟刷新，或各资源变更时通过事件异步更新。

#### audit_logs (P1 新增) — 审计日志

```sql
-- 数据治理平台合规核心 — 记录所有敏感操作
CREATE TABLE audit_logs (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id     INTEGER NOT NULL,
    project_id  INTEGER,                              -- NULL = 平台级操作
    resource    VARCHAR(64) NOT NULL,                  -- project / datasource / member / role / permission
    action      VARCHAR(64) NOT NULL,                  -- create / update / delete / grant / revoke / transfer
    target_id   INTEGER,                              -- 操作对象 ID
    target_name VARCHAR(256),                          -- 操作对象名称 (冗余, 便于查询)
    detail      JSON,                                 -- 变更详情 (before/after diff)
    ip_address  VARCHAR(45),
    user_agent  VARCHAR(512),
    created_at  DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_user_time (user_id, created_at),
    INDEX idx_project (project_id),
    INDEX idx_resource_action (resource, action),
    INDEX idx_created (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

-- 自动清理: 保留 180 天, 之后归档到冷存储
-- CREATE EVENT IF NOT EXISTS clean_old_audit_logs
-- ON SCHEDULE EVERY 1 DAY DO
-- DELETE FROM audit_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL 180 DAY);
```

**审计日志触发点**:

| 操作 | resource | action | 记录内容 |
|------|----------|--------|---------|
| 创建/删除项目 | project | create/delete | 项目名称、配置 |
| 项目转让 | project | transfer | 旧/新 owner, 转让时间 |
| 添加/移除成员 | member | grant/revoke | 目标用户、赋予的角色 |
| 修改成员角色 | member | update | 旧角色 → 新角色 |
| 创建/删除数据源 | datasource | create/delete | 数据源类型、名称（不含密码） |
| 分配/撤销全局角色 | role | grant/revoke | 目标用户、角色名 |
| 修改角色权限绑定 | permission | update | 角色名、新增/移除的权限列表 |
| 数据源密码查看 | datasource | decrypt | 仅记录"谁在什么时间查看了哪个数据源的密码" |

#### project_quotas (P2 新增) — 项目资源配额

```sql
-- 企业级多租户资源隔离, 防止单项目资源滥用
CREATE TABLE project_quotas (
    project_id          INTEGER PRIMARY KEY,
    max_datasources     INTEGER DEFAULT 50,
    max_crawlers        INTEGER DEFAULT 20,
    max_apis            INTEGER DEFAULT 100,
    max_pipelines       INTEGER DEFAULT 30,
    max_members         INTEGER DEFAULT 50,
    max_storage_mb      INTEGER DEFAULT 10240,        -- 10GB
    max_quality_rules   INTEGER DEFAULT 100,
    updated_at          DATETIME NOT NULL DEFAULT (now()),

    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- 所有新项目默认配额 (从全局配置表读取, 此处硬编码示例)
INSERT INTO project_quotas (project_id) VALUES (1);
```

#### 数据源密码加密策略 (P1 新增)

```python
# app/core/crypto.py — 敏感字段加密

from cryptography.fernet import Fernet
import os

# 加密密钥从环境变量获取 (生产环境使用 KMS)
FERNET_KEY = os.getenv("DATAOS_ENCRYPTION_KEY")
fernet = Fernet(FERNET_KEY) if FERNET_KEY else None

SENSITIVE_KEYS = {'password', 'secret', 'token', 'access_key', 'private_key', 'api_key'}

def encrypt_config(config: dict) -> dict:
    """加密 datasource.config 中的敏感字段 (入库前调用)."""
    if not fernet:
        return config  # 开发环境未配置加密密钥时跳过
    encrypted = config.copy()
    for key in SENSITIVE_KEYS:
        if key in encrypted and encrypted[key]:
            encrypted[key] = fernet.encrypt(str(encrypted[key]).encode()).decode()
    return encrypted

def decrypt_config(config: dict) -> dict:
    """解密 datasource.config 中的敏感字段 (出库后调用, 需权限+审计)."""
    if not fernet:
        return config
    decrypted = config.copy()
    for key in SENSITIVE_KEYS:
        if key in decrypted and decrypted[key]:
            try:
                decrypted[key] = fernet.decrypt(decrypted[key].encode()).decode()
            except Exception:
                pass  # 可能未加密的旧数据
    return decrypted
```

### 4.3 Pydantic Schema

```python
# schemas.py

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
    status: Optional[str] = None  # admin only

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

# ============================================================
# Role & Permission (RBAC)
# ============================================================
class RoleResponse(BaseModel):
    id: int
    name: str
    display_name: str
    description: Optional[str]
    scope: str               # global / project
    is_system: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class PermissionResponse(BaseModel):
    id: int
    name: str
    resource: str
    action: str
    description: Optional[str]
    model_config = {"from_attributes": True}

class RolePermissionList(BaseModel):
    role: RoleResponse
    permissions: list[PermissionResponse]

# ============================================================
# Project Member
# ============================================================
class ProjectMemberAdd(BaseModel):
    user_id: int
    role_id: int                         # FK → roles.id

class ProjectMemberUpdate(BaseModel):
    role_id: int                         # FK → roles.id

class ProjectMemberResponse(BaseModel):
    id: int
    user_id: int
    username: str
    email: str
    role_id: int
    role_name: str                       # 冗余: "project_owner" / "editor" / "viewer"
    role_display: str                    # 冗余: "项目负责人" / "编辑者" / "查看者"
    joined_at: datetime
    invited_by: Optional[int]

# ============================================================
# User Role (全局角色)
# ============================================================
class UserRoleAssign(BaseModel):
    user_id: int
    role_id: int                         # 只能分配 global scope 的角色

class UserWithRoles(BaseModel):
    """用户信息 + 全局角色 + 权限列表."""
    id: int
    username: str
    email: str
    display_name: Optional[str]
    is_superuser: bool                      # 仅用于紧急模式, 正常权限走 RBAC
    global_roles: list[RoleResponse]        # 全局角色
    permissions: list[str]                  # 展开后的权限名: ["project:create", "datasource:read", ...]
    accessible_projects: list[dict]         # P1: 可访问的项目列表 [{id, name, role}]

# ============================================================
# Audit Log
# ============================================================
class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    username: str                          # JOIN 冗余
    project_id: Optional[int]
    resource: str
    action: str
    target_id: Optional[int]
    target_name: Optional[str]
    detail: Optional[dict]
    ip_address: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

# ============================================================
# Project Quota
# ============================================================
class ProjectQuotaResponse(BaseModel):
    project_id: int
    max_datasources: int
    max_crawlers: int
    max_apis: int
    max_pipelines: int
    max_members: int
    max_storage_mb: int

class ProjectQuotaUpdate(BaseModel):
    max_datasources: Optional[int] = None
    max_crawlers: Optional[int] = None
    max_apis: Optional[int] = None
    max_members: Optional[int] = None
    max_storage_mb: Optional[int] = None

# ============================================================
# Project Transfer (P0)
# ============================================================
class ProjectTransferRequest(BaseModel):
    new_owner_id: int                      # 新 owner 的用户 ID (必须已是项目成员)
```

> **说明**: `User.is_superuser` 字段保留但仅用于"紧急模式"——数据库直接置位绕过 RBAC。正常业务流程完全通过 `user_roles` + RBAC 控制。`owner_id` 更名为"创建者"概念，仅用于审计溯源，不可修改；项目权限通过 `project_members` 中 `role=project_owner` 的角色决定。转让项目时调用 `POST /projects/{id}/transfer`，原子操作修改 `project_members` 中的角色分配。

---

## 五、API 设计

### 完整端点

```
# === 项目 CRUD ===
POST   /api/v1/projects                             创建项目
GET    /api/v1/projects                             项目列表 (支持分页/搜索/筛选/状态过滤)
GET    /api/v1/projects/{id}                        项目详情 (含成员+统计+配额)
PUT    /api/v1/projects/{id}                        更新项目
DELETE /api/v1/projects/{id}                        软删除/归档 (需二次确认)
POST   /api/v1/projects/{id}/validate-delete        删除预检 (返回关联资源清单)

# === 项目生命周期 (P1) ===
POST   /api/v1/projects/{id}/transfer               转让项目 ownership (P0)
POST   /api/v1/projects/{id}/freeze                 冻结项目
POST   /api/v1/projects/{id}/unfreeze               解冻项目
POST   /api/v1/projects/{id}/archive                归档项目
POST   /api/v1/projects/{id}/clone                  克隆项目配置 (不含数据)

# === 成员管理 ===
GET    /api/v1/projects/{id}/members                成员列表
POST   /api/v1/projects/{id}/members                添加成员
PUT    /api/v1/projects/{id}/members/{user_id}      修改成员角色
DELETE /api/v1/projects/{id}/members/{user_id}      移除成员 (不能移除创建者)

# === 资源概览 ===
GET    /api/v1/projects/{id}/stats                  资源统计
GET    /api/v1/projects/{id}/datasources            项目下数据源
GET    /api/v1/projects/{id}/pipelines              项目下清洗 Pipeline
GET    /api/v1/projects/{id}/audit-logs             项目审计日志 (P1)

# === 项目配额 (P2) ===
GET    /api/v1/projects/{id}/quota                  查看配额
PUT    /api/v1/projects/{id}/quota                  修改配额 (admin only)

# === RBAC 角色管理 (admin only) ===
GET    /api/v1/roles                                角色列表 (支持 ?scope=project 筛选)
POST   /api/v1/roles                                创建自定义角色
PUT    /api/v1/roles/{id}                           更新角色
DELETE /api/v1/roles/{id}                           删除角色 (is_system=false 才可删)
GET    /api/v1/roles/{id}/permissions               查看角色绑定的权限
PUT    /api/v1/roles/{id}/permissions               更新角色权限绑定

# === 权限查询 ===
GET    /api/v1/permissions                          权限列表 (可按 resource 筛选)
GET    /api/v1/users/{id}/permissions               查询某用户的最终权限 (全局 + 项目级合并)
GET    /api/v1/users/me/permissions                 当前用户权限 (前端渲染 UI 用)

# === 用户全局角色 ===
POST   /api/v1/users/{id}/roles                     分配全局角色
DELETE /api/v1/users/{id}/roles/{role_id}           撤销全局角色

# === 认证 (增强) ===
POST   /api/v1/auth/login                           登录 → 返回 token + user + permissions + projects
POST   /api/v1/auth/refresh                         刷新 Token
```

---

## 六、关键代码设计

### 6.1 权限守卫 — 核心依赖注入

```python
# app/core/deps.py — FastAPI 权限依赖

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.models.role import Role, Permission, RolePermission, UserRole
from app.models.project_member import ProjectMember

oauth2_scheme = HTTPBearer()

# ============================================================
# 角色层级常量 (集中管理, 可改为从 DB roles 表动态加载)
# ============================================================
ROLE_LEVEL = {
    "viewer": 1,
    "editor": 2,
    "project_owner": 3,
    "admin": 4,
    "super_admin": 5,
}
GLOBAL_ADMIN_ROLES = {"super_admin", "admin"}  # 全局穿透所有项目


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Bearer Token 解析当前用户."""
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的认证令牌")
    user = await db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return user


# ============================================================
# 权限缓存 (P0 修复: Redis 缓存避免每次请求 DB JOIN)
# ============================================================
class PermissionCache:
    """权限结果缓存 — 角色变更时主动失效.

    Key 设计:
      perm:user:{user_id}              → Set<permission_name>   (全局权限, TTL 30min)
      perm:user:{user_id}:proj:{pid}   → Set<permission_name>   (项目权限, TTL 15min)

    失效时机:
      - 用户全局角色变更 → 删除 perm:user:{uid}
      - 项目成员增删/角色变更 → 删除 perm:user:{uid}:proj:{pid}
      - 角色权限绑定变更 → 批量删除所有相关用户的缓存
    """

    def __init__(self, redis_client):
        self.redis = redis_client

    async def get(self, user_id: int, project_id: int | None = None) -> set[str] | None:
        key = f"perm:user:{user_id}" + (f":proj:{project_id}" if project_id else "")
        data = await self.redis.get(key)
        return set(data.split(",")) if data else None

    async def set(self, user_id: int, permissions: set[str], project_id: int | None = None):
        key = f"perm:user:{user_id}" + (f":proj:{project_id}" if project_id else "")
        ttl = 900 if project_id else 1800  # 项目级 15min, 全局 30min
        await self.redis.setex(key, ttl, ",".join(sorted(permissions)))

    async def invalidate_user(self, user_id: int):
        """删除用户所有权限缓存 (角色变更时调用)."""
        keys = await self.redis.keys(f"perm:user:{user_id}*")
        if keys:
            await self.redis.delete(*keys)

    async def invalidate_project_member(self, user_id: int, project_id: int):
        """删除用户在特定项目的权限缓存."""
        await self.redis.delete(f"perm:user:{user_id}:proj:{project_id}")

    async def invalidate_role(self, role_id: int):
        """角色权限变更时, 失效所有持有该角色的用户缓存 (异步批量)."""
        # 查出持有该角色的所有用户
        # DELETE FROM cache WHERE key LIKE 'perm:user:%' (简化版: 设短 TTL 自然过期)
        pass  # 生产实现: 消息队列异步批量失效


# 全局实例 (应用启动时注入 Redis 连接)
perm_cache: PermissionCache | None = None


async def get_user_global_roles(user_id: int, db: AsyncSession) -> list[Role]:
    """获取用户全局角色列表."""
    result = await db.execute(
        select(Role).join(UserRole).where(UserRole.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_user_permissions(
    user_id: int,
    db: AsyncSession,
    project_id: int | None = None,
) -> set[str]:
    """获取用户的最终权限集合 = 全局角色权限 ∪ 项目角色权限.

    P0 优化: 优先读 Redis 缓存, 未命中时查 DB 并回填缓存.
    """
    # 1. 尝试缓存命中
    if perm_cache:
        cached = await perm_cache.get(user_id, project_id)
        if cached is not None:
            return cached

    # 2. 缓存未命中, 查 DB
    perm_names: set[str] = set()

    # 2a. 全局角色权限 (一次 JOIN 查询)
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


def require_permission(permission: str):
    """权限守卫工厂 — 检查当前用户是否拥有指定权限.

    用法:
      @router.post("/projects")
      async def create_project(
          req: ProjectCreate,
          current_user = Depends(require_permission("project:create")),
          db = Depends(get_db),
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
                status_code=403,
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
          member = Depends(require_project_role("project_owner")),
          db = Depends(get_db),
      ):
          ...
    """
    async def checker(
        project_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        # ✅ P0 修复: 先查全局角色 — admin/super_admin 直接放行
        global_roles = await get_user_global_roles(current_user.id, db)
        global_role_names = {r.name for r in global_roles}
        if global_role_names & GLOBAL_ADMIN_ROLES:
            # 返回一个虚拟的 ProjectMember-like 对象供后续代码使用
            # admin 不需要真实的 project_members 记录
            return None  # 调用方需处理 None 的情况

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
            raise HTTPException(status_code=403, detail="你不是该项目成员")

        member, role = row
        min_level = min(ROLE_LEVEL.get(r, 0) for r in min_roles)
        user_level = ROLE_LEVEL.get(role.name, 0)

        if user_level < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"需要 {'/'.join(min_roles)} 角色, 当前: {role.display_name}",
            )
        return member
    return checker
```

> **⚠️ P0 修复说明**: `require_project_role` 原实现先查 `project_members` 表，如果 admin 不在项目成员表中就直接 403，导致全局管理员无法管理任何项目。修复后优先检查 `user_roles` 中的全局角色，`super_admin` 和 `admin` 直接放行，不再要求必须在每个项目中都有成员记录。

### 6.2 项目创建 (含事务 + 重名校验 + 自动加 Owner)

```python
# api/projects.py

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
    owner_role = await db.execute(
        select(Role).where(Role.name == "project_owner")
    )
    owner_role = owner_role.scalar_one()

    # 事务: 创建项目 + 添加 Owner 成员
    project = Project(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
        owner_id=current_user.id,
        tags=req.tags or [],
    )
    db.add(project)
    await db.flush()  # 获取 project.id

    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role_id=owner_role.id,           # 关联 project_owner 角色
    )
    db.add(member)

    await db.commit()
    await db.refresh(project)
    return _to_response(project)
```

### 6.3 成员管理

```python
# api/projects.py

@router.post("/{project_id}/members", status_code=201)
async def add_member(
    project_id: int,
    req: ProjectMemberAdd,
    _: ProjectMember = Depends(require_project_role("project_owner")),
    db: AsyncSession = Depends(get_db),
):
    """添加项目成员 — 只有 project_owner+ 可以操作."""
    # 校验 role_id 对应的角色是 project scope
    role = await db.get(Role, req.role_id)
    if not role or role.scope != "project":
        raise HTTPException(status_code=400, detail="角色不存在或不是项目级角色")

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
    )
    db.add(member)
    await db.commit()
    return {"message": "成员添加成功"}


@router.delete("/{project_id}/members/{user_id}")
async def remove_member(
    project_id: int,
    user_id: int,
    _: ProjectMember = Depends(require_project_role("project_owner")),
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
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="该用户不是项目成员")
    await db.commit()
    return {"message": "成员已移除"}
```

### 6.4 数据源创建 — 自动归属项目 + 权限校验

```python
# api/datasources.py

@router.post("/api/v1/datasources", response_model=DataSourceResponse, status_code=201)
async def create_datasource(
    req: DataSourceCreate,
    member: ProjectMember = Depends(require_project_role("project_owner", "editor")),
    db: AsyncSession = Depends(get_db),
):
    """创建数据源 — 自动归属到成员所在项目."""
    ds = DataSource(
        project_id=member.project_id,
        name=req.name,
        source_type=req.source_type,
        config=req.config,
        description=req.description,
    )
    db.add(ds)
    await db.commit()
    return ds


@router.delete("/api/v1/datasources/{ds_id}")
async def delete_datasource(
    ds_id: int,
    current_user: User = Depends(require_permission("datasource:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除数据源 — 需要 datasource:delete 权限."""
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 额外校验: 必须在项目中有对应角色
    await require_project_role("project_owner")(ds.project_id, current_user, db)

    await db.delete(ds)
    await db.commit()
    return {"message": "数据源已删除"}
```

### 6.5 用户权限查询 (前端用) + 登录增强

```python
# api/auth.py

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录 — P1 增强: 直接返回权限列表，避免前端多次请求."""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})

    # P1 增强: 获取用户全局角色和权限
    global_roles = await get_user_global_roles(user.id, db)
    permissions = await get_user_permissions(user.id, db)  # 全局权限

    # 获取用户可访问的项目列表
    projects_result = await db.execute(
        select(Project, Role.name)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .join(Role, Role.id == ProjectMember.role_id)
        .where(ProjectMember.user_id == user.id, Project.status == 'active')
    )
    accessible_projects = [
        {"id": p.id, "name": p.name, "display_name": p.display_name, "role": role_name}
        for p, role_name in projects_result.all()
    ]

    # 如果用户是全局 admin，追加所有活跃项目
    if any(r.name in ('super_admin', 'admin') for r in global_roles):
        all_projects = await db.execute(
            select(Project).where(Project.status == 'active')
        )
        for p in all_projects.scalars().all():
            if not any(ap["id"] == p.id for ap in accessible_projects):
                accessible_projects.append({
                    "id": p.id, "name": p.name,
                    "display_name": p.display_name, "role": "admin"
                })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "is_superuser": user.is_superuser,
            "global_roles": [r.name for r in global_roles],
            "permissions": sorted(permissions),           # 前端据此渲染按钮/菜单
            "accessible_projects": accessible_projects,    # 前端项目选择器
        }
    }


@router.get("/api/v1/users/me/permissions")
async def get_my_permissions(
    project_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户在指定项目中的合并权限 (前端切换项目时调用)."""
    perms = await get_user_permissions(current_user.id, db, project_id)
    global_roles = await get_user_global_roles(current_user.id, db)

    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "global_roles": [r.name for r in global_roles],
        "project_id": project_id,
        "permissions": sorted(perms),
    }
```

### 6.6 项目转让 — 原子操作 (P0)

```python
# api/projects.py

@router.post("/{project_id}/transfer")
async def transfer_ownership(
    project_id: int,
    req: ProjectTransferRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """转让项目 ownership — 原子操作: 修改 project_members 角色 + 记录审计日志.

    约束:
      - 只能由当前 project_owner 或 admin 发起
      - 新 owner 必须已是项目成员
      - owner_id 字段保持不变 (仅记录创建者)
    """
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 权限校验: 当前用户必须是 project_owner 或 admin
    current_roles = await get_user_global_roles(current_user.id, db)
    is_admin = any(r.name in ('super_admin', 'admin') for r in current_roles)

    if not is_admin:
        member_result = await db.execute(
            select(ProjectMember, Role)
            .join(Role, Role.id == ProjectMember.role_id)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
                Role.name == 'project_owner',
            )
        )
        if not member_result.one_or_none():
            raise HTTPException(status_code=403, detail="只有项目负责人可以转让项目")

    # 新 owner 必须是项目成员
    new_owner_member = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == req.new_owner_id,
        )
    )
    new_owner_member = new_owner_member.scalar_one_or_none()
    if not new_owner_member:
        raise HTTPException(status_code=400, detail="新负责人必须是项目成员")

    # 获取 project_owner 角色 ID
    owner_role = await db.execute(select(Role).where(Role.name == "project_owner"))
    owner_role = owner_role.scalar_one()

    # 原子操作: 修改项目成员角色
    # 1. 旧 owner 降级为 editor (如果当前用户在 project_members 中)
    old_member = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    )
    old_member = old_member.scalar_one_or_none()
    if old_member and not is_admin:
        editor_role = await db.execute(select(Role).where(Role.name == "editor"))
        editor_role = editor_role.scalar_one()
        old_member.role_id = editor_role.id

    # 2. 新 owner 升级
    new_owner_member.role_id = owner_role.id

    # 3. 记录审计日志
    audit = AuditLog(
        user_id=current_user.id,
        project_id=project_id,
        resource="project",
        action="transfer",
        target_id=project_id,
        target_name=project.name,
        detail={"old_owner_id": current_user.id, "new_owner_id": req.new_owner_id},
    )
    db.add(audit)

    # 4. 失效权限缓存
    if perm_cache:
        await perm_cache.invalidate_project_member(current_user.id, project_id)
        await perm_cache.invalidate_project_member(req.new_owner_id, project_id)

    await db.commit()
    return {"message": "项目转让成功", "new_owner_id": req.new_owner_id}
```

---

## 七、前端页面设计

### 7.0 权限驱动 UI — usePermission Hook (P2)

```typescript
// hooks/usePermission.ts
// 前端根据用户权限自动控制按钮/菜单的可见性和可操作性

import { useAuthStore } from '@/stores/auth';

interface PermissionHook {
  /** 检查是否拥有指定权限 */
  can: (permission: string) => boolean;
  /** 检查是否拥有任一权限 (OR) */
  canAny: (...permissions: string[]) => boolean;
  /** 检查是否拥有全部权限 (AND) */
  canAll: (...permissions: string[]) => boolean;
  /** 当前项目角色 */
  projectRole: string | null;
  /** 是否全局管理员 */
  isGlobalAdmin: boolean;
}

export function usePermission(projectId?: number): PermissionHook {
  const { permissions, globalRoles, accessibleProjects } = useAuthStore();

  const isGlobalAdmin = globalRoles.some(r =>
    ['super_admin', 'admin'].includes(r)
  );

  const projectRole = projectId
    ? accessibleProjects.find(p => p.id === projectId)?.role ?? null
    : null;

  return {
    can: (perm: string) => isGlobalAdmin || permissions.includes(perm),
    canAny: (...perms: string[]) =>
      isGlobalAdmin || perms.some(p => permissions.includes(p)),
    canAll: (...perms: string[]) =>
      isGlobalAdmin || perms.every(p => permissions.includes(p)),
    projectRole,
    isGlobalAdmin,
  };
}

// ===== 使用示例 =====

// 页面级: 控制按钮显隐
function ProjectToolbar() {
  const { can } = usePermission();

  return (
    <Space>
      {can('project:create') && (
        <Button type="primary" icon={<PlusOutlined />}>新建项目</Button>
      )}
      {can('project:manage_members') && (
        <Button icon={<TeamOutlined />}>成员管理</Button>
      )}
    </Space>
  );
}

// 项目内: 根据项目角色控制操作
function DataSourceActions({ projectId }: { projectId: number }) {
  const { can } = usePermission(projectId);

  return (
    <Space>
      {can('datasource:test_connection') && <Button>测试连接</Button>}
      {can('datasource:sync') && <Button type="primary">同步</Button>}
      {can('datasource:delete') && <Button danger>删除</Button>}
      {/* can('datasource:delete') 为 false 时, 删除按钮不渲染 */}
    </Space>
  );
}

// 菜单过滤: 只显示用户有 read 权限的页面
function filterMenuByPermission(menuItems: MenuItem[], permissions: string[]) {
  return menuItems.filter(item => {
    if (item.permission) return permissions.includes(item.permission);
    return true;
  });
}
```

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

### 8.1 开发任务

| 序号 | 功能 | 优先级 | 工作量 | 依赖 |
|------|------|:---:|--------|------|
| 1 | Role + Permission + RolePermission 模型 + seed SQL | P0 | 0.3天 | — |
| 2 | ProjectMember 改造 (role 字符串 → role_id FK) | P0 | 0.2天 | #1 |
| 3 | UserRole 模型 (全局角色) | P0 | 0.1天 | #1 |
| 4 | 权限守卫 (require_permission / require_project_role) | P0 | 0.5天 | #1-3 |
| 5 | **P0 修复: require_project_role 全局角色穿透** | P0 | 0.1天 | #4 |
| 6 | **P0 修复: 权限 Redis 缓存 (PermissionCache)** | P0 | 0.3天 | #4 |
| 7 | 项目转让 API (transfer ownership) | P0 | 0.2天 | #4 |
| 8 | roles/permissions CRUD API | P0 | 0.3天 | #1 |
| 9 | 用户权限查询 API (get_user_permissions + login 增强) | P1 | 0.3天 | #1-5 |
| 10 | 改造 projects API (创建/成员管理/权限校验) | P1 | 0.5天 | #1-7 |
| 11 | 改造 datasources API (权限校验 + 配置加密) | P1 | 0.3天 | #4, #19 |
| 12 | **P1 新增: AuditLog 模型 + 审计中间件** | P1 | 0.5天 | #1 |
| 13 | 审计日志查询 API | P1 | 0.2天 | #12 |
| 14 | 项目状态机实现 (freeze/archive/suspend) | P1 | 0.3天 | #10 |
| 15 | 数据安全等级字段 + 校验 | P1 | 0.1天 | — |
| 16 | 项目列表页 + 成员管理页前端 | P1 | 0.5天 | #1-10 |
| 17 | 角色权限管理页前端 (admin only) | P2 | 0.3天 | #1-8 |
| 18 | **P2 新增: usePermission Hook + 前端权限驱动 UI** | P2 | 0.2天 | #16 |
| 19 | **P1 新增: 数据源密码加密 (crypto.py)** | P1 | 0.2天 | — |
| 20 | 项目配额表 + API | P2 | 0.3天 | #10 |
| 21 | 权限失效触发器 (角色变更 → 清理缓存) | P2 | 0.2天 | #6 |
| 22 | 集成测试 + 权限矩阵验证 | P2 | 0.5天 | #1-21 |
| | **合计** | | **~5.8 天** | |

### 8.2 新增文件清单

| 文件 | 说明 | 优先级 |
|------|------|:---:|
| `app/models/role.py` | Role + Permission + RolePermission 模型 | P0 |
| `app/models/project_member.py` | ProjectMember + UserRole 模型 | P0 |
| `app/models/audit_log.py` | AuditLog 模型 (P1 合规) | P1 |
| `app/models/project_quota.py` | ProjectQuota 模型 (P2) | P2 |
| `app/core/deps.py` | get_current_user / require_permission / require_project_role / PermissionCache | P0 |
| `app/core/crypto.py` | 敏感字段加密/解密 (Fernet) | P1 |
| `app/api/permissions.py` | 角色和权限管理 CRUD API | P0 |
| `app/api/audit.py` | 审计日志查询 API | P1 |
| `app/middleware/audit.py` | 审计日志自动记录中间件 | P1 |
| `platform/frontend/src/hooks/usePermission.ts` | 前端权限 Hook | P2 |
| `components/mysql/init/02-seed-rbac.sql` | 预置角色 + 权限 + 初始 admin | P0 |

### 8.3 P0 修复亮点总结

| # | 问题 | 修复方式 | 所在章节 |
|---|------|---------|---------|
| P0-1 | 权限查询每次 2 次 DB JOIN | `PermissionCache` Redis 缓存, 角色变更时主动失效 | 6.1 |
| P0-2 | 全局 admin 无法穿透项目 | `require_project_role` 先查 `user_roles` 全局角色, admin/super_admin 直接放行 | 6.1 |
| P0-3 | `owner_id` 与角色双源冲突 | `owner_id` 重新定义为不可变的"创建者"(审计用); 项目权限完全走 `project_members` | 4.2, 6.6 |
| P1-1 | 缺少审计日志 | `audit_logs` 表 + 审计中间件, 记录所有敏感操作 | 4.2 |
| P1-2 | 数据源密码明文 | `crypto.py` Fernet 加密 SENSITIVE_KEYS, 解密需权限+审计 | 4.2 |
| P1-3 | 无数据安全等级 | `data_classification` 字段: internal/confidential/sensitive/restricted | 4.2 |
| P1-4 | 项目状态机不完整 | 7 种状态: creating→active→freezing→frozen→archived→deleted + suspended | 4.2 |
| P1-5 | 登录不返回权限 | `/auth/login` 直接返回 permissions + accessible_projects | 6.5 |
| P2-1 | permission 表冗余 | 注明 `name = resource:action` 可动态生成, 保留现有设计以简化查询 | 4.2 |
| P2-2 | 无资源配额 | `project_quotas` 表, 限制数据源/API/成员/存储数量 | 4.2 |
| P2-3 | API 端点缺失 | 补充 transfer/freeze/clone/validate-delete/audit-logs/quota 端点 | 5.0 |
| P2-4 | is_superuser 重叠 | 加注释: 仅用于"紧急模式"绕过 RBAC, 正常流程走 user_roles | 4.3 |
| P2-5 | 前端无权限控制 | `usePermission` Hook: can/canAny/canAll + 示例代码 | 7.0 |
| P2-6 | 删除无二次确认 | `validate-delete` 预检端点 + 前端确认对话框 | 5.0 |
