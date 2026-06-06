# DataOS 项目管理模块 — 技术详细设计文档

> 对标: DataWorks 工作空间 + DataLeap 项目中心 + Dataphin OneData 方法论  
> 版本: v2.0  
> 日期: 2026-06-06  
> 基于: [深度研究] 互联网大厂数据服务平台项目管理模块对比分析

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

#### 角色定义 (v2.0 对齐 DataWorks 专业版)

| 角色 | scope | 级别 | 对标 DataWorks | 说明 |
|------|-------|:---:|---------------|------|
| `super_admin` | global | L6 | — | 超级管理员，拥有全部权限，管理所有资源和用户 |
| `admin` | global | L5 | 空间管理员 | 平台管理员，管理用户和全局配置，可穿透所有项目 |
| `project_owner` | project | L4 | 项目负责人 | 管理项目内所有资源和成员，可转让项目 |
| `project_admin` | project | L3 | **新增** 项目管理员 | 管理成员+资源，但不能删除项目或转让（分担 owner 压力） |
| `developer` | project | L2.5 | **新增** 开发 | 对标 DataWorks"开发"角色，可创建/修改/运行任务，不可删资源 |
| `operator` | project | L2 | **新增** 运维 | 对标 DataWorks"运维"角色，可启停/执行/监控，不可创建/修改 |
| `editor` | project | L1.5 | **保留** 编辑者 | 可创建和修改资源，不可删除、不可发布、不可管成员 |
| `viewer` | project | L1 | 访客 | 对标 DataWorks"访客"角色，只读所有资源 |

> **设计决策**: DataWorks 专业版有 6 个空间级角色（管理员/开发/运维/访客/安全管理员/模型设计师），DataOS 对齐扩展为 **3 个全局角色 + 6 个项目角色**，覆盖核心场景。`project_admin` 是 project_owner 的"代理"角色——可管理成员但不能删除项目和转让所有权，解决企业场景中项目负责人过于集中的问题。`developer` 和 `operator` 拆分对标 DataWorks 的**开发/运维分离**，满足企业安全要求（开发不能直接运维生产任务）。

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

### 3.3 开发/生产环境隔离 (v2.0 新增，对齐 DataWorks 标准模式)

> **来源**: DataWorks 专业版的「标准模式工作空间」是 DataOS 项目管理模块最大的功能缺口。标准模式下，工作空间分为**开发环境**和**生产环境**，代码只能在开发环境编辑，通过发布流程部署到生产环境，确保生产数据安全。

#### 3.3.1 设计目标

```
┌─────────────────────────────────────────────────────────────┐
│                     DataOS 双环境架构                         │
│                                                             │
│  ┌─────────────────────┐        ┌─────────────────────┐    │
│  │   开发环境 (DEV)     │        │   生产环境 (PROD)    │    │
│  │                     │        │                     │    │
│  │ • 开发数据源         │ 发布   │ • 生产数据源         │    │
│  │ • 调试任务           │ ────→ │ • 正式调度任务        │    │
│  │ • 测试 Pipeline      │        │ • 线上 API           │    │
│  │ • 草稿质量规则        │        │ • 生效告警规则        │    │
│  │                     │        │                     │    │
│  │ 角色: developer+    │        │ 角色: operator+     │    │
│  └─────────────────────┘        └─────────────────────┘    │
│                                                             │
│  同一项目下的环境隔离，dev 和 prod 共享项目成员和基础配置       │
└─────────────────────────────────────────────────────────────┘
```

#### 3.3.2 数据模型扩展

