#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场情绪分析系统 - Web 仪表盘 (优化版)
减少数据传输，提升加载速度
"""

import os
import json
import sqlite3
from flask import Flask, render_template_string, jsonify, abort
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
# Railway 使用 Volume 持久化数据，本地使用当前目录
DB_PATH = Path(os.getenv('RAILWAY_VOLUME_MOUNT_PATH', '.')) / 'market_sentiment.db'

# 简化的 HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>市场情绪分析</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, -apple-system, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; text-align: center; }
        .header h1 { font-size: 1.5rem; margin-bottom: 0.25rem; }
        .header p { font-size: 0.875rem; opacity: 0.9; }
        .container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin-bottom: 1rem; }
        .stat { background: white; padding: 1rem; border-radius: 6px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stat h3 { font-size: 0.75rem; color: #666; margin-bottom: 0.25rem; }
        .stat .val { font-size: 1.5rem; font-weight: 600; }
        .stat .val.pos { color: #52c41a; }
        .stat .val.neg { color: #f5222d; }
        .sector-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 0.5rem; margin-bottom: 1rem; }
        .sector { background: white; padding: 0.75rem; border-radius: 6px; text-align: center; font-size: 0.875rem; }
        .sector .name { color: #666; margin-bottom: 0.25rem; }
        .sector .score { font-size: 1.25rem; font-weight: 600; }
        .sector .count { font-size: 0.75rem; color: #999; }
        .news-list { background: white; border-radius: 6px; padding: 1rem; }
        .news-item { padding: 0.75rem 0; border-bottom: 1px solid #eee; }
        .news-item:last-child { border-bottom: none; }
        .news-title { color: #1890ff; text-decoration: none; font-weight: 500; display: block; margin-bottom: 0.25rem; }
        .news-title:hover { text-decoration: underline; }
        .news-meta { font-size: 0.75rem; color: #999; }
        .tag { display: inline-block; padding: 0.1rem 0.4rem; border-radius: 3px; margin-right: 0.25rem; }
        .tag-pos { background: #f6ffed; color: #52c41a; }
        .tag-neg { background: #fff2f0; color: #f5222d; }
        .tag-neu { background: #f5f5f5; color: #666; }
        .tag-sec { background: #e6f7ff; color: #1890ff; }
        .refresh { position: fixed; bottom: 1rem; right: 1rem; background: #1890ff; color: white; border: none; padding: 0.75rem 1rem; border-radius: 50px; cursor: pointer; }
    </style>
</head>
<body>
    <header class="header">
        <h1>📊 市场情绪分析</h1>
        <p>基于 AI 的新闻情感分析与市场情绪监测</p>
    </header>
    <main class="container">
        <div class="stats">
            <div class="stat"><h3>新闻总数</h3><div class="val">{{ stats.total }}</div></div>
            <div class="stat"><h3>平均情感</h3><div class="val {{ 'pos' if stats.avg > 0.3 else 'neg' if stats.avg < -0.3 else '' }}">{{ "%.2f" | format(stats.avg) }}</div></div>
            <div class="stat"><h3>正面</h3><div class="val pos">{{ stats.pos }}</div></div>
            <div class="stat"><h3>负面</h3><div class="val neg">{{ stats.neg }}</div></div>
        </div>
        
        <div class="sector-grid">
            {% for s in sectors %}
            <div class="sector">
                <div class="name">{{ s.name }}</div>
                <div class="score" style="color: {{ '#52c41a' if s.score > 0.3 else '#f5222d' if s.score < -0.3 else '#999' }}">{{ "%.2f" | format(s.score) }}</div>
                <div class="count">{{ s.count }}条</div>
            </div>
            {% endfor %}
        </div>
        
        <div class="news-list">
            {% for n in news %}
            <div class="news-item">
                <a href="/news/{{ n.id }}" class="news-title">{{ n.title }}</a>
                <div class="news-meta">
                    <span class="tag tag-sec">{{ n.source }}</span>
                    {% if n.sector %}<span class="tag tag-sec">{{ n.sector }}</span>{% endif %}
                    <span class="tag tag-{{ 'pos' if n.label == 'positive' else 'neg' if n.label == 'negative' else 'neu' }}">{{ '正面' if n.label == 'positive' else '负面' if n.label == 'negative' else '中性' }}</span>
                    {% if n.score != 0 %}<span>{{ "%.2f" | format(n.score) }}</span>{% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
    </main>
    <button class="refresh" onclick="location.reload()">🔄</button>
</body>
</html>
"""

DETAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ news.title[:20] }}...</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; }
        .back { background: rgba(255,255,255,0.2); color: white; border: none; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; }
        .container { max-width: 800px; margin: 0 auto; padding: 1rem; }
        .card { background: white; border-radius: 6px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .title { font-size: 1.25rem; font-weight: 600; margin-bottom: 0.75rem; }
        .meta { font-size: 0.875rem; color: #666; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid #eee; }
        .tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.75rem; margin-right: 0.5rem; }
        .tag-pos { background: #f6ffed; color: #52c41a; }
        .tag-neg { background: #fff2f0; color: #f5222d; }
        .tag-neu { background: #f5f5f5; color: #666; }
        .tag-sec { background: #e6f7ff; color: #1890ff; }
        .content { line-height: 1.8; margin-bottom: 1rem; }
        .link { color: #1890ff; text-decoration: none; }
        .link:hover { text-decoration: underline; }
        .kw { display: inline-block; background: #f0f5ff; color: #2f54eb; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.875rem; margin-right: 0.25rem; }
    </style>
</head>
<body>
    <header class="header">
        <button class="back" onclick="history.back()">← 返回</button>
        <h1>新闻详情</h1>
    </header>
    <main class="container">
        <article class="card">
            <h1 class="title">{{ news.title }}</h1>
            <div class="meta">
                <span class="tag tag-sec">{{ news.source }}</span>
                {% if news.sector %}<span class="tag tag-sec">{{ news.sector }}</span>{% endif %}
                {% if news.sentiment_label %}<span class="tag tag-{{ 'pos' if news.sentiment_label == 'positive' else 'neg' if news.sentiment_label == 'negative' else 'neu' }}">{{ '正面' if news.sentiment_label == 'positive' else '负面' if news.sentiment_label == 'negative' else '中性' }}</span>{% endif %}
                {% if news.sentiment_score != 0 %}<span>分数: {{ "%.2f" | format(news.sentiment_score) }}</span>{% endif %}
            </div>
            <div class="content">{{ news.content | safe }}</div>
            {% if news.url %}<a href="{{ news.url }}" target="_blank" class="link">🔗 查看原文 →</a>{% endif %}
            {% if keywords %}
            <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #eee;">
                <p style="font-size: 0.875rem; color: #666; margin-bottom: 0.5rem;">关键词:</p>
                {% for kw in keywords %}<span class="kw">{{ kw }}</span>{% endfor %}
            </div>
            {% endif %}
        </article>
    </main>
</body>
</html>
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db()
    
    # 统计数据
    r = conn.execute("""
        SELECT COUNT(*) as total, AVG(sentiment_score) as avg,
               SUM(CASE WHEN sentiment_label='positive' THEN 1 ELSE 0 END) as pos,
               SUM(CASE WHEN sentiment_label='negative' THEN 1 ELSE 0 END) as neg
        FROM news
    """).fetchone()
    stats = {"total": r[0] or 0, "avg": r[1] or 0, "pos": r[2] or 0, "neg": r[3] or 0}
    
    # 行业统计（限制数量）
    sectors = []
    for row in conn.execute("""
        SELECT sector, COUNT(*) as cnt, AVG(sentiment_score) as score
        FROM news WHERE analyzed=1 AND sector IS NOT NULL AND sector!='' AND sector!='综合'
        GROUP BY sector ORDER BY cnt DESC LIMIT 8
    """):
        sectors.append({"name": row[0], "count": row[1], "score": round(row[2], 2)})
    
    # 最新新闻（限制10条）
    news = []
    for row in conn.execute("SELECT * FROM news ORDER BY published_at DESC LIMIT 10"):
        news.append({
            "id": row[0], "title": row[1], "content": row[2],
            "source": row[4], "sector": row[10], "label": row[7], "score": row[6]
        })
    conn.close()
    
    return render_template_string(HTML_TEMPLATE, stats=stats, sectors=sectors, news=news)

@app.route('/news/<int:nid>')
def detail(nid):
    conn = get_db()
    r = conn.execute("SELECT * FROM news WHERE id=?", (nid,)).fetchone()
    conn.close()
    if not r: abort(404)
    
    news = dict(r)
    keywords = json.loads(news.get('keywords', '[]')) if news.get('keywords') else []
    return render_template_string(DETAIL_TEMPLATE, news=news, keywords=keywords)

@app.route('/health')
def health():
    return jsonify({"status": "ok", "t": datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print(f"🚀 Dashboard on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
