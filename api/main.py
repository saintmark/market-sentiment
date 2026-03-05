"""
市场情绪分析系统 API 网关
使用 FastAPI 提供 RESTful API 接口
"""

import os
import json
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from clickhouse_connect import get_client as get_clickhouse_client

# 配置
class Settings:
    """应用配置"""
    # API 配置
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    
    # PostgreSQL 配置
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "market_sentiment")
    
    # ClickHouse 配置
    CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    CLICKHOUSE_PORT: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    CLICKHOUSE_DB: str = os.getenv("CLICKHOUSE_DB", "market_sentiment")
    CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "default")
    CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse")
    
    # Redis 配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    
    @property
    def postgres_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()

# 数据库连接
engine = create_engine(settings.postgres_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis 连接
redis_client: Optional[redis.Redis] = None

# ClickHouse 客户端
clickhouse_client = None

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_redis() -> redis.Redis:
    """获取 Redis 连接"""
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            decode_responses=True
        )
    return redis_client

def get_clickhouse():
    """获取 ClickHouse 客户端"""
    global clickhouse_client
    if clickhouse_client is None:
        clickhouse_client = get_clickhouse_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            username=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            database=settings.CLICKHOUSE_DB
        )
    return clickhouse_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    global redis_client
    redis_client = await redis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
        decode_responses=True
    )
    yield
    # 关闭时清理
    if redis_client:
        await redis_client.close()

# 创建 FastAPI 应用
app = FastAPI(
    title="市场情绪分析 API",
    description="提供市场新闻情感分析数据的 RESTful API",
    version="1.0.0",
    lifespan=lifespan
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Pydantic 模型 ==============

class NewsItem(BaseModel):
    """新闻项"""
    id: int
    title: str
    summary: Optional[str] = None
    url: str
    author: Optional[str] = None
    source_name: str
    published_at: datetime
    sentiment_label: Optional[str] = None
    sentiment_score: Optional[float] = None
    confidence: Optional[float] = None
    
    class Config:
        from_attributes = True

class NewsListResponse(BaseModel):
    """新闻列表响应"""
    total: int
    items: List[NewsItem]
    page: int
    page_size: int

class SentimentStats(BaseModel):
    """情感统计"""
    period: str
    news_count: int
    avg_sentiment: float
    positive_count: int
    neutral_count: int
    negative_count: int
    positive_ratio: float
    negative_ratio: float

class SectorStats(BaseModel):
    """行业统计"""
    sector_id: int
    sector_name: str
    news_count: int
    avg_sentiment: float
    sentiment_trend: Optional[str] = None

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]

# ============== API 路由 ==============