```sql
-- projects 表新增环境相关字段
ALTER TABLE projects ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'simple';
-- 'simple' = 单环境模式 (当前行为，向后兼容)
-- 'standard' = 标准模式 (dev + prod 双环境隔离)

ALTER TABLE projects ADD COLUMN default_environment VARCHAR(8) NOT NULL DEFAULT 'dev';
-- 默认进入的环境 (dev / prod)

-- 新建 project_environments 表 (v2.0)
CREATE TABLE project_environments (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    name            VARCHAR(16) NOT NULL,           -- 'dev' / 'prod'
    display_name    VARCHAR(64) NOT NULL,           -- '开发环境' / '生产环境'
    description     TEXT,
    is_default      BOOLEAN DEFAULT FALSE,
    created_at      DATETIME NOT NULL DEFAULT (now()),

    UNIQUE KEY uq_project_env (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- 所有项目资源表新增 environment 字段
ALTER TABLE datasources ADD COLUMN environment VARCHAR(16) NOT NULL DEFAULT 'dev';
ALTER TABLE pipelines ADD COLUMN environment VARCHAR(16) NOT NULL DEFAULT 'dev';
ALTER TABLE quality_rules ADD COLUMN environment VARCHAR(16) NOT NULL DEFAULT 'dev';
ALTER TABLE data_apis ADD COLUMN environment VARCHAR(16) NOT NULL DEFAULT 'dev';
-- 注意: crawlers 的 environment 字段通过 Crawlab 侧的 tag/label 实现，不在 DataOS 层存储
```

#### 3.3.3 环境感知的 API 设计

```python
# GET /api/v1/projects/{id}/datasources?environment=dev
# GET /api/v1/projects/{id}/datasources?environment=prod
# 所有资源列表端点统一支持 ?environment= 查询参数，默认值为当前项目的 default_environment

# POST /api/v1/projects/{id}/environments      创建环境 (standard 模式项目)
# DELETE /api/v1/projects/{id}/environments/{env_id}  删除环境

# POST /api/v1/projects/{id}/publish           发布任务从 dev 到 prod (P1)
# 参数: { resource_type: "pipeline", resource_id: 123, target_env: "prod" }
# 校验: 目标环境数据源连接有效、质量规则通过、无循环依赖
```

#### 3.3.4 环境隔离的权限控制

| 操作 | DEV 环境 | PROD 环境 |
|------|---------|----------|
| 创建/修改数据源 | developer+ | project_admin+ |
| 创建/修改 Pipeline | developer+ | project_admin+ |
| 启停任务 | developer+ | operator+ |
| 删除资源 | project_admin+ | project_owner |
| 发布到生产 | project_admin+ | — |
| 查看配置 | viewer+ | viewer+ |
| API 发布 | developer+ | project_admin+ |
| 质量规则修改 | developer+ | operator+ |

> **设计决策**: 对标 DataWorks，生产环境的写操作权限更高。`developer` 可以在开发环境自由实验，但不能直接修改生产环境的任务配置和删除资源——这需要 `project_admin` 或 `project_owner` 角色。

---

### 3.4 数据域与业务过程建模 (v2.0 新增，对齐 Dataphin OneData)

> **来源**: 阿里云 Dataphin 的核心差异化能力——遵循 OneData 方法论，通过**数据域 (Data Domain)** 和**业务过程 (Business Process)** 对数据进行业务化组织。这是 DataOS 从"技术项目管理"升级为"数据建设治理平台"的关键一步。

#### 3.4.1 概念对齐

```
OneData 体系:
┌──────────────────────────────────────────────────────┐
│  主题域 (Subject Area)                                │
│  ├── 数据域 (Data Domain)                             │
│  │   ├── 业务过程 (Business Process)                  │
│  │   │   ├── 维度表 (Dimension Table)                 │
│  │   │   ├── 事实表 (Fact Table)                      │
│  │   │   └── 汇总表 (Aggregate Table)                 │
│  │   │                                                │
│  │   └── 数据标准 (Data Standard)                     │
│  │       ├── 字段标准 (命名、类型、值域)               │
│  │       ├── 编码规则 (主键、业务键生成)               │
│  │       └── 指标定义 (原子→派生→复合)                 │
│  └── ...                                              │
└──────────────────────────────────────────────────────┘
```

#### 3.4.2 数据模型

