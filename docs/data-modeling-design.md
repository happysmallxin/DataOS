# 数据建模模块 — 技术详细设计

> 基于 MES 数据集平台文档 §3.3 数据建模管理操作 + §5 MES标准数据模型设计
> 版本: v1.0 | 日期: 2026-06-09

---

## 一、模块定位

将清洗后的 Gold 表数据抽象为公司级 MES 标准模型。按主题域设计维度表和事实表，建立字段字典、主键外键关联和模型版本发布。

**核心链路**: 主题域 → 业务过程 → 模型表(DIM/FACT/DWD/DWS/ADS) → 模型字段 → 关联关系 → 版本发布

---

## 二、业务流程

### 2.1 建模步骤 (对齐 MES 文档 §4.4)

```
1. 主题域拆分 → 2. 维度建模 → 3. 事实建模 → 4. 字段定义 → 5. 关联设计 → 6. 版本发布
```

### 2.2 详细操作

| 步骤 | 操作 | 产物 |
|------|------|------|
| 1. 主题域拆分 | 将 MES 数据划分为生产调度、生产执行、质量管理、基础维度等主题 | 主题域清单 |
| 2. 维度建模 | 抽象人员、物料、产品、工厂、工作中心、工作单元、工序、设备等维度 | 维度表模型 |
| 3. 事实建模 | 围绕订单、工单、派工、执行、报工、检测、反馈、返修等业务过程设计事实表 | 事实表模型 |
| 4. 字段定义 | 为每张模型表定义字段编码、字段名称、字段含义、字段类型、来源字段、质量规则 | 模型字段字典 |
| 5. 关联设计 | 通过订单号、工单号、派工单号、物料编码、工序编码等建立关联链路 | 模型关系图 |
| 6. 版本发布 | 模型审核后形成版本，后续数据集只能基于已发布模型生成 | 模型版本记录 |

---

## 三、数据库表设计

### 3.1 已有表 (保持)

| 表 | 用途 |
|------|------|
| `data_domains` | 数据域，树形层级 |
| `business_processes` | 业务过程，归属数据域 |

### 3.2 新增表

#### model_tables — 模型表定义

```sql
CREATE TABLE model_tables (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id INTEGER NOT NULL,
    process_id INTEGER NOT NULL,             -- 归属业务过程
    domain_id INTEGER NOT NULL,              -- 归属数据域(冗余, 快速查询)
    code VARCHAR(128) NOT NULL,              -- 模型表编码: dim_employee
    name VARCHAR(256) NOT NULL,              -- 模型表名称: 人员维度表
    table_type VARCHAR(32) NOT NULL DEFAULT 'DIM',  -- DIM/FACT/DWD/DWS/ADS
    description TEXT,
    primary_key_field VARCHAR(128),          -- 主键字段名
    source_gold_table VARCHAR(128),          -- 来源 Gold 表名
    target_gold_table VARCHAR(128),          -- 目标 Gold 表名 (自动生成DDL)
    version VARCHAR(32) DEFAULT '1.0',
    status VARCHAR(32) DEFAULT 'draft',      -- draft/published/archived
    relation_data JSON,                      -- 关联关系列表
    created_by INTEGER NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW(),
    UNIQUE KEY uq_model_code (project_id, code),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (process_id) REFERENCES business_processes(id) ON DELETE CASCADE,
    FOREIGN KEY (domain_id) REFERENCES data_domains(id) ON DELETE RESTRICT
);
```

#### model_fields — 模型字段字典

