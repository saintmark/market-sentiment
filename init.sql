-- ============================================================
-- 市场情绪分析系统数据库初始化脚本
-- Market Sentiment Analysis System - PostgreSQL Schema
-- ============================================================

-- ============================================================
-- 基础表定义 (Core Tables)
-- ============================================================

-- 新闻源表
CREATE TABLE IF NOT EXISTS news_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) NOT NULL,
    type VARCHAR(50) NOT NULL CHECK (type IN ('rss', 'api', 'scrape', 'webhook')),
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    fetch_interval INTEGER DEFAULT 300,  -- 采集间隔(秒)
    last_fetch_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 原始新闻表
CREATE TABLE IF NOT EXISTS raw_news (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES news_sources(id) ON DELETE SET NULL,
    external_id VARCHAR(255),
    title VARCHAR(500) NOT NULL,
    content TEXT,
    summary TEXT,
    url VARCHAR(1000) NOT NULL,
    author VARCHAR(200),
    language VARCHAR(10) DEFAULT 'zh',
    word_count INTEGER,
    published_at TIMESTAMP WITH TIME ZONE,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,  -- NLP处理时间
    is_processed BOOLEAN DEFAULT false,
    is_filtered BOOLEAN DEFAULT false,  -- 是否被过滤
    filter_reason VARCHAR(100),  -- 过滤原因
    raw_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, external_id)
);

-- 情感分析结果表
CREATE TABLE IF NOT EXISTS sentiment_results (
    id SERIAL PRIMARY KEY,
    news_id INTEGER REFERENCES raw_news(id) ON DELETE CASCADE,
    sentiment_score DECIMAL(5,4) NOT NULL CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    sentiment_label VARCHAR(20) NOT NULL CHECK (sentiment_label IN ('positive', 'neutral', 'negative')),
    confidence DECIMAL(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    entities JSONB DEFAULT '[]',            -- 提取的实体 [{"name": "", "type": "", "sentiment": ""}]
    keywords JSONB DEFAULT '[]',            -- 关键词
    market_impact_score INTEGER CHECK (market_impact_score >= 0 AND market_impact_score <= 100),
    impact_factors JSONB DEFAULT '{}',      -- 影响因子分析
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(50),
    raw_response TEXT,
    processing_time_ms INTEGER,             -- 处理耗时
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 市场领域/行业表
CREATE TABLE IF NOT EXISTS market_sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(50) UNIQUE,                -- 领域代码
    description TEXT,
    keywords JSONB DEFAULT '[]',            -- 关键词列表
    sentiment_keywords JSONB DEFAULT '{}',  -- 各领域情感关键词
    parent_id INTEGER REFERENCES market_sectors(id),
    weight DECIMAL(3,2) DEFAULT 1.00,       -- 权重
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 新闻与领域关联表
CREATE TABLE IF NOT EXISTS news_sectors (
    id SERIAL PRIMARY KEY,
    news_id INTEGER REFERENCES raw_news(id) ON DELETE CASCADE,
    sector_id INTEGER REFERENCES market_sectors(id) ON DELETE CASCADE,
    relevance_score DECIMAL(5,4) NOT NULL CHECK (relevance_score >= 0 AND relevance_score <= 1),
    is_primary BOOLEAN DEFAULT false,       -- 是否为主要领域
    extracted_keywords JSONB DEFAULT '[]',  -- 提取的领域相关关键词
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(news_id, sector_id)
);

-- 聚合统计数据表 (按小时)
CREATE TABLE IF NOT EXISTS hourly_sentiment_stats (
    id SERIAL PRIMARY KEY,
    sector_id INTEGER REFERENCES market_sectors(id) ON DELETE CASCADE,
    stat_time TIMESTAMP WITH TIME ZONE NOT NULL,
    news_count INTEGER DEFAULT 0,
    avg_sentiment DECIMAL(5,4),
    sentiment_std DECIMAL(5,4),             -- 标准差
    positive_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    positive_ratio DECIMAL(5,4),            -- 正面比例
    negative_ratio DECIMAL(5,4),            -- 负面比例
    avg_confidence DECIMAL(5,4),
    high_impact_count INTEGER DEFAULT 0,
    top_keywords JSONB DEFAULT '[]',        -- 热门关键词
    top_entities JSONB DEFAULT '[]',        -- 热门实体
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sector_id, stat_time)
);

-- 聚合统计数据表 (按天)
CREATE TABLE IF NOT EXISTS daily_sentiment_stats (
    id SERIAL PRIMARY KEY,
    sector_id INTEGER REFERENCES market_sectors(id) ON DELETE CASCADE,
    stat_date DATE NOT NULL,
    news_count INTEGER DEFAULT 0,
    avg_sentiment DECIMAL(5,4),
    sentiment_std DECIMAL(5,4),
    positive_count INTEGER DEFAULT 0,
    neutral_count INTEGER DEFAULT 0,
    negative_count INTEGER DEFAULT 0,
    positive_ratio DECIMAL(5,4),
    negative_ratio DECIMAL(5,4),
    avg_confidence DECIMAL(5,4),
    high_impact_count INTEGER DEFAULT 0,
    sentiment_trend VARCHAR(20) CHECK (sentiment_trend IN ('rising', 'falling', 'stable', 'volatile')),
    trend_strength DECIMAL(3,2),            -- 趋势强度 0-1
    top_keywords JSONB DEFAULT '[]',
    top_entities JSONB DEFAULT '[]',
    market_correlation DECIMAL(5,4),        -- 与市场指数的相关性
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sector_id, stat_date)
);

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    value_type VARCHAR(20) DEFAULT 'string' CHECK (value_type IN ('string', 'integer', 'float', 'boolean', 'json')),
    description TEXT,
    is_editable BOOLEAN DEFAULT true,
    category VARCHAR(50) DEFAULT 'general',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 任务执行日志表