```sql
-- 数据域表 (v2.0)
CREATE TABLE data_domains (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    parent_id       INTEGER,                              -- 父子域层级 (自引用)
    name            VARCHAR(128) NOT NULL,                 -- 域英文名: "trade_domain"
    display_name    VARCHAR(256) NOT NULL,                 -- 域中文名: "交易域"
    description     TEXT,
    owner_id        INTEGER,                              -- 域负责人
    sort_order      INTEGER DEFAULT 0,                    -- 排序
    created_at      DATETIME NOT NULL DEFAULT (now()),
    updated_at      DATETIME NOT NULL DEFAULT (now()),

    UNIQUE KEY uq_domain (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES data_domains(id) ON DELETE SET NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 业务过程表 (v2.0)
CREATE TABLE business_processes (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    domain_id       INTEGER NOT NULL,                      -- 所属数据域
    name            VARCHAR(128) NOT NULL,                 -- 过程英文名: "order_create"
    display_name    VARCHAR(256) NOT NULL,                 -- 过程中文名: "订单创建"
    description     TEXT,
    owner_id        INTEGER,
    source_tables   JSON,                                  -- 关联源表: ["ods_order", "ods_user"]
    target_tables   JSON,                                  -- 产出的目标表: ["dwd_trade_order"]
    schedule_cron   VARCHAR(64),                           -- 调度周期
    created_at      DATETIME NOT NULL DEFAULT (now()),
    updated_at      DATETIME NOT NULL DEFAULT (now()),

    UNIQUE KEY uq_process (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (domain_id) REFERENCES data_domains(id) ON DELETE RESTRICT,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
);

-- 数据标准表 (v2.0)
CREATE TABLE data_standards (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    domain_id       INTEGER,                               -- 可选: 归属到特定数据域
    name            VARCHAR(128) NOT NULL,                 -- 标准名称: "user_id_standard"
    field_name      VARCHAR(128) NOT NULL,                 -- 字段名称: "user_id"
    data_type       VARCHAR(64) NOT NULL,                  -- 数据类型: "BIGINT"
    length          INTEGER,                               -- 字段长度
    precision       INTEGER,                               -- 精度
    nullable        BOOLEAN DEFAULT FALSE,
    default_value   VARCHAR(256),
    enum_values     JSON,                                  -- 枚举值: ["0","1"]
    regex_pattern   VARCHAR(512),                          -- 正则校验
    description     TEXT,
    created_at      DATETIME NOT NULL DEFAULT (now()),
    updated_at      DATETIME NOT NULL DEFAULT (now()),

    UNIQUE KEY uq_standard (project_id, field_name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (domain_id) REFERENCES data_domains(id) ON DELETE SET NULL
);

-- 指标定义表 (v2.1)
CREATE TABLE metrics (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    domain_id       INTEGER,
    name            VARCHAR(128) NOT NULL,                 -- 指标英文名: "daily_order_amount"
    display_name    VARCHAR(256) NOT NULL,                 -- 指标中文名: "日订单金额"
    metric_type     VARCHAR(32) NOT NULL,                  -- 'atomic' (原子) / 'derived' (派生) / 'composite' (复合)
    formula         TEXT,                                  -- 派生/复合指标的计算公式
    parent_ids      JSON,                                  -- 父指标 ID 列表
    data_type       VARCHAR(64) DEFAULT 'DECIMAL',
    unit            VARCHAR(64),                           -- 单位: "元" / "次" / "%"
    owner_id        INTEGER,
    description     TEXT,
    created_at      DATETIME NOT NULL DEFAULT (now()),

    UNIQUE KEY uq_metric (project_id, name),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (domain_id) REFERENCES data_domains(id) ON DELETE SET NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
);
```

#### 3.4.3 数据源与数据域的关联

```sql
-- 数据源扩展: 关联到数据域
ALTER TABLE datasources ADD COLUMN domain_id INTEGER;
ALTER TABLE datasources ADD FOREIGN KEY (domain_id) REFERENCES data_domains(id) ON DELETE SET NULL;
```

#### 3.4.4 建模 API

```
POST   /api/v1/projects/{id}/domains                 创建数据域
GET    /api/v1/projects/{id}/domains                 数据域列表 (支持树形结构)
PUT    /api/v1/projects/{id}/domains/{did}           更新数据域
DELETE /api/v1/projects/{id}/domains/{did}           删除数据域 (需无子域和业务过程)

POST   /api/v1/projects/{id}/domains/{did}/processes   创建业务过程
GET    /api/v1/projects/{id}/processes                 业务过程列表 (按域筛选)

POST   /api/v1/projects/{id}/standards                  创建数据标准
GET    /api/v1/projects/{id}/standards                  数据标准列表

POST   /api/v1/projects/{id}/metrics                    创建指标
GET    /api/v1/projects/{id}/metrics                    指标列表 (按类型筛选)
```