```sql
CREATE TABLE model_fields (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    model_table_id INTEGER NOT NULL,         -- 归属模型表
    code VARCHAR(128) NOT NULL,              -- 字段编码: EMPLOYEE_CODE
    name VARCHAR(256) NOT NULL,              -- 字段名称: 人员编码
    description TEXT,                        -- 字段含义
    data_type VARCHAR(64) NOT NULL DEFAULT 'VARCHAR',  -- 字段类型
    length INTEGER,
    precision INTEGER,
    nullable BOOLEAN DEFAULT FALSE,
    default_value VARCHAR(256),
    is_primary_key BOOLEAN DEFAULT FALSE,
    is_foreign_key BOOLEAN DEFAULT FALSE,
    ref_table VARCHAR(128),                  -- 关联表: dim_employee
    ref_field VARCHAR(128),                  -- 关联字段: EMPLOYEE_CODE
    source_field VARCHAR(128),               -- 来源字段 (Gold表字段名)
    quality_rule VARCHAR(256),               -- 质量规则: not_null / unique
    standard_id INTEGER,                     -- 关联数据标准
    category VARCHAR(32) DEFAULT 'dimension', -- dimension/measure/status/time/relation
    sort_order INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (model_table_id) REFERENCES model_tables(id) ON DELETE CASCADE,
    FOREIGN KEY (standard_id) REFERENCES data_standards(id) ON DELETE SET NULL
);
```

#### model_versions — 模型版本

```sql
CREATE TABLE model_versions (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    model_table_id INTEGER NOT NULL,
    version VARCHAR(32) NOT NULL,
    status VARCHAR(32) DEFAULT 'draft',
    changelog TEXT,
    fields_snapshot JSON,                    -- 字段快照
    published_by INTEGER,
    published_at DATETIME,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (model_table_id) REFERENCES model_tables(id) ON DELETE CASCADE
);
```

---

## 四、API 设计

### 4.1 模型表 CRUD

```
POST   /api/v1/projects/{id}/model-tables                    创建模型表
GET    /api/v1/projects/{id}/model-tables?domain_id=&type=   模型表列表
GET    /api/v1/projects/{id}/model-tables/{mid}              模型表详情
PUT    /api/v1/projects/{id}/model-tables/{mid}              更新模型表
DELETE /api/v1/projects/{id}/model-tables/{mid}              删除模型表

POST   /api/v1/projects/{id}/model-tables/{mid}/publish      发布版本
GET    /api/v1/projects/{id}/model-tables/{mid}/versions      版本历史

POST   /api/v1/projects/{id}/model-tables/{mid}/ddl           生成并执行 DDL
```

### 4.2 模型字段 CRUD

```
GET    /api/v1/model-tables/{mid}/fields                      字段列表
POST   /api/v1/model-tables/{mid}/fields                      添加字段
PUT    /api/v1/model-tables/{mid}/fields/{fid}                更新字段
DELETE /api/v1/model-tables/{mid}/fields/{fid}                删除字段

POST   /api/v1/model-tables/{mid}/fields/import               从 Gold 表导入字段
```

### 4.3 Gold 表引用

```
GET    /api/v1/projects/{id}/gold-tables                      已实现的端点
GET    /api/v1/projects/{id}/gold-tables/{t}/columns          已实现的端点
```

---

## 五、MES 标准模型表参考 (对齐文档 §5)

### 5.1 基础维度 (DIM)

| 模型表编码 | 模型表名称 | 关键字段 |
|------|------|------|
| `dim_employee` | 人员维度表 | EMPLOYEE_CODE, EMPLOYEE_NAME, QUALIFICATION_CODE |
| `dim_material` | 物料维度表 | MRL_CODE, MRL_NAME |
| `dim_product` | 产品维度表 | PRODUCT_CODE, PRODUCT_NAME |
| `dim_site` | 工厂维度表 | SITE_CODE, SITE_NAME |
| `dim_work_center` | 工作中心维度表 | WORK_CENTER_CODE, WORK_CENTER_NAME |
| `dim_work_cell` | 工作单元维度表 | WORK_CELL_CODE, WORK_CELL_NAME |
| `dim_route_operation` | 工序维度表 | ROUTE_CODE, OPERATION_CODE |
| `dim_equipment` | 设备维度表 | EQUIPMENT_CODE, EQUIPMENT_NAME |

### 5.2 生产调度 (FACT)

| 模型表编码 | 模型表名称 | 关键字段 | 关联维度 |
|------|------|------|------|
| `fact_plan_order` | 计划订单事实表 | PLAN_ORDER_CODE, PLAN_QTY | dim_product, dim_site |
| `fact_work_order` | 生产工单事实表 | WORK_ORDER_CODE, PLAN_ORDER_CODE | dim_material, dim_work_center |
| `fact_task_order` | 派工单事实表 | TASK_ORDER_CODE, WORK_ORDER_CODE | dim_employee, dim_work_cell, dim_route_operation |

