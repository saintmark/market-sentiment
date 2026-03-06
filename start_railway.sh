#!/bin/bash
# Railway 启动脚本 - 同时运行 Dashboard 和后台采集/分析任务

echo "🚀 启动市场情感系统..."
echo ""

# 后台运行采集和情感分析（每5分钟一次）
(
    while true; do
        echo "[$(date)] 开始采集新闻..."
        cd /app && python3 -c "
import sys
sys.path.insert(0, '.')
from market_sentiment import Database, Collector

db = Database()
collector = Collector(db)
collector.run()
" 2>&1 | tail -5
        
        echo "[$(date)] 开始情感分析..."
        cd /app && python3 -c "
import sys, os
sys.path.insert(0, '.')
from market_sentiment import Database, SentimentAnalyzer
from dotenv import load_dotenv
load_dotenv()

db = Database()
analyzer = SentimentAnalyzer(db, os.getenv('KIMI_API_KEY', ''))
news_list = db.get_unanalyzed_news(limit=5)
for item in news_list:
    text = f'{item[\"title\"]} {item.get(\"content\", \"\")}'
    result = analyzer.analyze(text[:800])
    db.update_sentiment(item['id'], result['score'], result['label'], result['keywords'], result.get('sector', '综合'))
print(f'分析完成: {len(news_list)}条')
" 2>&1 | tail -3
        
        echo "[$(date)] 等待5分钟..."
        sleep 300
    done
) &

# 前台运行 Dashboard
echo "启动 Dashboard..."
exec python3 web_dashboard.py
