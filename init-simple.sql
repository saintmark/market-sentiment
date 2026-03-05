-- ============================================================
-- 市场情绪分析系统 - 简化版数据库初始化脚本
-- 只使用 PostgreSQL，去掉 Kafka/ClickHouse
-- ============================================================

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- 用于全文搜索

-- ============================================================
-- 1. 新闻源配置表
-- ============================================================
CREATE TABLE IF NOT EXISTS news_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50) NOT NULL,  -- rss, api, scraper
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    rate_limit_per_min INT DEFAULT 60,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 插入默认数据源
INSERT INTO news_sources (name, source_type, config, is_active) VALUES
('36氪', 'rss', '{"url": "https://36kr.com/feed", "language": "zh"}', TRUE),
('财新', 'rss', '{"url": "https://feed.caixin.com/rss.xml", "language": "zh"}', TRUE)
ON CONFLICT DO NOTHING;

-- ============================================================
-- 2. 原始新闻表
-- ============================================================
CREATE TABLE IF NOT EXISTS raw_news (
    id BIGSERIAL PRIMARY KEY,
    source_id INT REFERENCES news_sources(id) ON DELETE SET NULL,
    external_id VARCHAR(255),
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    url TEXT NOT NULL,
    author VARCHAR(255),
    published_at TIMESTAMP WITH TIME ZONE,
    raw_data JSONB DEFAULT '{}',
    is_processed BOOLEAN DEFAULT FALSE,  -- 是否已进行情感分析
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(source_id, external_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_raw_news_source ON raw_news(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_news_published_at ON raw_news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_news_is_processed ON raw_news(is_processed) WHERE is_processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_raw_news_title_trgm ON raw_news USING gin(title gin_trgm_ops);

-- ============================================================
-- 3. 情感分析结果表
-- ============================================================
CREATE TABLE IF NOT EXISTS sentiment_results (
    id BIGSERIAL PRIMARY KEY,
    news_id BIGINT UNIQUE REFERENCES raw_news(id) ON DELETE CASCADE,
    sentiment_score DECIMAL(4,3),  -- -1.0 到 1.0
    sentiment_label VARCHAR(20),   -- positive, negative, neutral
    confidence DECIMAL(3,2),       -- 0.0 到 1.0
    emotions JSONB DEFAULT '{}',   -- {optimism: 0.8, anxiety: 0.1, ...}
    entities JSONB DEFAULT '[]',   -- 提取的实体
    keywords JSONB DEFAULT '[]',   -- 关键词
    industry_tags JSONB DEFAULT '[]', -- 行业标签
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_sentiment_label ON sentiment_results(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_sentiment_score ON sentiment_results(sentiment_score);
CREATE INDEX IF NOT EXISTS idx_analyzed_at ON sentiment_results(analyzed_at DESC);

-- ============================================================
-- 4. 市场行业分类表
-- ============================================================
CREATE TABLE IF NOT EXISTS market_sectors (
    id SERIAL PRIMARY KEY,
    sector_code VARCHAR(20) UNIQUE NOT NULL,
    sector_name VARCHAR(100) NOT NULL,
    parent_id INT REFERENCES market_sectors(id) ON DELETE SET NULL,
    keywords JSONB DEFAULT '[]',   -- 行业关键词
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 插入申万一级行业
INSERT INTO market_sectors (sector_code, sector_name, keywords) VALUES
('sw_1_agriculture', '农林牧渔', '["农业", "种植", "养殖", "渔业", "林业", "农产品"]'),
('sw_1_mining', '基础化工', '["化工", "化学", "材料", "能源"]'),
('sw_1_steel', '钢铁', '["钢铁", "冶金", "金属"]'),
('sw_1_electronics', '电子', '["电子", "芯片", "半导体", "集成电路", "硬件"]'),
('sw_1_computer', '计算机', '["计算机", "软件", "IT", "科技", "互联网"]'),
('sw_1_media', '传媒', '["传媒", "媒体", "广告", "影视", "游戏", "娱乐"]'),
('sw_1_telecom', '通信', '["通信", "5G", "电信", "网络", "通讯"]'),
('sw_1_new_energy', '电力设备', '["新能源", "电力", "光伏", "风电", "储能", "电池"]'),
('sw_1_auto', '汽车', '["汽车", "新能源", "电动车", "造车", "自动驾驶"]'),
('sw_1_medicine', '医药生物', '["医药", "医疗", "药品", "生物", "健康", "疫苗"]'),
('sw_1_retail', '商贸零售', '["零售", "电商", "消费", "购物", "超市"]'),
('sw_1_estate', '房地产', '["房地产", "楼市", "房价", "地产", "物业"]'),
('sw_1_bank', '银行', '["银行", "金融", "贷款", "存款", "利率"]'),
('sw_1_securities', '非银金融', '["证券", "保险", "基金", "投资", "理财"]'),
('sw_1_machinery', '机械设备', '["机械", "设备", "制造", "工业", "自动化"]'),
('sw_1_defense', '国防军工', '["军工", "国防", "航空", "航天", "装备"]'),
('sw_1_construction', '建筑装饰', '["建筑", "装饰", "工程", "基建", "房地产"]'),
('sw_1_transport', '交通运输', '["交通", "运输", "物流", "航空", "航运", "快递"]'),
('sw_1_consumer', '食品饮料', '["食品", "饮料", "消费", "白酒", "零售"]'),
('sw_1_textile', '纺织服饰', '["纺织", "服装", "服饰", "面料", "时尚"]')
ON CONFLICT (sector_code) DO NOTHING;

-- ============================================================
-- 5. 新闻行业关联表
-- ============================================================
CREATE TABLE IF NOT EXISTS news_sectors (
    id BIGSERIAL PRIMARY KEY,
    news_id BIGINT REFERENCES raw_news(id) ON DELETE CASCADE,
    sector_id INT REFERENCES market_sectors(id) ON DELETE CASCADE,
    relevance_score DECIMAL(3,2),  -- 相关度 0-1
    UNIQUE(news_id, sector_id)
);

CREATE INDEX IF NOT EXISTS idx_news_sectors_news ON news_sectors(news_id);
CREATE INDEX IF NOT EXISTS idx_news_sectors_sector ON news_sectors(sector_id);

-- ============================================================
-- 6. 日度统计表
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_sentiment_stats (
    id BIGSERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    sector_id INT REFERENCES market_sectors(id) ON DELETE CASCADE,
    news_count INT DEFAULT 0,
    avg_sentiment DECIMAL(4,3),
    positive_count INT DEFAULT 0,
    neutral_count INT DEFAULT 0,
    negative_count INT DEFAULT 0,
    top_keywords JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(stat_date, sector_id)
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_sentiment_stats(stat_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_stats_sector ON daily_sentiment_stats(sector_id);

-- ============================================================
-- 7. 小时级统计表（用于趋势图）
-- ============================================================
CREATE TABLE IF NOT EXISTS hourly_sentiment_stats (
    id BIGSERIAL PRIMARY KEY,
    stat_hour TIMESTAMP WITH TIME ZONE NOT NULL,
    sector_id INT REFERENCES market_sectors(id) ON DELETE CASCADE,
    news_count INT DEFAULT 0,
    avg_sentiment DECIMAL(4,3),
    positive_count INT DEFAULT 0,
    neutral_count INT DEFAULT 0,
    negative_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(stat_hour, sector_id)
);

CREATE INDEX IF NOT EXISTS idx_hourly_stats_hour ON hourly_sentiment_stats(stat_hour DESC);
CREATE INDEX IF NOT EXISTS idx_hourly_stats_sector ON hourly_sentiment_stats(sector_id);

-- ============================================================
-- 8. 系统配置表
-- ============================================================
CREATE TABLE IF NOT EXISTS system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 插入默认配置
INSERT INTO system_configs (config_key, config_value, description) VALUES
('data_retention_days', '90', '原始数据保留天数'),
('sentiment_threshold_positive', '0.3', '正面情感阈值'),
('sentiment_threshold_negative', '-0.3', '负面情感阈值'),
('collection_interval', '300', '数据采集间隔（秒）')
ON CONFLICT (config_key) DO NOTHING;

-- ============================================================
-- 9. 任务日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS job_logs (
    id BIGSERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    job_type VARCHAR(50),  -- collect, analyze, aggregate
    status VARCHAR(20),    -- running, success, failed
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    records_processed INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_logs_name ON job_logs(job_name);
CREATE INDEX IF NOT EXISTS idx_job_logs_created ON job_logs(created_at DESC);

-- ============================================================
-- 创建更新触发器（自动更新 updated_at）
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 应用到需要自动更新的表
DROP TRIGGER IF EXISTS update_news_sources_updated_at ON news_sources;
CREATE TRIGGER update_news_sources_updated_at
    BEFORE UPDATE ON news_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_daily_stats_updated_at ON daily_sentiment_stats;
CREATE TRIGGER update_daily_stats_updated_at
    BEFORE UPDATE ON daily_sentiment_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 创建统计汇总视图
-- ============================================================
CREATE OR REPLACE VIEW v_latest_sector_sentiment AS
SELECT 
    ms.sector_code,
    ms.sector_name,
    COALESCE(dss.news_count, 0) as news_count_24h,
    dss.avg_sentiment,
    dss.positive_count,
    dss.neutral_count,
    dss.negative_count,
    CASE 
        WHEN dss.avg_sentiment > 0.3 THEN 'positive'
        WHEN dss.avg_sentiment < -0.3 THEN 'negative'
        ELSE 'neutral'
    END as sentiment_trend,
    dss.stat_date
FROM market_sectors ms
LEFT JOIN daily_sentiment_stats dss ON ms.id = dss.sector_id
WHERE dss.stat_date = CURRENT_DATE
   OR dss.stat_date IS NULL
ORDER BY dss.avg_sentiment DESC NULLS LAST;

-- ============================================================
-- 创建新闻搜索视图
-- ============================================================
CREATE OR REPLACE VIEW v_news_sentiment AS
SELECT 
    rn.id,
    rn.title,
    rn.content,
    rn.url,
    rn.author,
    rn.published_at,
    ns.source_name,
    sr.sentiment_score,
    sr.sentiment_label,
    sr.confidence,
    sr.keywords,
    sr.industry_tags,
    sr.analyzed_at
FROM raw_news rn
LEFT JOIN news_sources ns ON rn.source_id = ns.id
LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
ORDER BY rn.published_at DESC;

-- ============================================================
-- 初始化完成
-- ============================================================
