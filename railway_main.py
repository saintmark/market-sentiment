#!/usr/bin/env python3
"""
Railway 主程序 - 同时运行 Dashboard 和后台任务
使用多线程方式，确保在 Railway 容器中正常运行
"""

import os
import sys
import time
import threading
import traceback
from datetime import datetime

# 设置日志文件
LOG_FILE = "/tmp/market_sentiment.log"

def log(message):
    """同时输出到控制台和文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

# 添加当前目录到路径
sys.path.insert(0, '/app')

def run_collector():
    """后台采集任务"""
    log("🚀 后台采集任务启动")
    
    # 等待几秒钟确保 Flask 先启动
    time.sleep(5)
    
    while True:
        try:
            log("========== 开始新一轮采集 ==========")
            
            # 导入模块
            try:
                from market_sentiment import Database, Collector, SentimentAnalyzer
                from dotenv import load_dotenv
                load_dotenv()
                log("✅ 模块导入成功")
            except Exception as e:
                log(f"❌ 模块导入失败: {e}")
                log(traceback.format_exc())
                time.sleep(300)
                continue
            
            # 采集新闻
            log("📰 开始采集新闻...")
            try:
                db = Database()
                log(f"✅ 数据库连接成功，路径: {db.db_path if hasattr(db, 'db_path') else 'default'}")
                
                collector = Collector(db)
                log(f"📡 开始抓取 {len(collector.feeds)} 个 RSS 源...")
                
                collector.run()
                log("✅ 采集完成")
            except Exception as e:
                log(f"❌ 采集失败: {e}")
                log(traceback.format_exc())
            
            # 情感分析
            log("🤖 开始情感分析...")
            try:
                db = Database()
                analyzer = SentimentAnalyzer(db, os.getenv('KIMI_API_KEY', ''))
                
                if not os.getenv('KIMI_API_KEY'):
                    log("⚠️ 警告: KIMI_API_KEY 未设置")
                else:
                    log(f"✅ KIMI_API_KEY 已设置: {os.getenv('KIMI_API_KEY')[:20]}...")
                
                news_list = db.get_unanalyzed_news(limit=5)
                log(f"📊 发现 {len(news_list)} 条待分析新闻")
                
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
                        log(f"❌ 分析ID={item['id']}失败: {e}")
                
                log(f"✅ 分析完成: {count}条")
            except Exception as e:
                log(f"❌ 分析任务失败: {e}")
                log(traceback.format_exc())
            
            log("========== 本轮完成，等待5分钟 ==========")
            
        except Exception as e:
            log(f"❌ 后台任务异常: {e}")
            log(traceback.format_exc())
        
        time.sleep(300)  # 5分钟

def run_dashboard():
    """运行 Dashboard"""
    log("🌐 启动 Dashboard...")
    
    try:
        from web_dashboard import app
        port = int(os.getenv('PORT', 8080))
        log(f"✅ Flask 应用导入成功，端口: {port}")
        
        # 运行 Flask
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except Exception as e:
        log(f"❌ Dashboard 启动失败: {e}")
        log(traceback.format_exc())
        raise

if __name__ == '__main__':
    log("=" * 60)
    log("🚀 市场情感系统启动")
    log(f"Python: {sys.version}")
    log(f"工作目录: {os.getcwd()}")
    log(f"系统路径: {sys.path}")
    log("=" * 60)
    
    # 启动后台采集线程
    log("🔄 启动后台采集线程...")
    collector_thread = threading.Thread(target=run_collector, daemon=True)
    collector_thread.start()
    log("✅ 后台采集线程已启动")
    
    # 主线程运行 Dashboard
    run_dashboard()
