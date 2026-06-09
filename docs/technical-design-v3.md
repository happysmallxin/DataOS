# DataOS 技术详细设计文档 v3.0

> 基于 MES 数据集平台架构，10 个模块的完整技术设计  
> 每个模块包含：定位、业务流程、数据库表、API 端点、前端页面

---

## 一、数据接入模块

### 1.1 定位
负责各客户 MES 项目数据源的登记、连接、元数据扫描和初次采集。

### 1.2 业务流程
```
新增数据源 → 测试连接 → 元数据扫描 → 选择采集表 → 配置同步方式 → 执行初次采集 → 查看同步日志
```

### 1.3 数据库表 (已完成)
| 表 | 关键字段 |
|------|------|
| `datasources` | id, name, source_type, config(JSON加密), status, last_sync_at |
| `sync_history` | datasource_id, table_name, sync_mode, total_rows, storage_path, sync_column, last_sync_value |

### 1.4 已支持的数据源类型 (15种)
MySQL, PostgreSQL, MongoDB, Redis, Kafka, Elasticsearch, S3/MinIO, HDFS, Hive, ClickHouse, Doris, REST API, Web Crawler, File Upload, SQL File

### 1.5 已实现 API
```
POST   /api/v1/datasources/{id}/test-connection   测试连接
POST   /api/v1/datasources/{id}/tables              元数据扫描(表列表+字段)
POST   /api/v1/datasources/{id}/tables/{t}/preview  数据预览(前100行)
POST   /api/v1/datasources/{id}/sync                全量/增量同步
POST   /api/v1/datasources/{id}/sync-all            批量同步
GET    /api/v1/datasources/{id}/sync-history         同步历史
```

### 1.6 前端页面
`DataSources.tsx` — 数据源列表 + 创建表单 + 测试连接按钮 + 同步弹窗(选表/预览/同步) + 同步历史抽屉

---

## 二、数据标准模块

### 2.1 定位
维护公司级 MES 数据元素定义、字段命名标准、编码字典和字段映射关系。这是平台最核心的差异化能力——将不同项目的差异化字段统一到公司标准。

### 2.2 业务流程
```
创建标准字段库 → 项目接入后自动扫描字段 → 字段映射(自动+手动) → 编码字典配置 → 标准校验
```

### 2.3 核心能力：字段映射引擎

**自动映射算法**:
```python
# 模糊匹配: 源字段名与标准字段code/name的相似度
def auto_map(source_field: str, standards: list) -> Standard:
    for std in standards:
        # 精确匹配
        if source_field.lower() == std.code.lower(): return std
        # 包含匹配
        if source_field.lower() in std.code.lower(): return std
        if std.code.lower() in source_field.lower(): return std
        # 名称相似
        if std.name.lower() == source_field.lower(): return std
    return None  # 无法自动匹配, 需手动指定
```

### 2.4 数据库表 (已完成)
| 表 | 关键字段 |
|------|------|
| `data_standards` | id, code, name, data_type, category, scope(global/project), quality_rule |
| `field_mappings` | id, source_table, source_field, standard_id(→data_standards), transform_rule, confidence |
| `code_dictionaries` | id, name, code, source_value, standard_value |

### 2.5 标准字段分类 (category)
| 分类 | 说明 | 示例 |
|------|------|------|
| `dimension` | 维度字段 | EMPLOYEE_CODE, MRL_CODE, WORK_CENTER_CODE |
| `measure` | 指标字段 | PLAN_QTY, COMPLETE_QTY, QUALIFIED_QTY |
| `status` | 状态字段 | ORDER_STATUS, TASK_STATUS, CHECK_RESULT |
| `time` | 时间字段 | PLAN_START_TIME, ACTUAL_END_TIME |
| `relation` | 关联字段 | WORK_ORDER_CODE, TASK_ORDER_CODE |

### 2.6 已实现 API
```
GET/POST/DELETE /api/v1/projects/{id}/standards       标准字段CRUD
GET/POST         /api/v1/projects/{id}/mappings         字段映射CRUD
POST             /api/v1/projects/{id}/mappings/auto    自动映射(模糊匹配)
GET/POST         /api/v1/projects/{id}/code-dicts       编码字典CRUD
```

### 2.7 前端页面
项目详情 → `数据标准` Tab: 标准字段卡片 + 字段映射卡片 + 编码字典卡片

