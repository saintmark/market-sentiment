#!/bin/bash
# ============================================================
# 市场情绪分析系统 - 简化版启动脚本
# 只使用 PostgreSQL + Redis，去掉 Kafka/ClickHouse
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 帮助信息
show_help() {
    cat << EOF
市场情绪分析系统 - 简化版启动脚本

用法: $0 [选项]

选项:
    -h, --help          显示帮助信息
    -d, --detach        后台运行 (默认)
    -f, --foreground    前台运行，显示实时日志
    -b, --build         强制重新构建镜像
    --clean             清理并重新启动（删除所有数据）
    --stop              停止所有服务
    --logs              查看日志

示例:
    $0                           # 启动所有服务（后台）
    $0 -f                        # 前台运行
    $0 -b                        # 重新构建并启动
    $0 --clean                   # 清理数据并重新启动

EOF
}

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose 未安装，请先安装 docker-compose"
        exit 1
    fi
    
    # 检查 Docker 是否运行
    if ! docker info &> /dev/null; then
        log_error "Docker 未运行，请启动 Docker 服务"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 检查环境变量
check_env() {
    if [ ! -f ".env" ]; then
        log_warn ".env 文件不存在，使用默认配置"
    fi
    
    # 检查 Kimi API Key
    if grep -q "your-moonshot-api-key-here" .env 2>/dev/null || ! grep -q "KIMI_API_KEY=" .env 2>/dev/null; then
        log_error "请先在 .env 文件中配置 KIMI_API_KEY"
        log_info "示例: KIMI_API_KEY=sk-xxxxxxxxxxxxxxxx"
        exit 1
    fi
    
    log_success "环境变量检查通过"
}

# 创建必要目录
create_directories() {
    log_info "创建必要的目录..."
    mkdir -p logs/postgres logs/redis data
    log_success "目录创建完成"
}

# 启动服务
start_services() {
    local detach_flag="-d"
    local build_flag=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--detach)
                detach_flag="-d"
                shift
                ;;
            -f|--foreground)
                detach_flag=""
                shift
                ;;
            -b|--build)
                build_flag="--build"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    log_info "启动服务..."
    
    if [ -n "$build_flag" ]; then
        docker-compose -f docker-compose-simple.yml up --build $detach_flag
    else
        docker-compose -f docker-compose-simple.yml up $detach_flag
    fi
    
    if [ $? -eq 0 ]; then
        log_success "服务启动成功！"
        show_status
    else
        log_error "服务启动失败"
        exit 1
    fi
}

# 停止服务
stop_services() {
    log_info "停止服务..."
    docker-compose -f docker-compose-simple.yml down
    log_success "服务已停止"
}

# 清理数据
cleanup() {
    log_warn "即将清理所有数据（包括数据库）..."
    read -p "确认继续? (y/N): " confirm
    if [[ $confirm == [yY] || $confirm == [yY][eE][sS] ]]; then
        docker-compose -f docker-compose-simple.yml down -v
        rm -rf logs/* data/*
        log_success "数据已清理"
    else
        log_info "操作已取消"
    fi
}

# 查看日志
show_logs() {
    docker-compose -f docker-compose-simple.yml logs -f
}

# 显示状态
show_status() {
    echo ""
    echo "============================================================"
    echo "  市场情绪分析系统 - 简化版"
    echo "============================================================"
    echo ""
    echo "  服务状态:"
    docker-compose -f docker-compose-simple.yml ps
    echo ""
    echo "  访问地址:"
    echo "    - Web 仪表盘:    http://localhost:3000"
    echo "    - API 文档:      http://localhost:8000/docs"
    echo "    - 健康检查:      http://localhost:8000/health"
    echo ""
    echo "  常用命令:"
    echo "    - 查看日志:      ./start.sh --logs"
    echo "    - 停止服务:      ./start.sh --stop"
    echo "    - 重启服务:      ./start.sh -f"
    echo ""
    echo "============================================================"
}

# 主函数
main() {
    # 如果没有参数，默认后台启动
    if [ $# -eq 0 ]; then
        check_dependencies
        check_env
        create_directories
        start_services -d
        exit 0
    fi
    
    # 解析参数
    case $1 in
        -h|--help)
            show_help
            ;;
        -d|--detach)
            check_dependencies
            check_env
            create_directories
            start_services -d
            ;;
        -f|--foreground)
            check_dependencies
            check_env
            create_directories
            start_services -f
            ;;
        -b|--build)
            check_dependencies
            check_env
            create_directories
            start_services -d -b
            ;;
        --clean)
            cleanup
            ;;
        --stop)
            stop_services
            ;;
        --logs)
            show_logs
            ;;
        --status)
            show_status
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"