> **实施策略**: 数据域建模是 P2 功能（v2.0），优先级低于环境隔离和通知告警。初期可先实现数据域 + 业务过程两张表的基础 CRUD，指标管理留到 v2.1。

---

### 3.5 通知与告警系统 (v2.0 新增，对标 DataWorks 质量监控)

> **来源**: DataWorks 专业版的数据质量监控包含告警规则配置、通知渠道（短信/邮件/钉钉/Webhook）和阻塞策略。DataOS 当前质量引擎只有规则执行，缺少告警和通知。

#### 3.5.1 通知渠道

```sql
-- 通知渠道配置 (全局级，admin 管理)
CREATE TABLE notification_channels (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(64) NOT NULL UNIQUE,          -- 'email' / 'dingtalk' / 'wecom' / 'webhook' / 'sms'
    display_name    VARCHAR(128) NOT NULL,
    config          JSON NOT NULL,                         -- SMTP 配置 / Webhook URL / 钉钉机器人 key
    is_enabled      BOOLEAN DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT (now()),
    updated_at      DATETIME NOT NULL DEFAULT (now())
);

-- 用户通知偏好 (按用户自定义)
CREATE TABLE user_notification_prefs (
    user_id         INTEGER NOT NULL,
    channel_id      INTEGER NOT NULL,
    target          VARCHAR(256) NOT NULL,                -- 邮箱地址 / 手机号 / 企业微信 userid
    is_enabled      BOOLEAN DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT (now()),

    PRIMARY KEY (user_id, channel_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES notification_channels(id) ON DELETE CASCADE
);
```

#### 3.5.2 告警规则

```sql
-- 告警规则 (项目级)
CREATE TABLE alert_rules (
    id              INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id      INTEGER NOT NULL,
    name            VARCHAR(128) NOT NULL,
    resource_type   VARCHAR(64) NOT NULL,                 -- 'quality_check' / 'pipeline' / 'crawler' / 'datasource'
    resource_id     INTEGER,                              -- 关联的具体资源 ID
    trigger_type    VARCHAR(32) NOT NULL,                 -- 'threshold' / 'status_change' / 'execution_timeout' / 'error_rate'
    trigger_config  JSON NOT NULL,                        -- 触发条件: {"metric": "pass_rate", "op": "<", "value": 0.95}
    severity        VARCHAR(16) DEFAULT 'warning',        -- 'info' / 'warning' / 'critical' / 'blocking'
    is_enabled      BOOLEAN DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT (now()),
    updated_at      DATETIME NOT NULL DEFAULT (now()),

    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- 告警规则-通知渠道关联 (M:N)
CREATE TABLE alert_rule_channels (
    rule_id         INTEGER NOT NULL,
    channel_id      INTEGER NOT NULL,
    PRIMARY KEY (rule_id, channel_id),
    FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES notification_channels(id) ON DELETE CASCADE
);

-- 告警历史
CREATE TABLE alert_history (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    rule_id         INTEGER NOT NULL,
    project_id      INTEGER NOT NULL,
    resource_type   VARCHAR(64) NOT NULL,
    resource_id     INTEGER,
    severity        VARCHAR(16) NOT NULL,
    message         TEXT NOT NULL,
    detail          JSON,
    channels_sent   JSON,                                 -- 记录发送到了哪些渠道
    is_acknowledged BOOLEAN DEFAULT FALSE,                -- 是否已确认
    acknowledged_by INTEGER,                              -- 确认人
    acknowledged_at DATETIME,
    created_at      DATETIME NOT NULL DEFAULT (now()),

    INDEX idx_alert_time (project_id, created_at),
    FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

#### 3.5.3 通知触发时机

| 触发场景 | 告警类型 | 示例消息 | 默认渠道 |
|---------|---------|---------|---------|
| 质量检查失败率 > 阈值 | `quality_check` | "数据源 mysql_prod 的 user_info 表质量检查失败率 12%，超过阈值 5%" | 邮件 + 钉钉 |
| Pipeline 执行失败 | `pipeline` | "Pipeline user_data_clean 执行失败，错误: std stage null pointer" | 钉钉 |
| 爬虫任务异常退出 | `crawler` | "爬虫 news_spider 在运行 3h 后异常退出，退出码 137 (OOM)" | 钉钉 |
| 数据源连接断开 | `datasource` | "数据源 clickhouse_bi 连接失败: Connection refused，已持续 5 分钟" | 邮件 + 短信 |
| 项目配额接近上限 | `quota` | "项目 smart-factory 数据源数 48/50，接近配额上限" | 邮件 |

#### 3.5.4 通知 API

```
POST   /api/v1/admin/notification-channels             创建通知渠道 (admin)
GET    /api/v1/admin/notification-channels             通知渠道列表
PUT    /api/v1/admin/notification-channels/{id}        更新渠道配置
POST   /api/v1/admin/notification-channels/{id}/test   测试通知渠道