@app.get("/", tags=["Root"])
async def root():
    """根路径"""
    return {
        "name": "市场情绪分析 API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """健康检查接口"""
    services = {
        "api": "healthy"
    }
    
    # 检查 PostgreSQL
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        services["postgres"] = "healthy"
    except Exception as e:
        services["postgres"] = f"unhealthy: {str(e)}"
    
    # 检查 Redis
    try:
        if redis_client:
            await redis_client.ping()
            services["redis"] = "healthy"
        else:
            services["redis"] = "unhealthy: not connected"
    except Exception as e:
        services["redis"] = f"unhealthy: {str(e)}"
    
    # 检查 ClickHouse
    try:
        ch = get_clickhouse()
        ch.command("SELECT 1")
        services["clickhouse"] = "healthy"
    except Exception as e:
        services["clickhouse"] = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy" if all(s == "healthy" for s in services.values() if s != "api") else "degraded",
        timestamp=datetime.now(),
        version="1.0.0",
        services=services
    )

@app.get("/api/v1/news", response_model=NewsListResponse, tags=["News"])
async def get_news(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sentiment: Optional[str] = Query(None, description="情感标签筛选: positive, neutral, negative"),
    sector: Optional[str] = Query(None, description="行业筛选"),
    start_date: Optional[date] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: Session = Depends(get_db)
):
    """
    获取新闻列表
    
    支持分页、情感筛选、行业筛选、日期范围和关键词搜索
    """
    # 构建查询
    query = """
        SELECT 
            rn.id,
            rn.title,
            rn.summary,
            rn.url,
            rn.author,
            ns.name as source_name,
            rn.published_at,
            sr.sentiment_label,
            sr.sentiment_score,
            sr.confidence
        FROM raw_news rn
        JOIN news_sources ns ON rn.source_id = ns.id
        LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
        WHERE 1=1
    """
    count_query = """
        SELECT COUNT(*)
        FROM raw_news rn
        JOIN news_sources ns ON rn.source_id = ns.id
        LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
        WHERE 1=1
    """
    
    params = {}
    
    # 添加筛选条件
    if sentiment:
        query += " AND sr.sentiment_label = :sentiment"
        count_query += " AND sr.sentiment_label = :sentiment"
        params["sentiment"] = sentiment
    
    if sector:
        query += """ AND rn.id IN (
            SELECT news_id FROM news_sectors ns2 
            JOIN market_sectors ms ON ns2.sector_id = ms.id 
            WHERE ms.name = :sector
        )"""
        count_query += """ AND rn.id IN (
            SELECT news_id FROM news_sectors ns2 
            JOIN market_sectors ms ON ns2.sector_id = ms.id 
            WHERE ms.name = :sector
        )"""
        params["sector"] = sector
    
    if start_date:
        query += " AND DATE(rn.published_at) >= :start_date"
        count_query += " AND DATE(rn.published_at) >= :start_date"
        params["start_date"] = start_date
    
    if end_date:
        query += " AND DATE(rn.published_at) <= :end_date"
        count_query += " AND DATE(rn.published_at) <= :end_date"
        params["end_date"] = end_date
    
    if keyword:
        query += " AND (rn.title ILIKE :keyword OR rn.content ILIKE :keyword)"
        count_query += " AND (rn.title ILIKE :keyword OR rn.content ILIKE :keyword)"
        params["keyword"] = f"%{keyword}%"
    
    # 添加排序和分页
    query += " ORDER BY rn.published_at DESC LIMIT :limit OFFSET :offset"
    params["limit"] = page_size
    params["offset"] = (page - 1) * page_size
    
    # 执行查询
    result = db.execute(text(query), params)
    items = []
    for row in result:
        items.append(NewsItem(
            id=row.id,
            title=row.title,
            summary=row.summary,
            url=row.url,
            author=row.author,
            source_name=row.source_name,
            published_at=row.published_at,
            sentiment_label=row.sentiment_label,
            sentiment_score=float(row.sentiment_score) if row.sentiment_score else None,
            confidence=float(row.confidence) if row.confidence else None
        ))
    
    # 获取总数
    total_result = db.execute(text(count_query), {k: v for k, v in params.items() if k not in ["limit", "offset"]})
    total = total_result.scalar()
    
    return NewsListResponse(
        total=total,
        items=items,
        page=page,
        page_size=page_size
    )

@app.get("/api/v1/news/{news_id}", response_model=NewsItem, tags=["News"])
async def get_news_detail(news_id: int, db: Session = Depends(get_db)):
    """获取单条新闻详情"""
    query = """
        SELECT 
            rn.id,
            rn.title,
            rn.summary,
            rn.url,
            rn.author,
            ns.name as source_name,
            rn.published_at,
            sr.sentiment_label,
            sr.sentiment_score,
            sr.confidence
        FROM raw_news rn
        JOIN news_sources ns ON rn.source_id = ns.id
        LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
        WHERE rn.id = :news_id
    """
    
    result = db.execute(text(query), {"news_id": news_id}).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="News not found")
    
    return NewsItem(
        id=result.id,
        title=result.title,
        summary=result.summary,
        url=result.url,
        author=result.author,
        source_name=result.source_name,
        published_at=result.published_at,
        sentiment_label=result.sentiment_label,
        sentiment_score=float(result.sentiment_score) if result.sentiment_score else None,
        confidence=float(result.confidence) if result.confidence else None
    )

@app.get("/api/v1/sentiment/stats", response_model=SentimentStats, tags=["Sentiment"])
async def get_sentiment_stats(
    period: str = Query("24h", description="时间周期: 24h, 7d, 30d"),
    sector: Optional[str] = Query(None, description="行业筛选"),
    db: Session = Depends(get_db)
):
    """
    获取情感分析统计
    
    支持按时间周期和行业筛选
    """
    # 解析时间周期
    if period == "24h":
        start_time = datetime.now() - timedelta(hours=24)
    elif period == "7d":
        start_time = datetime.now() - timedelta(days=7)
    elif period == "30d":
        start_time = datetime.now() - timedelta(days=30)
    else:
        start_time = datetime.now() - timedelta(hours=24)
    
    query = """
        SELECT 
            COUNT(*) as total,
            COALESCE(AVG(sr.sentiment_score), 0) as avg_sentiment,
            COUNT(CASE WHEN sr.sentiment_label = 'positive' THEN 1 END) as positive_count,
            COUNT(CASE WHEN sr.sentiment_label = 'neutral' THEN 1 END) as neutral_count,
            COUNT(CASE WHEN sr.sentiment_label = 'negative' THEN 1 END) as negative_count
        FROM raw_news rn
        LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
        WHERE rn.published_at >= :start_time
    """
    
    params = {"start_time": start_time}
    
    if sector:
        query += """ AND rn.id IN (
            SELECT news_id FROM news_sectors ns 
            JOIN market_sectors ms ON ns.sector_id = ms.id 
            WHERE ms.name = :sector
        )"""
        params["sector"] = sector
    
    result = db.execute(text(query), params).fetchone()
    
    total = result.total or 0
    positive = result.positive_count or 0
    negative = result.negative_count or 0
    
    return SentimentStats(
        period=period,
        news_count=total,
        avg_sentiment=float(result.avg_sentiment) if result.avg_sentiment else 0.0,
        positive_count=positive,
        neutral_count=result.neutral_count or 0,
        negative_count=negative,
        positive_ratio=round(positive / total * 100, 2) if total > 0 else 0.0,
        negative_ratio=round(negative / total * 100, 2) if total > 0 else 0.0
    )

@app.get("/api/v1/sectors", response_model=List[SectorStats], tags=["Sectors"])
async def get_sectors(
    period: str = Query("24h", description="时间周期: 24h, 7d, 30d"),
    db: Session = Depends(get_db)
):
    """
    获取各行业情感统计
    """
    # 解析时间周期
    if period == "24h":
        start_time = datetime.now() - timedelta(hours=24)
    elif period == "7d":
        start_time = datetime.now() - timedelta(days=7)
    elif period == "30d":
        start_time = datetime.now() - timedelta(days=30)
    else:
        start_time = datetime.now() - timedelta(hours=24)
    
    query = """
        SELECT 
            ms.id as sector_id,
            ms.name as sector_name,
            COUNT(rn.id) as news_count,
            COALESCE(AVG(sr.sentiment_score), 0) as avg_sentiment
        FROM market_sectors ms
        LEFT JOIN news_sectors ns ON ms.id = ns.sector_id
        LEFT JOIN raw_news rn ON ns.news_id = rn.id AND rn.published_at >= :start_time
        LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
        GROUP BY ms.id, ms.name
        ORDER BY news_count DESC
    """
    
    result = db.execute(text(query), {"start_time": start_time})
    
    sectors = []
    for row in result:
        # 判断趋势
        trend = "stable"
        if row.avg_sentiment > 0.3:
            trend = "positive"
        elif row.avg_sentiment < -0.3:
            trend = "negative"
        
        sectors.append(SectorStats(
            sector_id=row.sector_id,
            sector_name=row.sector_name,
            news_count=row.news_count,
            avg_sentiment=float(row.avg_sentiment) if row.avg_sentiment else 0.0,
            sentiment_trend=trend
        ))
    
    return sectors

@app.get("/api/v1/trends", tags=["Trends"])
async def get_trends(
    days: int = Query(7, ge=1, le=90, description="天数"),
    sector: Optional[str] = Query(None, description="行业筛选"),
    db: Session = Depends(get_db)
):
    """
    获取情感趋势数据
    
    返回指定天数内的每日情感统计数据
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    query = """
        SELECT 
            DATE(rn.published_at) as date,
            COUNT(*) as count,
            COALESCE(AVG(sr.sentiment_score), 0) as avg_sentiment,
            COUNT(CASE WHEN sr.sentiment_label = 'positive' THEN 1 END) as positive,
            COUNT(CASE WHEN sr.sentiment_label = 'neutral' THEN 1 END) as neutral,
            COUNT(CASE WHEN sr.sentiment_label = 'negative' THEN 1 END) as negative
        FROM raw_news rn
        LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
        WHERE DATE(rn.published_at) BETWEEN :start_date AND :end_date
    """
    
    params = {"start_date": start_date, "end_date": end_date}
    
    if sector:
        query += """ AND rn.id IN (
            SELECT news_id FROM news_sectors ns 
            JOIN market_sectors ms ON ns.sector_id = ms.id 
            WHERE ms.name = :sector
        )"""
        params["sector"] = sector
    
    query += " GROUP BY DATE(rn.published_at) ORDER BY date"
    
    result = db.execute(text(query), params)
    
    trends = []
    for row in result:
        trends.append({
            "date": row.date.isoformat(),
            "count": row.count,
            "avg_sentiment": float(row.avg_sentiment) if row.avg_sentiment else 0.0,
            "positive": row.positive,
            "neutral": row.neutral,
            "negative": row.negative
        })
    
    return {"trends": trends, "days": days, "sector": sector}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)