### 5.3 生产执行 (FACT)

| 模型表编码 | 模型表名称 | 关联维度 |
|------|------|------|
| `fact_making_order` | 制造工单事实表 | dim_employee, dim_work_cell, dim_equipment |
| `fact_track_record` | 执行记录事实表 | dim_employee, dim_work_cell |
| `fact_daq_info` | 采集报工事实表 | dim_employee, dim_route_operation |

### 5.4 质量管理 (FACT)

| 模型表编码 | 关联维度 |
|------|------|
| `fact_quality_check_mrl` | dim_material |
| `fact_quality_check_wip` | dim_route_operation |
| `fact_quality_feedback` | dim_employee |
| `fact_rework_online` | dim_employee, dim_route_operation |

### 5.5 核心业务链路

```
计划订单 → 生产工单 → 派工单 → 执行记录 → 质量检测 → 反馈/返修
PLAN_ORDER → WORK_ORDER → TASK_ORDER → TRACK_ORDER → CHK_BILL → FEEDBACK/REWORK
```

---

## 六、前端页面设计

### 6.1 页面布局

```
┌─────────────────────────────────────────────────────────┐
│  数据建模                                  项目: [演示 ▾]│
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─ 数据域 ──────────────────────────────────────────┐  │
│  │ [生产调度] [生产执行] [质量管理] [基础维度]         │  │
│  │ [+ 新增数据域]                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ 模型表 ──────────────────────────────────────────┐  │
│  │ 数据域: [全部 ▾]  类型: [全部 ▾]  [+ 新建模型表]   │  │
│  │                                                    │  │
│  │ ┌──────────────────────────────────────────────┐   │  │
│  │ │ dim_employee  人员维度表  DIM  v1.0  已发布   │   │  │
│  │ │ 字段: EMPLOYEE_CODE, EMPLOYEE_NAME, 资质编码   │   │  │
│  │ │ 主键: EMPLOYEE_CODE                           │   │  │
│  │ │ [编辑字段] [生成DDL] [发布]                    │   │  │
│  │ └──────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
│  ┌─ 模型关系图 ──────────────────────────────────────┐  │
│  │  fact_work_order ─→ dim_employee                   │  │
│  │                  ─→ dim_material                   │  │
│  │                  ─→ dim_work_center                │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 6.2 模型表详情/编辑弹窗

```
┌──────────────────────────────────────────┐
│  编辑模型表: dim_employee                │
│                                          │
│  编码: [dim_employee]                    │
│  名称: [人员维度表]                       │
│  类型: [DIM ▾]  数据域: [基础维度 ▾]      │
│  主键: [EMPLOYEE_CODE ▾]                │
│  来源表: [employees ▾] (PG Gold)         │
│  描述: [...]                             │
│                                          │
│  ── 字段列表 ──────────────────────────  │
│  ┌────────────────────────────────────┐  │
│  │ 编码         名称   类型    主键 关联│  │
│  │ EMPLOYEE_CODE 人员编码 VARCHAR ✓   — │  │
│  │ EMPLOYEE_NAME 人员名称 VARCHAR —   — │  │
│  │ QUAL_CODE    资质编码 VARCHAR —   — │  │
│  │              [+ 添加字段]          │  │
│  └────────────────────────────────────┘  │
│                                          │
│  [从Gold表导入字段] [生成DDL] [保存]      │
└──────────────────────────────────────────┘
```

### 6.3 添加字段弹窗

```
┌──────────────────────────────────┐
│  添加字段                        │
│                                  │
│  编码: [EMPLOYEE_CODE]           │
│  名称: [人员编码]                 │
│  含义: [人员唯一编码]              │
│  类型: [VARCHAR(50) ▾]           │
│  主键: ☑                         │
│  外键: ☐ → 关联表: [...]        │
│  来源字段: [code] (Gold表)       │
│  分类: [dimension ▾]             │
│  质量规则: [not_null]            │
│  关联标准: [DS-USER-001 ▾]       │
└──────────────────────────────────┘
```
