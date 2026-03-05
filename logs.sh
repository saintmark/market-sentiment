#!/bin/bash
# ============================================================
# 市场情绪分析系统 - 日志查看脚本
# Market Sentiment Analysis System - Logs Script
# ============================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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
市场情绪分析系统日志查看脚本

用法: $0 [选项] [服务...]

选项:
    -h, --help          显示帮助信息
    -f, --follow        实时跟踪日志（类似 tail -f）
    -n, --lines         显示最近 N 行（默认 100）
    -s, --since         显示自某个时间以来的日志（如 10m, 1h）
    -t, --timestamps    显示时间戳
    -c, --colors        彩色输出（默认开启）
    --no-colors         禁用彩色输出
    --services          列出所有可用服务
    -a, --all           显示所有服务的日志（包括已停止的）

服务:                可选，指定要查看的特定服务
                     支持通配符，如 'ms-*'

示例:
    $0                           # 显示所有服务的最近 100 行日志
    $0 -f                        # 实时跟踪所有服务日志
    $0 -n 50                     # 显示最近 50 行
    $0 -f postgres               # 实时跟踪 PostgreSQL 日志
    $0 -n 200 api nlp            # 显示 API 和 NLP 服务的最近 200 行
    $0 -s 30m                    # 显示最近 30 分钟的日志
    $0 --services                # 列出所有服务

EOF
}

# 列出所有服务
list_services() {
    log_info "可用服务列表:"
    echo ""
    
    local services=(
        "ms-postgres:PostgreSQL 数据库"
        "ms-redis:Redis 缓存"
        "ms-kafka:Kafka 消息队列"
        "ms-clickhouse:ClickHouse 时序数据库"
        "ms-collector:数据采集服务"
        "ms-nlp:NLP 情感分析服务"
        "ms-aggregator:数据聚合服务"
        "ms-scheduler:定时任务服务"
        "ms-api:API 网关服务"
        "ms-web:Web 前端服务"
        "ms-kafka-ui:Kafka 管理界面"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r name desc <<< "$service_info"
        local status=$(docker ps --filter "name=$name" --format "{{.Status}}" 2>/dev/null || echo "")
        if [ -n "$status" ]; then
            echo -e "  ${GREEN}●${NC} $name"
            echo "     状态: $status"
            echo "     描述: $desc"
        else
            echo -e "  ${RED}○${NC} $name (未运行)"
            echo "     描述: $desc"
        fi
    done
}

# 主函数
main() {
    local follow=false
    local lines=100
    local since=""
    local timestamps=false
    local colors=true
    local all=false
    local services=()
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -f|--follow)
                follow=true
                shift
                ;;
            -n|--lines)
                lines="$2"
                shift 2
                ;;
            -s|--since)
                since="$2"
                shift 2
                ;;
            -t|--timestamps)
                timestamps=true
                shift
                ;;
            -c|--colors)
                colors=true
                shift
                ;;
            --no-colors)
                colors=false
                shift
                ;;
            --services)
                list_services
                exit 0
                ;;
            -a|--all)
                all=true
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
    
    # 禁用颜色
    if [ "$colors" = false ]; then
        RED=''
        GREEN=''
        YELLOW=''
        BLUE=''
        CYAN=''
        NC=''
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
    
    # 构建日志参数
    local log_args=""
    
    if [ "$follow" = true ]; then
        log_args="$log_args --follow"
    fi
    
    if [ -n "$lines" ]; then
        log_args="$log_args --tail=$lines"
    fi
    
    if [ -n "$since" ]; then
        log_args="$log_args --since=$since"
    fi
    
    if [ "$timestamps" = true ]; then
        log_args="$log_args --timestamps"
    fi
    
    # 显示日志
    if [ ${#services[@]} -eq 0 ]; then
        # 显示所有服务的日志
        log_info "查看所有服务日志..."
        $compose_cmd logs $log_args
    else
        # 显示指定服务的日志
        log_info "查看服务日志: ${services[*]}"
        $compose_cmd logs $log_args ${services[@]}
    fi
}

# 执行主函数
main "$@"