---

## 三、数据清洗模块

### 3.1 定位
对接入数据执行结构检查和规则化预处理。对齐 MES 文档中的 9 种清洗类型。

### 3.2 清洗类型 (对齐 MES 文档)

| 类型 | 处理内容 | 规则示例 |
|------|---------|---------|
| 结构检查 | 字段存在性、类型、长度 | 工单号字段必须存在且为字符型 |
| 主键唯一性 | 关键单据编码唯一非空 | 工单号/订单号/派工单号不可为空且唯一 |
| 空值处理 | 关键字段空值填充/过滤 | 必填字段空值记录不入模型 |
| 重复记录 | 按主键去重 | 按更新时间保留最新记录 |
| 编码映射 | 编码字段标准化 | 产品编码/物料编码映射到标准字段 |
| 状态标准化 | 数值/文本状态统一 | 0/1/2/3 → 未发布/部分发布/已发布/完工 |
| 时间逻辑校验 | 时间先后关系 | 开始<结束, 采集时间在合理周期内 |
| 数量合理性 | 数量非负, 合计关系 | 良品+不良品+报废=报工总数 |
| 脱敏处理 | 敏感字段屏蔽 | hashed_password/is_superuser 不进入模型 |

### 3.3 Pipeline 7 阶段引擎 (已完成)
```
画像(Profile) → 标准化(Standardize) → 插补(Imputation) → 去重(Dedup)
  → 异常检测(Outliers) → 业务规则(BusinessRules) → 质量门控(QualityGate)
```

### 3.4 数据库表 (已完成)
| 表 | 关键字段 |
|------|------|
| `cleaning_pipelines` | id, name, stages(JSON), datasource_id, source_table, target_table, version |

### 3.5 已实现 API
```
POST   /api/v1/cleaning/pipelines              创建Pipeline
GET    /api/v1/cleaning/pipelines?project_id=    列表
GET    /api/v1/cleaning/pipelines/{id}            详情
PUT    /api/v1/cleaning/pipelines/{id}            更新(version++)
DELETE /api/v1/cleaning/pipelines/{id}            删除
POST   /api/v1/cleaning/pipelines/run             执行(自动读Bronze→写Silver+Gold)
POST   /api/v1/cleaning/profile                   数据画像
GET    /api/v1/cleaning/stages                    可用阶段列表
```

### 3.6 前端页面
项目详情 → `Pipeline` Tab: 卡片列表 + 新建弹窗 + 执行/删除按钮 + 执行结果展示

**待优化**: MES 文档中的"清洗前后对比"和"问题清单导出"功能尚未实现，需新增清洗结果对比视图。

---

## 四、数据建模模块

### 4.1 定位
将项目数据抽象为公司级 MES 标准模型。按主题域设计维度表和事实表，建立字段字典和关联关系。

### 4.2 建模步骤 (对齐 MES 文档)
```
1. 主题域拆分 → 2. 维度建模 → 3. 事实建模 → 4. 字段定义 → 5. 关联设计 → 6. 版本发布
```

### 4.3 模型类型
| 类型 | 含义 | MES 示例 |
|------|------|---------|
| `DIM` 维度表 | 描述业务对象 | dim_employee, dim_material, dim_work_center |
| `FACT` 事实表 | 记录业务过程 | fact_work_order, fact_quality_check |
| `DWD` 明细表 | 清洗后原子数据 | dwd_task_execution |
| `DWS` 汇总表 | 聚合统计数据 | dws_daily_output |
| `ADS` 应用表 | 面向应用场景 | ads_production_report |

### 4.4 MES 标准模型表建议 (对齐文档 §5)
| 主题域 | 类型 | 建议模型表 |
|------|------|------|
| 基础维度 | DIM | dim_employee, dim_material, dim_product, dim_site, dim_work_center, dim_work_cell, dim_route_operation, dim_equipment |
| 生产调度 | FACT | fact_plan_order, fact_work_order, fact_task_order |
| 生产执行 | FACT | fact_making_order, fact_track_record, fact_daq_info |
| 质量管理 | FACT | fact_quality_check_mrl, fact_quality_check_wip, fact_quality_feedback, fact_rework_online |

