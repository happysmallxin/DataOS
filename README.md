# DataOS — 企业级数据治理平台

> 对标 Alibaba DataWorks + ByteDance DataLeap
> RelOS 的上游：数据采集 → 清洗 → 标准化 → API 服务化

## 架构

```
┌─────────────────────────────────────────┐
│         统一平台层 (自研 FastAPI+React)    │
├─────────────────────────────────────────┤
│  Directus  │ OpenMetadata │ Datavines   │
│  (API服务)  │  (元数据/血缘) │  (数据质量)   │
├─────────────────────────────────────────┤
│  SeaTunnel │   Crawlab    │ DolphinScheduler │
│  (数据集成)  │   (网页爬取)  │   (任务调度)     │
├─────────────────────────────────────────┤
│   MySQL / PostgreSQL / MongoDB / Redis  │
│   Elasticsearch / ZooKeeper / MinIO     │
└─────────────────────────────────────────┘
              ↓
          RelOS (关系操作系统)
```

## 快速开始

```bash
# 查看所有命令
make help

# 仅启动基础设施 (MySQL/Redis/Mongo/ES/ZK/MinIO)
make infra

# 启动基础设施 + 应用服务 (DS/OM/SeaTunnel/Crawlab/Datavines/Directus)
make apps

# 启动基础设施 + 平台层 (FastAPI + React)
make platform

# 一键全部启动
make all
```

Docker Compose 直接命令：

```bash
docker compose up -d                                    # 仅基础设施
docker compose --profile apps up -d                      # + 应用服务
docker compose --profile apps --profile platform up -d   # 全部
```

## 服务地址

| 组件 | 地址 | 说明 |
|------|------|------|
| DataOS Platform | http://localhost:5000 | 统一平台前端 |
| Platform API | http://localhost:8000/docs | FastAPI Swagger |
| DolphinScheduler | http://localhost:12345/dolphinscheduler | 任务调度 |
| OpenMetadata | http://localhost:8585 | 元数据管理 |
| Crawlab | http://localhost:8088 | 爬虫管理 |
| Datavines | http://localhost:5600 | 数据质量 |
| Directus | http://localhost:8055/admin | 数据 API |
| MinIO Console | http://localhost:9001 | 对象存储 |

## 本地开发

```bash
# 后端
make dev-backend   # cd platform/backend && uvicorn app.main:app --reload --port 8000

# 前端
make dev-frontend  # cd platform/frontend && npm install && npm run dev
```

## 项目结构

```
DataOS/
├── docker-compose.yml         # 完整编排 (Docker Compose profiles)
├── Makefile                   # 便捷命令
├── scripts/start.sh           # 一键启动脚本
├── .env                       # 环境变量
├── components/                # 各组件配置
│   ├── mysql/init/            # MySQL 初始化 (自动建库)
│   ├── seatunnel/config/      # SeaTunnel 引擎配置
│   ├── seatunnel/jobs/        # 同步作业
│   └── ...
├── platform/                  # 统一平台层 (自研)
│   ├── backend/               # FastAPI (Python 3.11+)
│   │   └── app/
│   │       ├── main.py        # 入口 + 路由注册
│   │       ├── core/          # config / security / database
│   │       ├── models/        # User / Project / DataSource
│   │       ├── api/           # auth / health / projects / datasources
│   │       └── services/      # 下游组件代理 (ComponentClient)
│   └── frontend/              # React 18 + Vite + Tailwind CSS + Ant Design
│       └── src/
│           ├── App.tsx        # 路由配置
│           ├── layouts/       # MainLayout (侧边栏+顶栏)
│           └── pages/         # Dashboard / DataSources / Crawlers / Quality / API / Settings
├── docs/                      # 文档
└── scripts/                   # 脚本
```

## 技术栈

| 层 | 技术 |
|----|------|
| 平台后端 | Python 3.11+ / FastAPI / SQLAlchemy async / Redis |
| 平台前端 | React 18 / TypeScript / Vite / Tailwind CSS / Ant Design |
| 任务调度 | Apache DolphinScheduler 3.2.1 |
| 元数据+血缘 | OpenMetadata 1.5.13 |
| 数据集成 | Apache SeaTunnel 2.3.9 |
| 网页爬取 | Crawlab (Golang + Vue3) |
| 数据质量 | Datavines 1.0.0 + Great Expectations |
| API 服务 | Directus 11 (REST + GraphQL) |
| 数据存储 | MySQL 8 / PostgreSQL 15 / MongoDB 7 / MinIO |
| 缓存消息 | Redis 7 / Elasticsearch 8 / ZooKeeper 3.8 |

## 分阶段路线

- **Phase 1** (✅ 当前): 底座搭建 — Docker Compose 集成所有组件 + 平台骨架
- **Phase 2**: 治理能力 — 数据地图、质量中心、安全中心、RelOS 对接
- **Phase 3**: 智能化 — 指标平台、数据建模、AI 辅助

## License

MIT
