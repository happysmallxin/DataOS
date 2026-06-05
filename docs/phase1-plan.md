# Phase 1: 底座搭建 — 详细执行计划

## 目标

搭建 DataOS 完整开发环境，所有开源组件通过 Docker Compose 统一编排，
统一平台层骨架（FastAPI + React）可运行。

## 组件清单

| # | 组件 | 版本 | 用途 | 启动优先级 |
|---|------|------|------|-----------|
| 1 | MySQL | 8.0.36 | 共享数据库 | P0 (基础设施) |
| 2 | PostgreSQL | 15.6 | Directus 数据库 | P0 |
| 3 | MongoDB | 7.0.12 | Crawlab 数据库 | P0 |
| 4 | Redis | 7.2 | 缓存 + 消息队列 | P0 |
| 5 | Elasticsearch | 8.11.4 | OpenMetadata 搜索 | P0 |
| 6 | ZooKeeper | 3.8.4 | DolphinScheduler 协调 | P0 |
| 7 | MinIO | latest | S3 对象存储 | P0 |
| 8 | DolphinScheduler | 3.2.1 | 任务编排调度 | P1 (应用服务) |
| 9 | OpenMetadata | 1.5.13 | 元数据+血缘 | P1 |
| 10 | SeaTunnel | 2.3.9 | 数据集成引擎 | P1 |
| 11 | Crawlab | latest | 爬虫管理 | P1 |
| 12 | Datavines | 1.0.0 | 数据质量 | P1 |
| 13 | Directus | 11.3.5 | 数据 API 服务 | P1 |
| 14 | Platform Backend | 0.1.0 | 统一接入层 | P2 (平台层) |
| 15 | Platform Frontend | 0.1.0 | 统一 UI | P2 |

## 已创建文件

```
DataOS/
├── .env                              # 全局环境变量
├── .gitignore
├── docker-compose.yml                # 基础设施层 (MySQL/Redis/Mongo/ES/ZK/MinIO)
├── docker-compose.apps.yml           # 应用服务层 (DS/OM/SeaTunnel/Crawlab/Datavines/Directus)
├── docker-compose.platform.yml       # 平台层 (FastAPI + React)
├── Makefile                          # 便捷命令
├── README.md
├── scripts/start.sh                  # 一键启动脚本
├── docs/phase1-plan.md               # 本文档
├── components/
│   ├── mysql/init/01-create-databases.sql   # 自动建库
│   ├── dolphinscheduler/resources/
│   ├── openmetadata/conf/
│   ├── seatunnel/config/seatunnel.yaml      # SeaTunnel 引擎配置
│   ├── seatunnel/jobs/                      # 同步作业目录
│   ├── crawlab/
│   ├── datavines/
│   └── directus/{extensions,snapshots}/
├── platform/
│   ├── backend/                      # FastAPI 后端
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py               # 入口 + 路由注册
│   │       ├── core/                 # 配置/安全/数据库
│   │       ├── models/               # User/Project/DataSource
│   │       ├── api/                  # auth/health/projects/datasources
│   │       └── services/             # 下游组件代理
│   └── frontend/                     # React 前端
│       ├── Dockerfile                # 多阶段构建
│       ├── nginx.conf                # 生产 Nginx 配置
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.js
│       └── src/
│           ├── main.tsx
│           ├── App.tsx               # 路由
│           ├── layouts/MainLayout.tsx # 侧边栏+顶部导航
│           └── pages/                # Dashboard/DataSources/Crawlers/Quality/API/Settings
└── docs/
    └── architecture.md               # (待补充)
```

## 启动步骤

### 方式一: Makefile

```bash
# 查看帮助
make help

# 分步启动
make infra       # 基础设施
make apps        # 应用服务
make platform    # 平台层

# 一键全部
make all
```

### 方式二: 脚本

```bash
bash scripts/start.sh          # 全部启动
bash scripts/start.sh infra    # 仅基础设施
bash scripts/start.sh apps     # 仅应用服务
bash scripts/start.sh platform # 仅平台层
```

### 方式三: 手动

```bash
# 基础设施
docker compose up -d

# 应用服务
docker compose -f docker-compose.apps.yml up -d

# 平台层 (Docker)
docker compose -f docker-compose.platform.yml up -d

# 或本地开发
cd platform/backend && uvicorn app.main:app --reload --port 8000
cd platform/frontend && npm install && npm run dev
```

## 下一步 (Phase 2)

- [ ] SeaTunnel: 配置首批 10 个数据源连接器 (MySQL/PostgreSQL/MongoDB/Kafka/API/CSV 等)
- [ ] Crawlab: 编写首批网页爬虫模板 (Scrapy + Crawlee)
- [ ] Datavines: 配置基础数据质量规则 (非空/范围/格式/去重)
- [ ] Directus: 创建首批数据 API (设备列表/告警记录/行业数据)
- [ ] OpenMetadata: 接入首批数据源的元数据采集
- [ ] 平台层: 数据地图页面 (全局检索 + 血缘可视化)
- [ ] 平台层: 对接 RelOS ingestion/
- [ ] 平台层: 用户认证 (JWT 中间件完善)