GET    /api/v1/users/me/notification-prefs             获取当前用户通知偏好
PUT    /api/v1/users/me/notification-prefs             更新通知偏好

GET    /api/v1/projects/{id}/alert-rules               项目告警规则列表
POST   /api/v1/projects/{id}/alert-rules               创建告警规则
PUT    /api/v1/projects/{id}/alert-rules/{rid}         更新告警规则
DELETE /api/v1/projects/{id}/alert-rules/{rid}         删除告警规则

GET    /api/v1/projects/{id}/alert-history              告警历史 (支持时间范围+级别筛选)
POST   /api/v1/projects/{id}/alert-history/{aid}/ack   确认告警
```

---

### 3.6 资源配额与用量监控 (v2.0 增强)

> **来源**: DataWorks 专业版的资源管理有配额限制，防止单项目资源滥用。DataOS 已有 `project_quotas` 表设计，本节补充配额检查的 middleware 和用量展示 API。

```python
# app/core/quota.py — 配额检查中间件

from functools import wraps
from fastapi import HTTPException

class QuotaExceededError(HTTPException):
    """资源配额超限异常."""
    def __init__(self, resource: str, current: int, limit: int):
        super().__init__(
            status_code=429,
            detail=f"项目资源配额不足: {resource} 已达 {current}/{limit}"
        )

async def check_quota(project_id: int, resource_type: str, db: AsyncSession):
    """创建资源前检查配额 — 使用方式: await check_quota(project.id, 'datasource', db)."""
    quota = await db.get(ProjectQuota, project_id)
    if not quota:
        return  # 未配置配额 = 不限制

    current_counts = {
        "datasource": await db.scalar(
            select(func.count(DataSource.id)).where(DataSource.project_id == project_id)
        ),
        "crawler": await db.scalar(
            select(func.count(Crawler.id)).where(Crawler.project_id == project_id)
        ),
        "api": await db.scalar(
            select(func.count(DataApi.id)).where(DataApi.project_id == project_id)
        ),
        "pipeline": await db.scalar(
            select(func.count(Pipeline.id)).where(Pipeline.project_id == project_id)
        ),
        "member": await db.scalar(
            select(func.count(ProjectMember.id)).where(ProjectMember.project_id == project_id)
        ),
        "quality_rule": await db.scalar(
            select(func.count(QualityRule.id)).where(QualityRule.project_id == project_id)
        ),
    }

    limit = getattr(quota, f"max_{resource_type}s", None)
    current = current_counts.get(resource_type, 0)

    if limit is not None and current >= limit:
        raise QuotaExceededError(resource=resource_type, current=current, limit=limit)