### 4.5 核心业务链路
```
计划订单 → 生产工单 → 派工单 → 执行记录 → 质量检测 → 反馈/返修
PLAN_ORDER → WORK_ORDER → TASK_ORDER → TRACK_ORDER → CHK_BILL → FEEDBACK/REWORK
```

### 4.6 数据库表 (已完成)
| 表 | 关键字段 |
|------|------|
| `data_domains` | id, name, display_name, parent_id(树形), scope(global/project) |
| `business_processes` | id, domain_id, name, table_type, source_tables, target_tables, view_sql |

### 4.7 已实现 API
```
POST/GET/PUT/DELETE /api/v1/projects/{id}/domains                 数据域CRUD(树形)
POST/GET/PUT/DELETE /api/v1/projects/{id}/processes               业务过程CRUD
POST   /api/v1/projects/{id}/processes/{pid}/create-view          创建视图
POST   /api/v1/projects/{id}/domains/{did}/processes              创建业务过程(自动DDL+Pipeline)
GET    /api/v1/projects/{id}/gold-tables                           Gold表列表
GET    /api/v1/projects/{id}/gold-tables/{t}/columns               Gold表列定义
```

### 4.8 自动 DDL 生成 (已完成)
创建业务过程时自动:
1. 读取源表结构 → 2. 排除敏感字段 → 3. 检测主键 → 4. 生成DDL → 5. 执行建表 → 6. 自动创建Pipeline

### 4.9 前端页面
项目详情 → `数据建模` Tab: 数据域列表 + 业务过程表格 + 新增弹窗(含自定义SQL视图)

**待优化**: MES 文档中的"关系图生成"和"模型版本对比"功能尚未实现。

---

## 五、标签分类模块 (待实现)

### 5.1 定位
为模型表、字段和数据集增加可检索、可筛选、可复用的多维度标签。

### 5.2 标签类型 (对齐 MES 文档)
| 类型 | 说明 | 示例值 |
|------|------|------|
| `business` 业务主题 | 数据所属业务领域 | 生产调度、生产执行、质量管理 |
| `field_type` 字段类型 | 字段在模型中的角色 | 维度字段、指标字段、状态字段 |
| `quality` 质量 | 数据质量评级 | 已验证、待整改、高风险 |
| `status` 状态 | 数据生命周期状态 | 草稿、已发布、已归档 |
| `time_granularity` 时间粒度 | 数据时间维度 | 实时、日、周、月 |
| `scenario` 适用场景 | 数据可用的业务场景 | 报表、大屏、分析、API |

### 5.3 数据库表设计
```sql
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL,          -- 标签名称
    type VARCHAR(32) NOT NULL,           -- business/field_type/quality/status/time_granularity/scenario
    color VARCHAR(32) DEFAULT '#1890ff', -- 标签颜色
    description TEXT,
    created_at DATETIME DEFAULT NOW(),
    UNIQUE KEY uq_tag (name, type)
);

CREATE TABLE taggables (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    tag_id INTEGER NOT NULL,
    taggable_type VARCHAR(64) NOT NULL,  -- domain/model_table/field/dataset
    taggable_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT NOW(),
    UNIQUE KEY uq_taggable (tag_id, taggable_type, taggable_id),
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
```

### 5.4 待实现 API
```
GET/POST/PUT/DELETE /api/v1/tags                  标签CRUD
GET/POST/DELETE     /api/v1/{type}/{id}/tags       对象关联标签
```

---

## 六、数据集生成模块 (待实现)

### 6.1 定位
基于已发布模型生成面向使用的版本化数据集。

### 6.2 生成流程 (对齐 MES 文档)
```
选择主题域 → 选择模型表 → 配置输出字段 → 设置标签 → 配置版本/更新周期/格式 
→ 预览数据 → 执行生成 → 质量校验 → 通过验收 → 发布
```

