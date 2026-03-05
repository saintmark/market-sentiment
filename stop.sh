#!/bin/bash
# ============================================================
# 市场情绪分析系统 - 停止脚本
# Market Sentiment Analysis System - Stop Script
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

# 帮助信息
show_help() {
    cat << EOF
市场情绪分析系统停止脚本

用法: $0 [选项] [服务...]

选项:
    -h, --help          显示帮助信息
    -t, --timeout       停止超时时间（秒，默认 30）
    -v, --volumes       同时删除数据卷
    -r, --remove        同时删除容器
    -a, --all           删除所有（容器+数据卷+镜像）
    -f, --force         强制停止，不提示

服务:                可选，指定要停止的特定服务
                     如果不指定，则停止所有服务

示例:
    $0                           # 停止所有服务
    $0 -t 60                     # 60秒超时
    $0 -v                        # 停止并删除数据卷
    $0 -a                        # 完全清理所有内容
    $0 postgres                  # 仅停止 PostgreSQL

EOF
}

# 主函数
main() {
    local timeout=30
    local remove_volumes=false
    local remove_containers=false
    local remove_all=false
    local force=false
    local services=()
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -t|--timeout)
                timeout="$2"
                shift 2
                ;;
            -v|--volumes)
                remove_volumes=true
                shift
                ;;
            -r|--remove)
                remove_containers=true
                shift
                ;;
            -a|--all)
                remove_all=true
                shift
                ;;
            -f|--force)
                force=true
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
    
    # 确认危险操作
    if [ "$remove_all" = true ] && [ "$force" = false ]; then
        log_warn "⚠️  这将删除所有容器、数据卷和镜像！"
        read -p "确定要继续吗？(yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            log_info "操作已取消"
            exit 0
        fi
    fi
    
    # 检查是否在项目目录
    if [ ! -f "docker-compose.yml" ]; then
        log_error "未找到 docker-compose.yml，请确保在正确的目录运行"
        exit 1
    fi
    
    # 确定 compose 命令
    local compose_cmd="docker-compose"
    if docker compose version &> /dev/null; then
        compose_cmd="docker compose"
    fi
    
    # 构建停止参数
    local stop_args="-t $timeout"
    
    log_info "正在停止服务..."
    
    if [ ${#services[@]} -eq 0 ]; then
        # 停止所有服务
        if [ "$remove_all" = true ]; then
            log_warn "正在删除所有容器、数据卷和镜像..."
            $compose_cmd down -v --rmi all --remove-orphans
        elif [ "$remove_volumes" = true ]; then
            log_warn "正在停止并删除数据卷..."
            $compose_cmd down -v --remove-orphans
        elif [ "$remove_containers" = true ]; then
            log_warn "正在停止并删除容器..."
            $compose_cmd down --remove-orphans
        else
            $compose_cmd stop $stop_args
        fi
    else
        # 停止指定服务
        if [ "$remove_containers" = true ] || [ "$remove_volumes" = true ]; then
            log_warn "正在删除指定服务的容器..."
            $compose_cmd rm -fs ${services[@]}
        else
            $compose_cmd stop $stop_args ${services[@]}
        fi
    fi
    
    log_success "服务已停止"
    
    # 显示状态
    echo ""
    log_info "当前容器状态:"
    docker-compose ps 2>/dev/null || echo "无运行中的容器"
}

# 执行主函数
main "$@"
