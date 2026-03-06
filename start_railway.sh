#!/bin/bash
# Railway 启动脚本 - 同时运行 Dashboard 和后台采集/分析任务

set -e

echo "🚀 启动市场情感系统..."
echo "当前时间: $(date)"
echo "工作目录: $(pwd)"
echo ""

# 确保数据目录存在
mkdir -p /app/data

# 检查环境变量
if [ -z "$KIMI_API_KEY" ]; then
    echo "⚠️ 警告: KIMI_API_KEY 未设置"
else
    echo "✅ KIMI_API_KEY 已配置"
fi

# 后台运行采集和情感分析（每5分钟一次）
(
    echo "[$(date)] 后台采集任务启动"
    while true; do
        echo "[$(date)] ========== 开始新一轮采集 =========="
        
        # 采集新闻
        echo "[$(date)] 开始采集新闻..."
        cd /app && python3 -c "
import sys
sys.path.insert(0, '.')
from market_sentiment import Database, Collector

try:
    db = Database()
    collector = Collector(db)
    collector.run()
    print('[OK] 采集完成')
except Exception as e:
    print(f'[ERROR] 采集失败: {e}')
" 2>&1
        
        # 情感分析
        echo "[$(date)] 开始情感分析..."
        cd /app && python3 -c "
import sys, os
sys.path.insert(0, '.')
from market_sentiment import Database, SentimentAnalyzer
from dotenv import load_dotenv
load_dotenv()

try:
    db = Database()
    analyzer = SentimentAnalyzer(db, os.getenv('KIMI_API_KEY', ''))
    news_list = db.get_unanalyzed_news(limit=5)
    count = 0
    for item in news_list:
        try:
            text = f'{item[\"title\"]} {item.get(\"content\", \"\")}'
            result = analyzer.analyze(text[:800])
            db.update_sentiment(item['id'], result['score'], result['label'], result['keywords'], result.get('sector', '综合'))
            count += 1
        except Exception as e:
            print(f'[ERROR] 分析ID={item[\"id\"]}失败: {e}')
    print(f'[OK] 分析完成: {count}条')
except Exception as e:
    print(f'[ERROR] 分析任务失败: {e}')
" 2>&1
        
        echo "[$(date)] ========== 本轮完成，等待5分钟 =========="
        sleep 300
    done
) >> /app/data/collector.log 2>&1 &
echo "✅ 后台采集任务已启动 (PID: $!)"

# 等待几秒确保后台任务启动
sleep 2

# 检查后台任务是否运行
if ps aux | grep -v grep | grep -q "python3.*market_sentiment"; then
    echo "✅ 后台任务运行正常"
else
    echo "⚠️ 后台任务可能未启动，查看日志:"
    tail -5 /app/data/collector.log 2>/dev/null || echo "无日志"
fi

echo ""
echo "🌐 启动 Dashboard..."
echo ""

# 前台运行 Dashboard（Railway 需要前台进程保持运行）
exec python3 web_dashboard.py
