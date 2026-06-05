# ============================================================
# DataOS — 便捷命令
# ============================================================

.PHONY: help infra apps platform all stop clean status logs

help:
	@echo "DataOS — 数据治理平台"
	@echo ""
	@echo "  make infra       启动基础设施 (MySQL/Redis/Mongo/ES/ZK/MinIO)"
	@echo "  make apps        启动基础设施 + 应用服务 (DS/OM/SeaTunnel/Crawlab/Datavines/Directus)"
	@echo "  make platform    启动基础设施 + 平台层 (FastAPI 后端 + React 前端)"
	@echo "  make all         启动全部服务"
	@echo ""
	@echo "  make status      查看所有服务状态"
	@echo "  make logs        查看所有服务日志"
	@echo "  make stop        停止全部服务"
	@echo "  make clean       停止并清理数据卷 (危险!)"
	@echo ""
	@echo "  服务地址:"
	@echo "    DolphinScheduler:  http://localhost:12345/dolphinscheduler"
	@echo "    OpenMetadata:       http://localhost:8585"
	@echo "    Crawlab:            http://localhost:8088"
	@echo "    Datavines:          http://localhost:5600"
	@echo "    Directus:           http://localhost:8055/admin"
	@echo "    MinIO Console:      http://localhost:9001"
	@echo "    DataOS Platform:    http://localhost:5000"
	@echo "    Platform API Docs:  http://localhost:8000/docs"

# ---- 启动命令 ----

infra:
	@echo "🚀 启动基础设施层..."
	docker compose up -d
	@echo "⏳ 等待 MySQL 就绪..."
	@until docker exec dataos-mysql mysqladmin ping -h localhost -u root -pdataos_root_2025 --silent 2>/dev/null; do sleep 2; done
	@echo "✅ 基础设施就绪"

apps:
	@echo "🚀 启动基础设施 + 应用服务..."
	docker compose --profile apps up -d
	@echo "⏳ 等待服务就绪 (约 3-5 分钟)..."
	@sleep 10
	@echo "✅ 应用服务已启动"

platform:
	@echo "🚀 启动基础设施 + 平台层..."
	docker compose --profile platform up -d
	@sleep 5
	@echo "✅ 平台层已启动"
	@echo "  前端: http://localhost:5000"
	@echo "  API:  http://localhost:8000/docs"

all:
	@echo "🚀 启动全部 DataOS 服务..."
	docker compose --profile apps --profile platform up -d
	@echo ""
	@echo "✅ DataOS 全部服务已启动!"
	@echo ""
	@$(MAKE) status

# ---- 状态 & 日志 ----

status:
	@echo "📊 服务状态:"
	@echo ""
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

logs:
	docker compose logs -f --tail=50

# ---- 停止 & 清理 ----

stop:
	@echo "🛑 停止全部 DataOS 服务..."
	docker compose --profile apps --profile platform down 2>/dev/null || true
	docker compose down
	@echo "✅ 全部服务已停止"

clean:
	@echo "⚠️  将删除所有数据卷! (5 秒后执行, Ctrl+C 取消)"
	@sleep 5
	docker compose --profile apps --profile platform down -v 2>/dev/null || true
	docker compose down -v
	@echo "✅ 已清理全部服务和数据卷"

# ---- 开发 ----

dev-backend:
	cd platform/backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd platform/frontend && npm install && npm run dev
