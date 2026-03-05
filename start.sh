#!/bin/bash
# ============================================================
# 市场情绪分析系统 - 启动脚本
# Market Sentiment Analysis System - Start Script
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 帮助信息
show_help() {
    cat << EOF
市场情绪分析系统启动脚本

用法: $0 [选项] [服务...]

选项:
    -h, --help          显示帮助信息
    -d, --detach        后台运行 (默认)
    -f, --foreground    前台运行，显示实时日志
    -b, --build         强制重新构建镜像
    --no-build          跳过构建步骤
    --clean             清理并重新启动（删除所有数据）
    --dev               启动开发模式（包含 Kafka UI）
    --debug             启动调试模式（包含额外工具）
    --init-only         仅初始化配置，不启动服务

服务:                可选，指定要启动的特定服务
                     如果不指定，则启动所有服务

示例:
    $0                           # 启动所有服务（后台）
    $0 -f                        # 前台运行
    $0 -b                        # 重新构建并启动
    $0 --clean                   # 清理数据并重新启动
    $0 --dev                     # 开发模式启动
    $0 postgres redis            # 仅启动数据库服务

EOF
}

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 Docker Compose"
        exit 1
    fi
    
    # 检查 Docker 守护进程
    if ! docker info &> /dev/null; then
        log_error "Docker 守护进程未运行，请启动 Docker"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 检查 .env 文件
check_env_file() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            log_warn ".env 文件不存在，从 .env.example 复制..."
            cp .env.example .env
            log_warn "请编辑 .env 文件配置您的环境变量，特别是 API 密钥"
        else
            log_error ".env 和 .env.example 文件都不存在"
            exit 1
        fi
    fi
    
    # 检查关键配置
    if grep -q "your-moonshot-api-key-here" .env; then
        log_warn "⚠️  检测到默认的 KIMI_API_KEY，请在 .env 文件中配置正确的 API 密钥"
    fi
    
    if grep -q "change-me-in-production" .env; then
        log_warn "⚠️  检测到默认的安全密钥，请在 .env 文件中配置强密码"
    fi
}

# 创建必要的目录
setup_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p logs/postgres
    mkdir -p logs/clickhouse
    mkdir -p config
    mkdir -p data/backup
    
    # 创建 Redis 配置文件（如果不存在）
    if [ ! -f "config/redis.conf" ]; then
        cat > config/redis.conf << 'EOF'
# Redis 配置
maxmemory 256mb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
EOF
        log_info "创建默认 Redis 配置文件"
    fi
    
    # 创建 ClickHouse 配置文件（如果不存在）
    if [ ! -f "config/clickhouse.xml" ]; then
        cat > config/clickhouse.xml << 'EOF'
<?xml version="1.0"?>
<clickhouse>
    <logger>
        <level>information</level>
        <console>true</console>
    </logger>
    <http_port>8123</http_port>
    <tcp_port>9000</tcp_port>
</clickhouse>
EOF
        log_info "创建默认 ClickHouse 配置文件"
    fi
    
    log_success "目录创建完成"
}

# 清理数据
clean_data() {
    log_warn "⚠️  即将删除所有数据卷和容器！"
    read -p "确定要继续吗？(yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "操作已取消"
        exit 0
    fi
    
    log_info "停止所有服务..."
    docker-compose down --volumes --remove-orphans 2>/dev/null || true
    
    log_info "删除数据卷..."
    docker volume rm market-sentiment_postgres_data 2>/dev/null || true
    docker volume rm market-sentiment_redis_data 2>/dev/null || true
    docker volume rm market-sentiment_clickhouse_data 2>/dev/null || true
    docker volume rm market-sentiment_kafka_data 2>/dev/null || true
    docker volume rm market-sentiment_zookeeper_data 2>/dev/null || true
    
    log_info "清理完成"
}

# 等待服务就绪
wait_for_services() {
    log_info "等待核心服务就绪..."
    
    local services=("postgres" "redis" "kafka" "clickhouse")
    local max_wait=120
    local waited=0
    
    for service in "${services[@]}"; do
        log_info "等待 $service 就绪..."
        while ! docker-compose ps "$service" | grep -q "healthy" 2>/dev/null; do
            sleep 2
            waited=$((waited + 2))
            if [ $waited -ge $max_wait ]; then
                log_error "$service 启动超时，请检查日志"
                return 1
            fi
            echo -n "."
        done
        echo ""
    done
    
    log_success "所有核心服务已就绪"
}

# 显示服务状态
show_status() {
    echo ""
    log_info "服务状态:"
    docker-compose ps
    
    echo ""
    log_info "访问地址:"
    echo "  📊 Web 前端:    http://localhost:3000"
    echo "  🔌 API 接口:    http://localhost:8000"
    echo "  📈 API 文档:    http://localhost:8000/docs"
    echo "  🔍 Kafka UI:    http://localhost:8080"
    echo "  🗄️  PostgreSQL: localhost:5432"
    echo "  💾 Redis:       localhost:6379"
    echo "  📊 ClickHouse:  http://localhost:8123"
    
    echo ""
    log_info "常用命令:"
    echo "  查看日志:   ./logs.sh"
    echo "  停止服务:   ./stop.sh"
    echo "  重启服务:   ./start.sh -b"
}

# 主函数
main() {
    local detach=true
    local build=false
    local clean=false
    local dev_mode=false
    local debug_mode=false
    local init_only=false
    local compose_profiles=""
    local services=()
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--detach)
                detach=true
                shift
                ;;
            -f|--foreground)
                detach=false
                shift
                ;;
            -b|--build)
                build=true
                shift
                ;;
            --no-build)
                build=false
                shift
                ;;
            --clean)
                clean=true
                shift
                ;;
            --dev)
                dev_mode=true
                compose_profiles="--profile dev"
                shift
                ;;
            --debug)
                debug_mode=true
                compose_profiles="--profile debug"
                shift
                ;;
            --init-only)
                init_only=true
                shift
                ;;
            -*)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
            *)
                services+=("$1")
                shift
                ;;
        esac
    done
    
    # 检查依赖
    check_dependencies
    
    # 检查 .env 文件
    check_env_file
    
    # 创建目录
    setup_directories
    
    # 仅初始化
    if [ "$init_only" = true ]; then
        log_info "初始化完成，服务未启动"
        exit 0
    fi
    
    # 清理数据
    if [ "$clean" = true ]; then
        clean_data
    fi
    
    # 构建参数
    local compose_cmd="docker-compose"
    if docker compose version &> /dev/null; then
        compose_cmd="docker compose"
    fi
    
    # 构建镜像
    if [ "$build" = true ]; then
        log_info "构建 Docker 镜像..."
        $compose_cmd build --no-cache ${services[@]}
    fi
    
    # 启动服务
    log_info "启动服务..."
    
    local up_args=""
    if [ "$detach" = true ]; then
        up_args="-d"
    fi
    
    if [ ${#services[@]} -eq 0 ]; then
        # 启动所有服务
        if [ -n "$compose_profiles" ]; then
            $compose_cmd $compose_profiles up $up_args --build
        else
            $compose_cmd up $up_args --build
        fi
    else
        # 启动指定服务
        $compose_cmd up $up_args --build ${services[@]}
    fi
    
    # 等待服务就绪
    if [ "$detach" = true ]; then
        if wait_for_services; then
            show_status
        else
            log_error "部分服务启动失败，请检查日志: ./logs.sh"
            exit 1
        fi
    fi
    
    log_success "启动脚本执行完成"
}

# 执行主函数
main "$@"