### 6.3 数据库表设计
```sql
CREATE TABLE datasets (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(256) NOT NULL,
    version VARCHAR(32) NOT NULL,
    description TEXT,
    domain_id INTEGER,
    model_tables JSON NOT NULL,           -- 包含的模型表ID列表
    output_fields JSON NOT NULL,          -- 输出字段配置
    tags JSON,                            -- 关联标签
    update_cycle VARCHAR(64),             -- 更新周期: daily/weekly/monthly/once
    export_format VARCHAR(64) DEFAULT 'parquet',  -- CSV/Parquet/JSON
    storage_path VARCHAR(512),
    total_rows INTEGER DEFAULT 0,
    total_size_bytes INTEGER DEFAULT 0,
    quality_score FLOAT,                  -- 质量评分 (0-100)
    status VARCHAR(32) DEFAULT 'draft',   -- draft/generating/validating/published/rejected
    created_by INTEGER,
    created_at DATETIME DEFAULT NOW(),
    published_at DATETIME,
    FOREIGN KEY (domain_id) REFERENCES data_domains(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE dataset_versions (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    dataset_id INTEGER NOT NULL,
    version VARCHAR(32) NOT NULL,
    status VARCHAR(32) DEFAULT 'draft',
    total_rows INTEGER DEFAULT 0,
    storage_path VARCHAR(512),
    quality_report JSON,                  -- 质量校验报告
    changelog TEXT,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
);
```

### 6.4 待实现 API
```
POST   /api/v1/datasets                          创建数据集(向导式)
GET    /api/v1/datasets?domain_id=&status=        数据集列表
GET    /api/v1/datasets/{id}                      数据集详情
PUT    /api/v1/datasets/{id}                      更新配置
POST   /api/v1/datasets/{id}/preview              预览数据(前N条)
POST   /api/v1/datasets/{id}/generate             执行生成
POST   /api/v1/datasets/{id}/publish              发布版本
GET    /api/v1/datasets/{id}/versions             版本历史
GET    /api/v1/datasets/{id}/versions/{vid}/download  下载数据集文件
```

### 6.5 数据集卡片 (对齐 MES 文档)
生成后每个数据集有独立卡片:
- ID: `DS-2026-0001`
- 名称: 生产执行数据集
- 版本: v1.2
- 主题域: 生产执行
- 记录数: 1,234,567
- 字段数: 25
- 标签: [生产执行] [已验证] [日报表]
- 质量评分: 96.5
- 负责人: 张三
- 更新时间: 2026-06-09

---

## 七、质量校验模块 (待实现)

### 7.1 定位
对生成的数据集进行验收，保证数据达到可用标准。

### 7.2 校验规则 (对齐 MES 文档)
| 规则类型 | 检查内容 | 评分权重 |
|------|------|:--:|
| 完整性 | 必填字段非空率、记录完整率 | 20% |
| 准确性 | 字段类型正确率、数值范围合理率 | 20% |
| 一致性 | 关联字段引用完整率、状态逻辑一致率 | 15% |
| 唯一性 | 主键唯一率、业务键去重率 | 15% |
| 时间逻辑 | 时间先后合理性、时间范围合理性 | 15% |
| 关联完整性 | 外键引用有效、维度关联完整 | 15% |

### 7.3 验收流程
```
执行校验 → 查看问题明细(定位到记录主键+问题字段) → 查看处理建议
  → 综合评分 ≥ 阈值(默认85分) → 生成验收报告 → 通过验收 → 发布
  → 综合评分 < 阈值 → 驳回 → 返回清洗或建模环节整改
```

### 7.4 数据库表设计
```sql
CREATE TABLE validation_reports (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    dataset_id INTEGER NOT NULL,
    dataset_version_id INTEGER,
    total_rules INTEGER DEFAULT 0,
    passed_rules INTEGER DEFAULT 0,
    failed_rules INTEGER DEFAULT 0,
    pass_rate FLOAT DEFAULT 0,
    overall_score FLOAT DEFAULT 0,
    status VARCHAR(32) DEFAULT 'pending',  -- pending/passed/rejected
    report_detail JSON,
    reviewed_by INTEGER,
    reviewed_at DATETIME,
    comment TEXT,
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
);

CREATE TABLE validation_issues (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    report_id INTEGER NOT NULL,
    rule_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) DEFAULT 'warning',  -- info/warning/critical
    record_key VARCHAR(256),                 -- 问题记录主键
    field_name VARCHAR(128),                 -- 问题字段
    issue_description TEXT,
    suggestion TEXT,
    status VARCHAR(32) DEFAULT 'open',       -- open/resolved/ignored
    FOREIGN KEY (report_id) REFERENCES validation_reports(id) ON DELETE CASCADE
);
```