```

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

-- 预置角色 (v2.0 扩展为 8 个系统角色)
INSERT INTO roles (name, display_name, description, scope, is_system) VALUES
('super_admin',   '超级管理员',   '平台最高权限，管理所有资源和用户',                    'global',  TRUE),
('admin',         '平台管理员',   '管理用户和全局配置，可穿透所有项目',                  'global',  TRUE),
('project_owner', '项目负责人',   '项目最高权限，管理所有资源和成员，可转让和删除项目',   'project', TRUE),
('project_admin', '项目管理员',   '管理项目成员和资源，不可删除项目和转让所有权',        'project', TRUE),
('developer',     '开发者',       '创建/修改/运行数据开发任务，不可删除资源和发布上线',  'project', TRUE),
('operator',      '运维者',       '启停/执行/监控任务和数据源，不可创建和修改任务',      'project', TRUE),
('editor',        '编辑者',       '创建和修改数据源配置，不可删除和运行任务',            'project', TRUE),
('viewer',        '查看者',       '只读查看项目内所有资源',                             'project', TRUE);
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
    "editor": 1.5,
    "operator": 2,
    "developer": 2.5,
    "project_admin": 3,
    "project_owner": 4,
    "admin": 5,
    "super_admin": 6,
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

### 8.1 开发任务 (v2.0 更新)

| 序号 | 功能 | 优先级 | 工作量 | 依赖 | 版本 |
|------|------|:---:|--------|------|:---:|
| **Phase 0: 当前已有 (代码已完成)** |||||
| 0.1 | Role + Permission + RolePermission 模型 + seed | ✅ 完成 | — | — | v1.0 |
| 0.2 | ProjectMember 改造 (role_id FK) | ✅ 完成 | — | — | v1.0 |
| 0.3 | UserRole 模型 (全局角色) | ✅ 完成 | — | — | v1.0 |
| 0.4 | require_permission / require_project_role 守卫 | ✅ 完成 | — | — | v1.0 |
| 0.5 | 全局角色穿透 (admin bypass) | ✅ 完成 | — | — | v1.0 |
| 0.6 | 项目 CRUD + 成员管理 API | ✅ 完成 | — | — | v1.0 |
| 0.7 | 项目转让 API | ✅ 完成 | — | — | v1.0 |
| 0.8 | 项目 freeze/unfreeze API | ✅ 完成 | — | — | v1.0 |
| 0.9 | 审计日志基础 (手动记录) | ✅ 完成 | — | — | v1.0 |
| **Phase 1: 核心补强 (v1.5)** |||||
| 1.1 | **P0 修复: 权限 Redis 缓存 (PermissionCache)** | P0 | 0.3天 | 0.4 | v1.5 |
| 1.2 | **P0 修复: 项目列表分页 (服务端)** | P0 | 0.2天 | 0.6 | v1.5 |
| 1.3 | 角色扩充: 新增 project_admin / developer / operator | P0 | 0.3天 | 0.1 | v1.5 |
| 1.4 | 更新权限矩阵: 新角色的 permission 绑定 | P0 | 0.2天 | 1.3 | v1.5 |
| 1.5 | 用户搜索/自动完成 API (成员管理用) | P1 | 0.2天 | — | v1.5 |
| 1.6 | Token 刷新机制 (refresh token) | P1 | 0.3天 | — | v1.5 |
| 1.7 | 审计日志中间件 (AOP 自动记录) | P1 | 0.5天 | 0.9 | v1.5 |
| 1.8 | 审计日志查询 API (分页+筛选) | P1 | 0.2天 | 1.7 | v1.5 |
| 1.9 | 数据源密码加密 (crypto.py Fernet) | P1 | 0.2天 | — | v1.5 |
| 1.10 | 前端用户搜索组件 (Select+Search) | P1 | 0.2天 | 1.5 | v1.5 |
| 1.11 | 前端角色管理页 (admin only) | P1 | 0.3天 | 1.3 | v1.5 |
| **Phase 2: 环境隔离 + 告警 (v2.0)** |||||
| 2.1 | 项目 modes (simple/standard) 字段 | P1 | 0.1天 | — | v2.0 |
| 2.2 | project_environments 表 + CRUD API | P1 | 0.3天 | 2.1 | v2.0 |
| 2.3 | 资源表增加 environment 字段 | P1 | 0.2天 | 2.2 | v2.0 |
| 2.4 | 环境感知的资源列表查询 (?environment=) | P1 | 0.3天 | 2.3 | v2.0 |
| 2.5 | 发布流程 (dev→prod publish) | P1 | 0.5天 | 2.4 | v2.0 |
| 2.6 | 通知渠道表 + CRUD API | P1 | 0.3天 | — | v2.0 |
| 2.7 | 告警规则表 + CRUD API | P1 | 0.3天 | 2.6 | v2.0 |
| 2.8 | 告警引擎 (规则检查+消息发送) | P1 | 0.5天 | 2.7 | v2.0 |
| 2.9 | 告警历史表 + 确认 API | P1 | 0.2天 | 2.8 | v2.0 |
| 2.10 | 项目配额 middleware (check_quota) | P2 | 0.3天 | 0.6 | v2.0 |
| 2.11 | 前端环境切换器组件 | P2 | 0.2天 | 2.4 | v2.0 |
| 2.12 | 前端告警规则配置页 | P2 | 0.3天 | 2.7 | v2.0 |
| **Phase 3: 数据建模 (v2.1)** |||||
| 3.1 | data_domains 表 + 树形 CRUD API | P2 | 0.3天 | — | v2.1 |
| 3.2 | business_processes 表 + CRUD API | P2 | 0.2天 | 3.1 | v2.1 |
| 3.3 | data_standards 表 + CRUD API | P2 | 0.3天 | 3.1 | v2.1 |
| 3.4 | 数据源关联数据域 (datasources.domain_id) | P2 | 0.1天 | 3.1 | v2.1 |
| 3.5 | metrics 表 (原子/派生/复合) | P3 | 0.3天 | 3.1 | v2.1 |
| 3.6 | 前端数据域管理页 (树形+拖拽) | P3 | 0.5天 | 3.1 | v2.1 |
| 3.7 | 前端数据标准管理页 | P3 | 0.3天 | 3.3 | v2.1 |
| **集成与测试** |||||
| T.1 | 权限矩阵集成测试 (pytest) | P1 | 0.3天 | 1.4 | v1.5 |
| T.2 | 环境隔离 E2E 测试 (Playwright) | P1 | 0.3天 | 2.5 | v2.0 |
| T.3 | 告警规则集成测试 | P2 | 0.2天 | 2.8 | v2.0 |
| | **Phase 1 小计** | | **~2.9 天** | | |
| | **Phase 2 小计** | | **~3.5 天** | | |
| | **Phase 3 小计** | | **~2.0 天** | | |
| | **总计** | | **~8.4 天** | | |

### 8.2 新增/修改文件清单 (v2.0)

| 文件 | 说明 | 版本 |
|------|------|:---:|
| `app/models/role.py` | Role + Permission + RolePermission 模型 | ✅ v1.0 |
| `app/models/project_member.py` | ProjectMember + UserRole 模型 | ✅ v1.0 |
| `app/models/audit_log.py` | AuditLog 模型 | ✅ v1.0 |
| `app/models/project_quota.py` | ProjectQuota 模型 | v2.0 |
| `app/models/project_environment.py` | **新增** ProjectEnvironment 模型 | v2.0 |
| `app/models/data_domain.py` | **新增** DataDomain + BusinessProcess 模型 | v2.1 |
| `app/models/data_standard.py` | **新增** DataStandard 模型 | v2.1 |
| `app/models/metric.py` | **新增** Metric 模型 | v2.1 |
| `app/models/notification.py` | **新增** NotificationChannel + UserNotificationPref 模型 | v2.0 |
| `app/models/alert.py` | **新增** AlertRule + AlertHistory 模型 | v2.0 |
| `app/core/deps.py` | get_current_user / require_permission / require_project_role / PermissionCache | ✅ v1.0 |
| `app/core/crypto.py` | 敏感字段加密/解密 (Fernet) | v1.5 |
| `app/core/quota.py` | **新增** 配额检查 middleware | v2.0 |
| `app/api/projects.py` | 项目 CRUD + 成员管理 + 转让 + 环境管理 | v1.0+v2.0 |
| `app/api/permissions.py` | 角色和权限管理 CRUD API | ✅ v1.0 |
| `app/api/audit.py` | 审计日志查询 API | v1.5 |
| `app/api/notifications.py` | **新增** 通知渠道和告警规则 API | v2.0 |
| `app/api/domains.py` | **新增** 数据域和业务过程 API | v2.1 |
| `app/middleware/audit.py` | 审计日志自动记录中间件 | v1.5 |
| `app/middleware/alert.py` | **新增** 告警引擎 (规则检查+消息发送) | v2.0 |
| `app/tasks/alert_checker.py` | **新增** 后台告警检查定时任务 | v2.0 |
| `platform/frontend/src/hooks/usePermission.ts` | 前端权限 Hook | ✅ v1.0 |
| `platform/frontend/src/pages/ProjectSettings.tsx` | 项目设置页 (成员+环境+告警) | v1.5 |
| `platform/frontend/src/pages/ProjectDomains.tsx` | **新增** 数据域管理页 | v2.1 |
| `platform/frontend/src/pages/AlertRules.tsx` | **新增** 告警规则配置页 | v2.0 |
| `platform/frontend/src/components/UserSelect.tsx` | **新增** 用户搜索选择组件 | v1.5 |
| `platform/frontend/src/components/EnvSwitcher.tsx` | **新增** 环境切换器组件 | v2.0 |
| `components/mysql/init/02-seed-rbac.sql` | 预置 8 角色 + 37 权限 + 初始 admin | v1.0+v2.0 |
| `components/mysql/migrations/` | **新增** 数据库迁移脚本目录 | v1.5 |

### 8.3 大厂对齐设计决策总结 (v2.0)

> 每个设计决策都标注了来源平台和原因，确保不是"为了功能而功能"。

| # | 设计决策 | 对齐来源 | 决策原因 |
|---|---------|---------|---------|
| 1 | **双范围 RBAC + 权限并集** | DataOS 原创 | DataWorks/Dataphin 的权限是登录时固化，DataOS 每次请求动态计算，角色变更即时生效，更适合自建部署场景 |
| 2 | **8 角色体系 (3全局+6项目)** | DataWorks 专业版 | DataWorks 有空间管理员/开发/运维/访客/安全管理员/模型设计师。DataOS 先对齐核心角色，安全管理员和模型设计师留到 v2.2 |
| 3 | **project_admin 角色** | Dataphin 代理负责人 | Dataphin 有"项目负责人"和"项目管理员"的区分。企业场景中 Owner 通常是业务负责人，日常管理需要 project_admin 代理 |
| 4 | **developer/operator 拆分** | DataWorks 开发运维分离 | DataWorks 标准模式中，开发角色只能在 DEV 环境编辑，运维角色负责 PROD 环境的启停和监控。DataOS 对齐此模型 |
| 5 | **simple/standard 双模式** | DataWorks 简单/标准模式 | DataWorks 基础版只有简单模式(单环境)，专业版才有标准模式(双环境)。DataOS 也提供两种模式，向后兼容 |
| 6 | **环境隔离 (dev/prod)** | DataWorks 标准模式+DataLeap | DataWorks 的标准模式工作空间是最核心的差异化能力，DataLeap 也有类似的双环境设计。这是 DataOS 当前最大的功能缺口 |
| 7 | **数据域+业务过程建模** | Dataphin OneData | Dataphin 的核心方法论——先建模再开发。DataOS 目前的"先连接数据源再做处理"缺少标准化环节 |
| 8 | **发布流程 (dev→prod)** | DataWorks 发布中心 | 发布时校验目标环境连接+质量规则+依赖，对标 DataWorks 的发布前检查 |
| 9 | **数据标准管理** | Dataphin 数据标准 | 字段命名、类型、值域的统一标准化，是 DataOS 从"ETL 工具"升级为"治理平台"的标志 |
| 10 | **指标管理 (原子→派生→复合)** | Dataphin 指标字典 | 指标唯一归属+可追溯，是企业级数据治理的核心能力 |
| 11 | **通知告警+多通道** | DataWorks 质量监控+WeData | DataWorks 支持邮件/短信/钉钉/Webhook 四通道告警。DataOS 对齐此设计 |
| 12 | **Fernet 配置加密+API脱敏** | DataWorks KMS 集成 | DataWorks 用阿里云 KMS 加密，DataOS 自建部署用 Fernet(AES-128)，设计思路一致 |
| 13 | **全量审计日志+diff** | DataWorks 操作审计+DataLeap | 所有大厂平台都有审计日志。DataOS 多做了 before/after diff 记录，在自建场景中更有用 |
| 14 | **服务端分页+搜索** | DataWorks 项目管理列表 | DataOS 当前是客户端分页，已有代码对所有项目做全量查询。改为服务端分页减少传输量 |
| 15 | **资源配额 middleware** | DataWorks 配额管理 | DataWorks 专业版有资源组和配额限制。DataOS 的 project_quotas 表设计对齐此功能 |
| 16 | **Token 刷新机制** | 行业标配 | DataOS 当前 JWT 有效期8小时无刷新，补充 refresh token 是安全基础要求 |
| 17 | **组件代理统一抽象 (ComponentClient)** | DataOS 原创 | 所有外部 OSS (DolphinScheduler/OpenMetadata/SeaTunnel) 通过统一 Client 类访问，可换可替换 |

### 8.4 P0 修复亮点总结

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
