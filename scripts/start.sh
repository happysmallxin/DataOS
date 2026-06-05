#!/usr/bin/env bash
# ============================================================
# DataOS 一键启动脚本
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }
step() { echo -e "\n${BLUE}═══ $1 ═══${NC}"; }

# 检查 Docker 环境
check_deps() {
    step "检查环境依赖"
    if ! command -v docker &> /dev/null; then
        err "未安装 Docker，请先安装 Docker Desktop: https://docker.com"
        exit 1
    fi
    if ! docker compose version &> /dev/null; then
        err "Docker Compose 不可用，请升级 Docker Desktop"
        exit 1
    fi
    log "Docker 环境就绪 ✓"
}

# 检查资源
check_resources() {
    step "检查系统资源"
    local mem_free
    mem_free=$(vm_stat 2>/dev/null | awk '/free/ {print $3}' | sed 's/\.//' || echo "0")
    if command -v sysctl &> /dev/null && [[ $(sysctl -n hw.memsize 2>/dev/null) -lt 8589934592 ]]; then
        warn "内存小于 8GB，建议至少 16GB 运行全部服务"
    fi
    # 检查端口占用
    local ports=(3306 5432 6379 9200 2181 9000 12345 8585 8088 5600 8055 3000 8000)
    local occupied=()
    for port in "${ports[@]}"; do
        if lsof -i :"$port" -sTCP:LISTEN &>/dev/null; then
            occupied+=("$port")
        fi
    done
    if [[ ${#occupied[@]} -gt 0 ]]; then
        warn "以下端口已被占用: ${occupied[*]}"
        warn "请先释放端口或修改 .env 中的端口配置"
    fi
}

# 启动基础设施
start_infra() {
    step "1/3 启动基础设施层"
    docker compose up -d
    log "等待 MySQL 就绪..."
    local retries=0
    while [[ $retries -lt 30 ]]; do
        if docker exec dataos-mysql mysqladmin ping -h localhost -u root -pdataos_root_2025 --silent 2>/dev/null; then
            log "MySQL 就绪 ✓"
            break
        fi
        sleep 2
        ((retries++))
    done
    if [[ $retries -ge 30 ]]; then
        err "MySQL 启动超时"
        exit 1
    fi
    log "基础设施层启动完成"
}

# 启动应用服务
start_apps() {
    step "2/3 启动应用服务层"
    docker compose --profile apps up -d
    log "等待服务就绪 (约 3-5 分钟)..."
    sleep 15
    log "应用服务层启动完成"
}

# 启动平台层
start_platform() {
    step "3/3 启动平台层"
    docker compose --profile platform up -d 2>/dev/null || {
        warn "Docker 启动失败，请使用本地开发模式: make dev-backend / make dev-frontend"
        return
    }
    log "平台层启动完成"
}

# 打印信息
print_info() {
    step "DataOS 启动完成!"
    echo ""
    echo "  服务地址:"
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │ DataOS Platform  │ http://localhost:3000            │"
    echo "  │ Platform API     │ http://localhost:8000/docs       │"
    echo "  │ DolphinScheduler │ http://localhost:12345/dolphinscheduler │"
    echo "  │ OpenMetadata     │ http://localhost:8585            │"
    echo "  │ Crawlab          │ http://localhost:8088            │"
    echo "  │ Datavines        │ http://localhost:5600            │"
    echo "  │ Directus         │ http://localhost:8055/admin      │"
    echo "  │ MinIO Console    │ http://localhost:9001            │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""
    echo "  查看状态: docker compose ps"
    echo "  查看日志: docker compose logs -f"
    echo "  停止服务: make stop"
}

main() {
    echo ""
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║         DataOS — 数据治理平台              ║"
    echo "  ║         Phase 1: 底座搭建                  ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo ""

    check_deps
    check_resources

    local mode="${1:-full}"
    case "$mode" in
        infra)
            start_infra
            ;;
        apps)
            start_apps
            ;;
        platform)
            start_platform
            ;;
        full|*)
            start_infra
            start_apps
            start_platform
            print_info
            ;;
    esac
}

main "$@"