### 7.5 待实现 API
```
POST   /api/v1/datasets/{id}/validate          执行校验
GET    /api/v1/datasets/{id}/validations         校验历史
GET    /api/v1/validations/{rid}                 校验报告详情
GET    /api/v1/validations/{rid}/issues          问题明细
POST   /api/v1/validations/{rid}/approve         通过验收
POST   /api/v1/validations/{rid}/reject          驳回(附意见)
```

---

## 八、任务调度模块

### 8.1 已实现
- Redis 异步任务队列 (`app/core/job_queue.py`)
- Worker 后台线程 (`app/workers/sync_handler.py`)
- 任务状态轮询 (`GET /api/v1/jobs/{job_id}`)
- 同步任务异步执行 (`POST /datasources/{id}/sync?async=true`)

### 8.2 待增强 (对齐 MES 文档)
| 功能 | 说明 |
|------|------|
| 定时任务 | Cron 表达式支持, 通过 DolphinScheduler 集成 |
| 失败重试 | 自动重试策略 (最多3次, 指数退避) |
| 任务依赖 | A完成后触发B (清洗完成→自动触发建模) |
| 任务列表 | 统一的任务列表页面, 按状态/类型筛选 |
| 异常提醒 | 任务失败时通知 (钉钉/邮件) |

---

## 九、首页总览模块

### 9.1 待实现指标卡片 (对齐 MES 文档)
| 指标 | 数据来源 |
|------|------|
| 接入项目数 | `SELECT COUNT(*) FROM datasources` |
| 已标准化表数 | `SELECT COUNT(*) FROM field_mappings WHERE status='mapped'` |
| 数据质量得分 | 最近一次质量校验的 overall_score |
| 已生成数据集数 | `SELECT COUNT(*) FROM datasets WHERE status='published'` |

### 9.2 待实现流程进度
```
数据接入 ──→ 数据标准 ──→ 数据清洗 ──→ 数据建模 ──→ 数据集生成 ──→ 质量验收
   ✅          ✅          🔄          ⏳           ⏳           ⏳
```

### 9.3 待实现趋势图
- 近30天数据采集量折线图
- 近30天质量问题趋势图
- 模型覆盖率饼图
- 数据集发布数量柱状图

---

## 十、系统配置模块

### 10.1 待实现配置项 (对齐 MES 文档)
| 配置项 | 说明 | 默认值 |
|------|------|------|
| 存储路径 | Bronze/Silver/Gold 存储位置 | MinIO buckets |
| 导出格式 | 数据集默认导出格式 | Parquet |
| 评分阈值 | 质量验收通过分数线 | 85 |
| 任务并发数 | 同时执行的最大任务数 | 5 |
| 同步超时 | 数据同步超时时间(秒) | 300 |
| 数据保留天数 | 历史数据保留天数 | 180 |
| 通知渠道 | 告警通知方式 | 邮件 |

---

## 十一、数据库表总览 (已完成18张 + 待建5张)

### 已完成
`users`, `projects`, `roles`, `permissions`, `role_permissions`, `user_roles`, `project_members`, `datasources`, `crawlers`, `quality_rules`, `cleaning_pipelines`, `audit_logs`, `sync_history`, `data_domains`, `business_processes`, `data_standards`, `field_mappings`, `code_dictionaries`

### 待建
`tags`, `taggables`, `datasets`, `dataset_versions`, `validation_reports`, `validation_issues`

### 十二、前端页面总览

| 页面 | 状态 | 说明 |
|------|:--:|------|
| Dashboard | ⚠️ | 需增加指标卡片+流程进度+趋势图 |
| DataSources | ✅ | 完整CRUD+同步+预览+历史 |
| DataQuality | ✅ | 规则CRUD+执行检查 |
| Crawlers | ✅ | 爬虫CRUD+启停 |
| ProjectDetail | ✅ | 7 Tab: 概览/数据源/Pipeline/数据建模/数据标准/成员/审计 |
| Projects | ✅ | 项目列表+创建 |
| UserManagement | ✅ | 用户CRUD+角色分配+权限查看 |
| AuditLogs | ✅ | 审计日志查询 |
| DataAPI | ⚠️ | 仍为mock数据, 需对接Directus |
| Settings | ⚠️ | 空白页面, 需补系统配置 |
| DatasetGeneration | 🔜 | 待新建 |
| QualityValidation | 🔜 | 待新建 |
| TagManagement | 🔜 | 待新建 |
| TaskScheduler | 🔜 | 待新建 |