CREATE TABLE IF NOT EXISTS job_logs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'success', 'failed', 'cancelled')),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_message TEXT,
    stack_trace TEXT,
    metadata JSONB DEFAULT '{}',
    hostname VARCHAR(100),
    pid INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 用户和认证表 (预留)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 用户订阅表
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    sector_id INTEGER REFERENCES market_sectors(id) ON DELETE CASCADE,
    alert_threshold DECIMAL(5,4),           -- 预警阈值
    alert_type VARCHAR(50) CHECK (alert_type IN ('email', 'webhook', 'sms')),
    webhook_url VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, sector_id)
);

-- ============================================================
-- 索引优化 (Index Optimization)
-- ============================================================

-- 新闻源索引
CREATE INDEX IF NOT EXISTS idx_news_sources_active ON news_sources(is_active);
CREATE INDEX IF NOT EXISTS idx_news_sources_type ON news_sources(type);
CREATE INDEX IF NOT EXISTS idx_news_sources_last_fetch ON news_sources(last_fetch_at);

-- 原始新闻索引
CREATE INDEX IF NOT EXISTS idx_raw_news_source_id ON raw_news(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_news_published_at ON raw_news(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_news_collected_at ON raw_news(collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_news_processed ON raw_news(is_processed);
CREATE INDEX IF NOT EXISTS idx_raw_news_source_external ON raw_news(source_id, external_id);
CREATE INDEX IF NOT EXISTS idx_raw_news_url ON raw_news(url);

-- 复合索引: 未处理的新闻 (用于 NLP 服务)
CREATE INDEX IF NOT EXISTS idx_raw_news_unprocessed ON raw_news(is_processed, collected_at) WHERE is_processed = false;

-- 情感分析结果索引
CREATE INDEX IF NOT EXISTS idx_sentiment_news_id ON sentiment_results(news_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_label ON sentiment_results(sentiment_label);
CREATE INDEX IF NOT EXISTS idx_sentiment_analyzed_at ON sentiment_results(analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_sentiment_score ON sentiment_results(sentiment_score);
CREATE INDEX IF NOT EXISTS idx_sentiment_impact ON sentiment_results(market_impact_score DESC);
CREATE INDEX IF NOT EXISTS idx_sentiment_label_analyzed ON sentiment_results(sentiment_label, analyzed_at);

-- 领域关联索引
CREATE INDEX IF NOT EXISTS idx_news_sectors_news_id ON news_sectors(news_id);
CREATE INDEX IF NOT EXISTS idx_news_sectors_sector_id ON news_sectors(sector_id);
CREATE INDEX IF NOT EXISTS idx_news_sectors_relevance ON news_sectors(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_news_sectors_primary ON news_sectors(is_primary) WHERE is_primary = true;

-- 聚合统计索引
CREATE INDEX IF NOT EXISTS idx_hourly_stats_sector_time ON hourly_sentiment_stats(sector_id, stat_time DESC);
CREATE INDEX IF NOT EXISTS idx_hourly_stats_time ON hourly_sentiment_stats(stat_time DESC);
CREATE INDEX IF NOT EXISTS idx_daily_stats_sector_date ON daily_sentiment_stats(sector_id, stat_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_sentiment_stats(stat_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_stats_trend ON daily_sentiment_stats(sentiment_trend);

-- 任务日志索引
CREATE INDEX IF NOT EXISTS idx_job_logs_job_name ON job_logs(job_name);
CREATE INDEX IF NOT EXISTS idx_job_logs_status ON job_logs(status);
CREATE INDEX IF NOT EXISTS idx_job_logs_started_at ON job_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_logs_job_started ON job_logs(job_name, started_at DESC);

-- 系统配置索引
CREATE INDEX IF NOT EXISTS idx_system_configs_category ON system_configs(category);

-- GIN 索引 (JSONB 字段)
CREATE INDEX IF NOT EXISTS idx_raw_news_raw_data ON raw_news USING GIN (raw_data);
CREATE INDEX IF NOT EXISTS idx_sentiment_entities ON sentiment_results USING GIN (entities);
CREATE INDEX IF NOT EXISTS idx_sentiment_keywords ON sentiment_results USING GIN (keywords);
CREATE INDEX IF NOT EXISTS idx_market_sectors_keywords ON market_sectors USING GIN (keywords);
CREATE INDEX IF NOT EXISTS idx_news_sectors_keywords ON news_sectors USING GIN (extracted_keywords);

-- ============================================================
-- 初始化数据 (Initial Data)
-- ============================================================

-- 插入默认数据源
INSERT INTO news_sources (name, url, type, config, is_active, fetch_interval) VALUES 
    ('36氪', 'https://36kr.com/feed', 'rss', '{"encoding": "utf-8", "timeout": 30}', true, 300),
    ('财新网', 'https://weekly.caixin.com/rss.xml', 'rss', '{"encoding": "utf-8"}', true, 600),
    ('华尔街见闻', 'https://wallstreetcn.com/rss.xml', 'rss', '{}', true, 300),
    ('澎湃新闻', 'https://www.thepaper.cn/rss.xml', 'rss', '{}', true, 600),
    ('界面新闻', 'https://www.jiemian.com/rss.xml', 'rss', '{}', true, 600)
ON CONFLICT (name) DO NOTHING;

-- 插入默认市场领域 (支持层级)
INSERT INTO market_sectors (name, code, description, keywords, sentiment_keywords, weight, is_active) VALUES 
    ('科技', 'tech', '科技行业相关新闻', '["科技", "技术", "AI", "人工智能", "芯片", "互联网", "软件", "硬件"]', '{"positive": ["突破", "创新", "增长"], "negative": ["下滑", "亏损", "裁员"]}', 1.00, true),
    ('金融', 'finance', '金融行业相关新闻', '["金融", "银行", "保险", "投资", "股市", "证券", "基金", "理财"]', '{"positive": ["上涨", "盈利", "分红"], "negative": ["下跌", "亏损", "风险"]}', 1.00, true),
    ('消费', 'consumer', '消费行业相关新闻', '["消费", "零售", "电商", "品牌", "购物", "餐饮", "旅游"]', '{"positive": ["热销", "增长", "扩张"], "negative": ["低迷", "关店", "亏损"]}', 0.90, true),
    ('医疗', 'healthcare', '医疗健康行业相关新闻', '["医疗", "医药", "健康", "生物科技", "疫苗", "医院"]', '{"positive": ["获批", "突破", "治愈"], "negative": ["召回", "副作用", "失败"]}', 0.95, true),
    ('新能源', 'new_energy', '新能源行业相关新闻', '["新能源", "电动车", "光伏", "储能", "电池", "风电", "氢能"]', '{"positive": ["增长", "突破", "扩张"], "negative": ["产能过剩", "降价", "亏损"]}', 0.85, true),
    ('房地产', 'real_estate', '房地产行业相关新闻', '["房地产", "楼市", "房价", "地产", "建筑", "物业"]', '{"positive": ["上涨", "热销", "回暖"], "negative": ["下跌", "滞销", "暴雷"]}', 0.80, true),
    ('制造业', 'manufacturing', '制造业相关新闻', '["制造", "工厂", "生产", "供应链", "工业", "自动化"]', '{"positive": ["订单增长", "扩产", "出口增长"], "negative": ["订单下滑", "停产", "亏损"]}', 0.85, true),
    ('人工智能', 'ai', 'AI 细分行业', '["AI", "人工智能", "大模型", "机器学习", "深度学习", "算法"]', '{"positive": ["突破", "融资", "落地"], "negative": ["泡沫", "亏损", "裁员"]}', 0.95, true, 1),
    ('半导体', 'semiconductor', '半导体细分行业', '["芯片", "半导体", "晶圆", "代工", "光刻", "集成电路"]', '{"positive": ["突破", "国产化", "扩产"], "negative": ["制裁", "短缺", "过剩"]}', 0.90, true, 1)
ON CONFLICT (name) DO NOTHING;

-- 更新 AI 和半导体领域的父级关系
UPDATE market_sectors SET parent_id = (SELECT id FROM market_sectors WHERE name = '科技') 
WHERE name IN ('人工智能', '半导体') AND parent_id IS NULL;

-- 插入系统默认配置
INSERT INTO system_configs (config_key, config_value, value_type, description, category) VALUES 
    ('collector_interval_sec', '300', 'integer', '数据采集间隔(秒)', 'collector'),
    ('sentiment_batch_size', '10', 'integer', '情感分析批处理大小', 'nlp'),
    ('sentiment_max_retries', '3', 'integer', '情感分析最大重试次数', 'nlp'),
    ('aggregation_window_hours', '24', 'integer', '聚合统计时间窗口(小时)', 'aggregator'),
    ('aggregation_interval_minutes', '60', 'integer', '聚合统计执行间隔(分钟)', 'aggregator'),
    ('data_retention_days', '90', 'integer', '原始数据保留天数', 'retention'),
    ('aggregated_data_retention_days', '365', 'integer', '聚合数据保留天数', 'retention'),
    ('log_retention_days', '30', 'integer', '日志保留天数', 'retention'),
    ('daily_report_time', '08:00', 'string', '日报生成时间', 'scheduler'),
    ('cleanup_schedule', '0 2 * * *', 'string', '数据清理定时任务(Cron表达式)', 'scheduler'),
    ('enable_auto_cleanup', 'true', 'boolean', '是否启用自动清理', 'maintenance'),
    ('enable_sentiment_alert', 'false', 'boolean', '是否启用情感预警', 'alert'),
    ('sentiment_alert_threshold', '0.8', 'float', '情感预警阈值', 'alert'),
    ('api_rate_limit', '1000', 'integer', 'API 每分钟请求限制', 'api'),
    ('api_cache_ttl', '300', 'integer', 'API 缓存时间(秒)', 'api')
ON CONFLICT (config_key) DO NOTHING;

-- ============================================================
-- 示例数据 (Sample Data) - 仅用于开发测试
-- ============================================================

-- 插入示例新闻数据
INSERT INTO raw_news (source_id, external_id, title, content, summary, url, author, published_at, is_processed, collected_at) 
SELECT 
    ns.id,
    'sample-' || ns.id || '-' || generate_series,
    case generate_series % 3 
        when 0 then '科技巨头发布新款AI芯片，性能提升50%'
        when 1 then '新能源汽车销量创新高，市场前景广阔'
        else '金融市场波动加剧，投资者需谨慎'
    end,
    case generate_series % 3 
        when 0 then '某科技公司今日发布了最新一代AI处理器，相比上一代产品性能提升了50%，能效比也有显著改善。业内专家普遍认为，这一突破将推动人工智能应用的进一步普及。'
        when 1 then '最新数据显示，新能源汽车市场持续高速增长，上月销量同比增长超过80%。多家车企宣布扩产计划，产业链上下游企业纷纷受益。'
        else '受国际局势影响，全球金融市场出现较大波动。分析师建议投资者保持谨慎，关注政策动向，合理配置资产。'
    end,
    case generate_series % 3 
        when 0 then '新一代AI处理器发布，性能大幅提升'
        when 1 then '新能源汽车销量创新高'
        else '金融市场波动加剧'
    end,
    'https://example.com/news/' || generate_series,
    '记者' || generate_series,
    NOW() - (generate_series || ' hours')::INTERVAL,
    true,
    NOW() - (generate_series || ' hours')::INTERVAL
FROM news_sources ns
CROSS JOIN generate_series(1, 5)
WHERE ns.name = '36氪'
ON CONFLICT (source_id, external_id) DO NOTHING;

-- 插入示例情感分析结果
INSERT INTO sentiment_results (news_id, sentiment_score, sentiment_label, confidence, entities, keywords, market_impact_score, analyzed_at)
SELECT 
    rn.id,
    case rn.id % 3 
        when 0 then 0.65
        when 1 then 0.45
        else -0.25
    end,
    case rn.id % 3 
        when 0 then 'positive'
        when 1 then 'neutral'
        else 'negative'
    end,
    0.85,
    case rn.id % 3 
        when 0 then '[{"name": "AI芯片", "type": "product", "sentiment": "positive"}, {"name": "科技公司", "type": "company", "sentiment": "positive"}]'::jsonb
        when 1 then '[{"name": "新能源汽车", "type": "industry", "sentiment": "positive"}]'::jsonb
        else '[{"name": "金融市场", "type": "market", "sentiment": "negative"}]'::jsonb
    end,
    case rn.id % 3 
        when 0 then '["AI", "芯片", "性能", "提升"]'::jsonb
        when 1 then '["新能源", "汽车", "销量", "增长"]'::jsonb
        else '["金融", "市场", "波动", "投资"]'::jsonb
    end,
    case rn.id % 3 
        when 0 then 75
        when 1 then 60
        else 45
    end,
    rn.collected_at + INTERVAL '5 minutes'
FROM raw_news rn
WHERE rn.id <= 5
ON CONFLICT DO NOTHING;

-- 插入示例领域关联
INSERT INTO news_sectors (news_id, sector_id, relevance_score, is_primary)
SELECT 
    rn.id,
    ms.id,
    0.85,
    true
FROM raw_news rn
CROSS JOIN market_sectors ms
WHERE rn.id <= 5
AND (
    (rn.title LIKE '%AI%' AND ms.name = '人工智能')
    OR (rn.title LIKE '%芯片%' AND ms.name = '半导体')
    OR (rn.title LIKE '%新能源%' AND ms.name = '新能源')
    OR (rn.title LIKE '%金融%' AND ms.name = '金融')
)
ON CONFLICT DO NOTHING;

-- 插入示例聚合统计数据
INSERT INTO hourly_sentiment_stats (sector_id, stat_time, news_count, avg_sentiment, positive_count, neutral_count, negative_count, avg_confidence)
SELECT 
    ms.id,
    date_trunc('hour', NOW()) - (generate_series || ' hours')::INTERVAL,
    10 + floor(random() * 20)::int,
    0.1 + (random() * 0.4 - 0.2),
    5 + floor(random() * 10)::int,
    3 + floor(random() * 5)::int,
    2 + floor(random() * 5)::int,
    0.75 + random() * 0.2
FROM market_sectors ms
CROSS JOIN generate_series(0, 23)
WHERE ms.is_active = true
ON CONFLICT (sector_id, stat_time) DO NOTHING;

-- ============================================================
-- 函数和触发器 (Functions & Triggers)
-- ============================================================

-- 更新时间戳函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器自动更新时间戳
DROP TRIGGER IF EXISTS update_news_sources_updated_at ON news_sources;
CREATE TRIGGER update_news_sources_updated_at
    BEFORE UPDATE ON news_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_system_configs_updated_at ON system_configs;
CREATE TRIGGER update_system_configs_updated_at
    BEFORE UPDATE ON system_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_market_sectors_updated_at ON market_sectors;
CREATE TRIGGER update_market_sectors_updated_at
    BEFORE UPDATE ON market_sectors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 自动计算比例触发器
CREATE OR REPLACE FUNCTION calculate_sentiment_ratios()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.news_count > 0 THEN
        NEW.positive_ratio = NEW.positive_count::DECIMAL / NEW.news_count;
        NEW.negative_ratio = NEW.negative_count::DECIMAL / NEW.news_count;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hourly_stats_ratios ON hourly_sentiment_stats;
CREATE TRIGGER trg_hourly_stats_ratios
    BEFORE INSERT OR UPDATE ON hourly_sentiment_stats
    FOR EACH ROW
    EXECUTE FUNCTION calculate_sentiment_ratios();

DROP TRIGGER IF EXISTS trg_daily_stats_ratios ON daily_sentiment_stats;
CREATE TRIGGER trg_daily_stats_ratios
    BEFORE INSERT OR UPDATE ON daily_sentiment_stats
    FOR EACH ROW
    EXECUTE FUNCTION calculate_sentiment_ratios();

-- 任务日志自动计算耗时触发器
CREATE OR REPLACE FUNCTION calculate_job_duration()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.started_at IS NOT NULL AND NEW.completed_at IS NOT NULL THEN
        NEW.duration_ms = EXTRACT(EPOCH FROM (NEW.completed_at - NEW.started_at)) * 1000;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_job_logs_duration ON job_logs;
CREATE TRIGGER trg_job_logs_duration
    BEFORE INSERT OR UPDATE ON job_logs
    FOR EACH ROW
    EXECUTE FUNCTION calculate_job_duration();

-- ============================================================
-- 视图 (Views)
-- ============================================================

-- 新闻情感分析完整视图
CREATE OR REPLACE VIEW v_news_sentiment AS
SELECT 
    rn.id,
    rn.title,
    rn.url,
    rn.published_at,
    ns.name as source_name,
    sr.sentiment_score,
    sr.sentiment_label,
    sr.confidence,
    sr.market_impact_score,
    sr.entities,
    sr.keywords,
    sr.analyzed_at
FROM raw_news rn
LEFT JOIN news_sources ns ON rn.source_id = ns.id
LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
WHERE rn.is_processed = true;

-- 领域情感统计视图
CREATE OR REPLACE VIEW v_sector_sentiment_summary AS
SELECT 
    ms.id as sector_id,
    ms.name as sector_name,
    COUNT(DISTINCT rn.id) as total_news,
    AVG(sr.sentiment_score) as avg_sentiment,
    COUNT(CASE WHEN sr.sentiment_label = 'positive' THEN 1 END) as positive_count,
    COUNT(CASE WHEN sr.sentiment_label = 'neutral' THEN 1 END) as neutral_count,
    COUNT(CASE WHEN sr.sentiment_label = 'negative' THEN 1 END) as negative_count,
    AVG(sr.confidence) as avg_confidence,
    MAX(rn.published_at) as latest_news_at
FROM market_sectors ms
LEFT JOIN news_sectors ns ON ms.id = ns.sector_id
LEFT JOIN raw_news rn ON ns.news_id = rn.id AND rn.is_processed = true
LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
WHERE ms.is_active = true
GROUP BY ms.id, ms.name;

-- ============================================================
-- 注释 (Comments)
-- ============================================================

COMMENT ON TABLE news_sources IS '新闻数据源配置表';
COMMENT ON TABLE raw_news IS '原始新闻数据表';
COMMENT ON TABLE sentiment_results IS '情感分析结果表';
COMMENT ON TABLE market_sectors IS '市场领域/行业分类表';
COMMENT ON TABLE hourly_sentiment_stats IS '小时级情感统计表';
COMMENT ON TABLE daily_sentiment_stats IS '日级情感统计表';
COMMENT ON TABLE system_configs IS '系统配置表';
COMMENT ON TABLE job_logs IS '任务执行日志表';

-- 完成初始化
SELECT 'Database initialization completed successfully!' as status;
