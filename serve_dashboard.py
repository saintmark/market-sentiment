#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成静态 HTML 仪表盘并用 ngrok 暴露
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import time

DB_PATH = Path("./market_sentiment.db")
HTML_PATH = Path("./dashboard/index.html")

def generate_html():
    """生成 HTML 仪表盘"""
    
    # 读取数据库
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 统计
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            AVG(sentiment_score) as avg_sentiment,
            SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as negative,
            SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral
        FROM news
    """)
    stats = dict(cursor.fetchone())
    
    # 最新新闻
    cursor.execute("SELECT * FROM news ORDER BY published_at DESC LIMIT 20")
    news_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # 生成新闻 HTML
    news_html = ""
    for news in news_list:
        label_class = news.get('sentiment_label', 'neutral')
        label_text = {'positive': '正面', 'negative': '负面', 'neutral': '中性'}.get(label_class, '中性')
        score_text = f"({news.get('sentiment_score', 0):+.2f})" if news.get('sentiment_score') else ""
        
        news_html += f"""
        <div class="news-item">
            <div class="news-title">{news['title']}</div>
            <div class="news-meta">
                <span>来源: {news['source']}</span>
                <span class="sentiment-badge sentiment-{label_class}">{label_text}</span>
                <span>{score_text}</span>
            </div>
        </div>
        """
    
    # 情感颜色
    avg_score = stats.get('avg_sentiment', 0) or 0
    sentiment_class = 'positive' if avg_score > 0.3 else 'negative' if avg_score < -0.3 else 'neutral'
    
    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>市场情绪分析系统</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem; text-align: center; }}
        .header h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }}
        .stat-card {{ background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
        .stat-card h3 {{ font-size: 0.875rem; color: #666; margin-bottom: 0.5rem; }}
        .stat-value {{ font-size: 2rem; font-weight: 700; }}
        .stat-value.positive {{ color: #52c41a; }}
        .stat-value.negative {{ color: #f5222d; }}
        .stat-value.neutral {{ color: #faad14; }}
        .news-section {{ background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .news-section h2 {{ margin-bottom: 1rem; color: #333; }}
        .news-item {{ padding: 1rem 0; border-bottom: 1px solid #eee; }}
        .news-item:last-child {{ border-bottom: none; }}
        .news-title {{ font-weight: 600; margin-bottom: 0.5rem; color: #1890ff; }}
        .news-meta {{ font-size: 0.875rem; color: #999; display: flex; gap: 1rem; align-items: center; }}
        .sentiment-badge {{ padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.75rem; font-weight: 500; }}
        .sentiment-positive {{ background: #f6ffed; color: #52c41a; }}
        .sentiment-negative {{ background: #fff2f0; color: #f5222d; }}
        .sentiment-neutral {{ background: #fffbe6; color: #faad14; }}
        .footer {{ text-align: center; padding: 2rem; color: #999; font-size: 0.875rem; }}
        .refresh-btn {{ position: fixed; bottom: 2rem; right: 2rem; background: #1890ff; color: white; border: none; padding: 1rem 1.5rem; border-radius: 50px; cursor: pointer; font-size: 1rem; box-shadow: 0 4px 12px rgba(24,144,255,0.4); }}
        .info {{ background: #e6f7ff; border: 1px solid #91d5ff; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; color: #096dd9; }}
    </style>
</head>
<body>
    <header class="header">
        <h1>📊 市场情绪分析系统</h1>
        <p>基于 AI 的新闻情感分析与市场情绪监测</p>
    </header>
    
    <main class="container">
        <div class="info">
            <strong>系统状态：</strong>数据更新于 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>新闻总数</h3>
                <div class="stat-value">{stats.get('total', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>平均情感</h3>
                <div class="stat-value {sentiment_class}">{avg_score:+.2f}</div>
            </div>
            <div class="stat-card">
                <h3>正面新闻</h3>
                <div class="stat-value positive">{stats.get('positive', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>负面新闻</h3>
                <div class="stat-value negative">{stats.get('negative', 0)}</div>
            </div>
        </div>
        
        <section class="news-section">
            <h2>📰 最新新闻 ({len(news_list)} 条)</h2>
            {news_html}
        </section>
    </main>
    
    <footer class="footer">
        <p>市场情绪分析系统 © 2024</p>
    </footer>
    
    <button class="refresh-btn" onclick="location.reload()">🔄 刷新</button>
</body>
</html>
"""
    
    # 保存文件
    HTML_PATH.parent.mkdir(exist_ok=True)
    HTML_PATH.write_text(html, encoding='utf-8')
    print(f"✓ 仪表盘已生成: {HTML_PATH}")
    return HTML_PATH.parent

def start_server(directory, port=8080):
    """启动 HTTP 服务器"""
    os.chdir(directory)
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"🚀 Web 服务器启动: http://localhost:{port}")
    server.serve_forever()

if __name__ == '__main__':
    # 生成 HTML
    dashboard_dir = generate_html()
    
    # 启动服务器
    print("\n启动 Web 服务器...")
    print("按 Ctrl+C 停止\n")
    start_server(dashboard_dir, port=8080)
