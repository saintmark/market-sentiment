#!/usr/bin/env python3
"""
Railway 主程序 - 同时运行 Dashboard 和后台任务
使用多线程方式，确保在 Railway 容器中正常运行
"""

import os
import sys
import time
import threading
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, '/app')

def run_collector():
    """后台采集任务"""
    print(f"[{datetime.now()}] 后台采集任务启动")
    
    while True:
        try:
            print(f"[{datetime.now()}] ========== 开始新一轮采集 ==========")
            
            # 导入模块
            from market_sentiment import Database, Collector, SentimentAnalyzer
            from dotenv import load_dotenv
            load_dotenv()
            
            # 采集新闻
            print(f"[{datetime.now()}] 开始采集新闻...")
            try:
                db = Database()
                collector = Collector(db)
                collector.run()
                print(f"[{datetime.now()}] [OK] 采集完成")
            except Exception as e:
                print(f"[{datetime.now()}] [ERROR] 采集失败: {e}")
            
            # 情感分析
            print(f"[{datetime.now()}] 开始情感分析...")
            try:
                db = Database()
                analyzer = SentimentAnalyzer(db, os.getenv('KIMI_API_KEY', ''))
                news_list = db.get_unanalyzed_news(limit=5)
                count = 0
                for item in news_list:
                    try:
                        text = f"{item['title']} {item.get('content', '')}"
                        result = analyzer.analyze(text[:800])
                        db.update_sentiment(
                            item['id'], 
                            result['score'], 
                            result['label'], 
                            result['keywords'], 
                            result.get('sector', '综合')
                        )
                        count += 1
                    except Exception as e:
                        print(f"[{datetime.now()}] [ERROR] 分析ID={item['id']}失败: {e}")
                print(f"[{datetime.now()}] [OK] 分析完成: {count}条")
            except Exception as e:
                print(f"[{datetime.now()}] [ERROR] 分析任务失败: {e}")
            
            print(f"[{datetime.now()}] ========== 本轮完成，等待5分钟 ==========")
            
        except Exception as e:
            print(f"[{datetime.now()}] [ERROR] 后台任务异常: {e}")
        
        time.sleep(300)  # 5分钟

def run_dashboard():
    """运行 Dashboard"""
    print(f"[{datetime.now()}] 启动 Dashboard...")
    
    # 导入 Flask 应用
    from web_dashboard import app
    port = int(os.getenv('PORT', 8080))
    
    # 运行 Flask
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 市场情感系统启动")
    print(f"时间: {datetime.now()}")
    print("=" * 60)
    
    # 启动后台采集线程
    collector_thread = threading.Thread(target=run_collector, daemon=True)
    collector_thread.start()
    print(f"[{datetime.now()}] 后台采集线程已启动")
    
    # 主线程运行 Dashboard
    run_dashboard()
