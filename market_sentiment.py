#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
市场情绪分析系统 - 极简版
使用 SQLite + 直接调用 Kimi API，不依赖 Docker
"""

import os
import sys
import json
import sqlite3
import asyncio
import argparse
import feedparser
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin

# 配置 - 优先使用 Railway Volume 路径
DB_PATH = Path(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", ".")) / "market_sentiment.db"
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"

@dataclass
class NewsItem:
    """新闻条目"""
    id: int
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    sentiment_score: float = 0.0
    sentiment_label: str = ""
    keywords: List[str] = None

class Database:
    """SQLite 数据库操作"""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 新闻表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                url TEXT UNIQUE,
                source TEXT,
                published_at TIMESTAMP,
                sentiment_score REAL DEFAULT 0,
                sentiment_label TEXT DEFAULT '',
                keywords TEXT DEFAULT '[]',
                analyzed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 行业表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                name TEXT,
                keywords TEXT
            )
        """)
        
        # 日统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stat_date DATE,
                sector_id INTEGER,
                news_count INTEGER DEFAULT 0,
                avg_sentiment REAL,
                positive_count INTEGER DEFAULT 0,
                negative_count INTEGER DEFAULT 0,
                neutral_count INTEGER DEFAULT 0,
                UNIQUE(stat_date, sector_id)
            )
        """)
        
        # 插入默认行业
        sectors = [
            ("tech", "科技", "[\"科技\",\"互联网\",\"AI\",\"软件\",\"芯片\"]"),
            ("finance", "金融", "[\"金融\",\"银行\",\"证券\",\"保险\",\"投资\"]"),
            ("estate", "房地产", "[\"房地产\",\"楼市\",\"房价\",\"地产\"]"),
            ("consumer", "消费", "[\"消费\",\"零售\",\"电商\",\"食品\"]"),
            ("energy", "能源", "[\"能源\",\"新能源\",\"光伏\",\"电力\"]"),
            ("medicine", "医药", "[\"医药\",\"医疗\",\"健康\",\"药品\"]"),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO sectors (code, name, keywords) VALUES (?, ?, ?)",
            sectors
        )
        
        conn.commit()
        conn.close()
    
    def save_news(self, news_list: List[Dict]) -> int:
        """保存新闻列表，返回保存数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved = 0
        for news in news_list:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO news (title, content, url, source, published_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    news["title"],
                    news.get("content", ""),
                    news["url"],
                    news.get("source", "unknown"),
                    news.get("published_at", datetime.now())
                ))
                if cursor.rowcount > 0:
                    saved += 1
            except Exception as e:
                print(f"保存新闻失败: {e}")
        
        conn.commit()
        conn.close()
        return saved
    
    def get_unanalyzed_news(self, limit: int = 10) -> List[Dict]:
        """获取未分析的新闻"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM news 
            WHERE analyzed = 0 
            ORDER BY published_at DESC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_sentiment(self, news_id: int, sentiment_score: float, 
                        sentiment_label: str, keywords: List[str], sector: str = ""):
        """更新情感分析结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE news 
            SET sentiment_score = ?, sentiment_label = ?, keywords = ?, sector = ?, analyzed = 1
            WHERE id = ?
        """, (sentiment_score, sentiment_label, json.dumps(keywords), sector, news_id))
        
        conn.commit()
        conn.close()
    
    def get_stats(self, days: int = 7) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(sentiment_score) as avg_sentiment,
                SUM(CASE WHEN sentiment_label = 'positive' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN sentiment_label = 'negative' THEN 1 ELSE 0 END) as negative,
                SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral
            FROM news
            WHERE created_at >= datetime('now', '-{} days')
        """.format(days))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            "total": row[0] or 0,
            "avg_sentiment": round(row[1] or 0, 2),
            "positive": row[2] or 0,
            "negative": row[3] or 0,
            "neutral": row[4] or 0
        }
    
    def get_news_list(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """获取新闻列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM news 
            ORDER BY published_at DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]


class Collector:
    """数据采集器"""
    
    def __init__(self, db: Database):
        self.db = db
        self.feeds = [
            {"name": "36氪", "url": "https://36kr.com/feed"},
            {"name": "IT之家", "url": "https://www.ithome.com/rss"},
            {"name": "Solidot", "url": "https://www.solidot.org/index.rss"},
        ]
    
    def fetch_rss(self, feed_url: str, source_name: str) -> List[Dict]:
        """抓取 RSS 源"""
        try:
            print(f"正在抓取: {source_name} ({feed_url})")
            feed = feedparser.parse(feed_url)
            
            news_list = []
            for entry in feed.entries[:20]:  # 只取前20条
                news = {
                    "title": entry.get("title", ""),
                    "content": entry.get("summary", entry.get("description", "")),
                    "url": entry.get("link", ""),
                    "source": source_name,
                    "published_at": self._parse_date(entry.get("published", ""))
                }
                news_list.append(news)
            
            return news_list
        except Exception as e:
            print(f"抓取 {source_name} 失败: {e}")
            return []
    
    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串 - 支持多种 RSS 格式"""
        if not date_str:
            return datetime.now()
        
        # 尝试多种日期格式
        formats = [
            "%a, %d %b %Y %H:%M:%S",      # RFC 2822: Thu, 05 Mar 2026 09:24:26
            "%Y-%m-%d %H:%M:%S",           # ISO: 2026-03-05 17:07:14
            "%Y-%m-%dT%H:%M:%S",           # ISO8601: 2026-03-05T17:07:14
        ]
        
        for fmt in formats:
            try:
                # 去掉时区信息尝试解析
                clean_str = date_str.split('+')[0].split('GMT')[0].strip()[:25]
                return datetime.strptime(clean_str, fmt)
            except:
                continue
        
        # 都失败了返回当前时间
        return datetime.now()
    
    def run(self):
        """运行采集"""
        print("\n=== 开始数据采集 ===")
        total_saved = 0
        
        for feed in self.feeds:
            news_list = self.fetch_rss(feed["url"], feed["name"])
            saved = self.db.save_news(news_list)
            total_saved += saved
            print(f"  {feed['name']}: 抓取 {len(news_list)} 条，保存 {saved} 条")
        
        print(f"\n✓ 共保存 {total_saved} 条新闻")


class SentimentAnalyzer:
    """情感分析器"""
    
    def __init__(self, db: Database, api_key: str):
        self.db = db
        self.api_key = api_key
    
    def analyze(self, text: str) -> Dict:
        """分析单条文本的情感和行业"""
        if not self.api_key:
            print("警告: 未设置 API Key，使用随机情感")
            return {
                "score": 0.0,
                "label": "neutral",
                "keywords": [],
                "sector": "其他"
            }
        
        prompt = f'''分析以下新闻的情感倾向和所属行业，返回 JSON 格式：

新闻内容: {text[:500]}

请分析：
1. sentiment_score: 情感分数 (-1.0 到 1.0)
2. sentiment_label: 情感标签 (positive/negative/neutral)
3. keywords: 关键词列表 (3-5 个)
4. sector: 所属行业（从以下分类中选择最接近的一个）

行业分类（参考A股申万一级行业）：
- 电子（芯片、半导体、消费电子）
- 计算机（软件、IT服务、云计算、AI）
- 通信（5G、电信、通信设备）
- 传媒（游戏、影视、广告、互联网）
- 电力设备（新能源、光伏、电池、电网）
- 机械设备（机器人、工业机械、自动化）
- 汽车（新能源汽车、零部件、整车）
- 医药生物（制药、医疗器械、生物科技）
- 食品饮料（白酒、食品、饮料）
- 家用电器（家电、智能家居）
- 银行（商业银行、投资银行）
- 非银金融（保险、证券、信托）
- 房地产（房地产开发、物业管理）
- 交通运输（物流、航空、港口、快递）
- 煤炭（煤炭开采、煤化工）
- 有色金属（锂、铜、铝、稀土）
- 化工（化学制品、石油化工、材料）
- 钢铁（钢铁冶炼、特钢）
- 建筑材料（水泥、玻璃、建材）
- 建筑装饰（工程建筑、装修）
- 农林牧渔（农业、养殖、渔业）
- 商贸零售（电商、超市、零售）
- 社会服务（旅游、教育、餐饮）
- 公用事业（电力、燃气、水务、环保）
- 国防军工（军工、航天、船舶）
- 综合（多元化业务，无法归类）

返回格式：
{{
    "sentiment_score": 0.5,
    "sentiment_label": "positive",
    "keywords": ["AI", "投资", "增长"],
    "sector": "计算机"
}}'''

        try:
            response = requests.post(
                KIMI_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                data = json.loads(content)
                return {
                    "score": float(data.get("sentiment_score", 0)),
                    "label": data.get("sentiment_label", "neutral"),
                    "keywords": data.get("keywords", []),
                    "sector": data.get("sector", "综合")
                }
            else:
                print(f"API 错误: {response.status_code} - {response.text}")
                return {"score": 0, "label": "neutral", "keywords": [], "sector": "综合"}
                
        except Exception as e:
            print(f"分析失败: {e}")
            return {"score": 0, "label": "neutral", "keywords": [], "sector": "综合"}
    
    def run(self, batch_size: int = 5):
        """运行分析"""
        print("\n=== 开始情感分析 ===")
        
        news_list = self.db.get_unanalyzed_news(limit=batch_size)
        if not news_list:
            print("没有待分析的新闻")
            return
        
        print(f"找到 {len(news_list)} 条待分析新闻")
        
        for i, news in enumerate(news_list, 1):
            print(f"\n[{i}/{len(news_list)}] 分析: {news['title'][:50]}...")
            
            text = f"{news['title']} {news['content']}"
            result = self.analyze(text)
            
            self.db.update_sentiment(
                news['id'], 
                result['score'], 
                result['label'],
                result['keywords'],
                result.get('sector', '综合')
            )
            
            print(f"  结果: {result['label']} ({result['score']:+.2f}) [{result.get('sector', '综合')}]")
        
        print(f"\n✓ 分析完成 {len(news_list)} 条新闻")


class Reporter:
    """报告生成器"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def generate_report(self):
        """生成统计报告"""
        print("\n=== 市场情绪报告 ===")
        
        stats = self.db.get_stats(days=7)
        
        print(f"\n过去 7 天统计:")
        print(f"  新闻总数: {stats['total']}")
        print(f"  平均情感: {stats['avg_sentiment']:+.2f}")
        print(f"  正面新闻: {stats['positive']} ({self._pct(stats['positive'], stats['total'])})")
        print(f"  负面新闻: {stats['negative']} ({self._pct(stats['negative'], stats['total'])})")
        print(f"  中性新闻: {stats['neutral']} ({self._pct(stats['neutral'], stats['total'])})")
        
        print(f"\n市场情绪: {self._sentiment_emoji(stats['avg_sentiment'])} {self._sentiment_text(stats['avg_sentiment'])}")
    
    def _pct(self, part: int, total: int) -> str:
        """计算百分比"""
        if total == 0:
            return "0%"
        return f"{part/total*100:.1f}%"
    
    def _sentiment_emoji(self, score: float) -> str:
        """情感表情"""
        if score > 0.3:
            return "😊"
        elif score < -0.3:
            return "😔"
        return "😐"
    
    def _sentiment_text(self, score: float) -> str:
        """情感文字"""
        if score > 0.3:
            return "偏正面"
        elif score < -0.3:
            return "偏负面"
        return "中性"
    
    def show_latest_news(self, count: int = 5):
        """显示最新新闻"""
        print("\n=== 最新新闻 ===")
        
        news_list = self.db.get_news_list(limit=count)
        for news in news_list:
            emoji = "😊" if news.get('sentiment_label') == 'positive' else "😔" if news.get('sentiment_label') == 'negative' else "😐"
            print(f"\n{emoji} {news['title']}")
            print(f"   来源: {news['source']} | 情感: {news.get('sentiment_label', '未分析')}")


def main():
    parser = argparse.ArgumentParser(description="市场情绪分析系统 - 极简版")
    parser.add_argument("command", choices=["collect", "analyze", "report", "all", "web"], 
                       help="要执行的命令")
    parser.add_argument("--batch-size", type=int, default=5, help="分析批次大小")
    
    args = parser.parse_args()
    
    # 检查 API Key
    if not KIMI_API_KEY:
        print("警告: 环境变量 KIMI_API_KEY 未设置")
        print("情感分析功能将无法使用")
    
    # 初始化数据库
    db = Database()
    
    # 执行命令
    if args.command == "collect":
        collector = Collector(db)
        collector.run()
    
    elif args.command == "analyze":
        analyzer = SentimentAnalyzer(db, KIMI_API_KEY)
        analyzer.run(batch_size=args.batch_size)
    
    elif args.command == "report":
        reporter = Reporter(db)
        reporter.generate_report()
        reporter.show_latest_news()
    
    elif args.command == "all":
        # 执行完整流程
        collector = Collector(db)
        collector.run()
        
        analyzer = SentimentAnalyzer(db, KIMI_API_KEY)
        analyzer.run(batch_size=args.batch_size)
        
        reporter = Reporter(db)
        reporter.generate_report()
        reporter.show_latest_news()
    
    elif args.command == "web":
        print("Web 界面功能开发中...")
        print("目前可以使用 SQLite 数据库查看器查看数据")
        print(f"数据库位置: {DB_PATH.absolute()}")


if __name__ == "__main__":
    main()
