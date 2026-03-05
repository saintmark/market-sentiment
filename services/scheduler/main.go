package main

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-co-op/gocron/v2"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
	"github.com/sirupsen/logrus"
)

// 配置结构体
type Config struct {
	// PostgreSQL 配置
	PostgresHost     string
	PostgresPort     string
	PostgresUser     string
	PostgresPassword string
	PostgresDB       string

	// Redis 配置
	RedisHost string
	RedisPort string

	// Collector API 配置
	CollectorAPIURL string

	// 定时任务配置
	DailyReportTime string // 格式: "08:00"
}

var log = logrus.New()

// 从环境变量加载配置
func loadConfig() Config {
	return Config{
		PostgresHost:     getEnv("POSTGRES_HOST", "localhost"),
		PostgresPort:     getEnv("POSTGRES_PORT", "5432"),
		PostgresUser:     getEnv("POSTGRES_USER", "postgres"),
		PostgresPassword: getEnv("POSTGRES_PASSWORD", "postgres"),
		PostgresDB:       getEnv("POSTGRES_DB", "market_sentiment"),
		RedisHost:        getEnv("REDIS_HOST", "localhost"),
		RedisPort:        getEnv("REDIS_PORT", "6379"),
		CollectorAPIURL:  getEnv("COLLECTOR_API_URL", "http://collector:8080"),
		DailyReportTime:  getEnv("DAILY_REPORT_TIME", "08:00"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func main() {
	log.SetFormatter(&logrus.JSONFormatter{})
	log.SetLevel(logrus.InfoLevel)

	cfg := loadConfig()
	log.Info("Scheduler service starting...")

	// 连接 PostgreSQL
	pgConnStr := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		cfg.PostgresUser, cfg.PostgresPassword, cfg.PostgresHost, cfg.PostgresPort, cfg.PostgresDB)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	pgPool, err := pgxpool.New(ctx, pgConnStr)
	cancel()

	if err != nil {
		log.Fatalf("Failed to connect to PostgreSQL: %v", err)
	}
	defer pgPool.Close()
	log.Info("Connected to PostgreSQL")

	// 连接 Redis
	redisAddr := fmt.Sprintf("%s:%s", cfg.RedisHost, cfg.RedisPort)
	rdb := redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})

	if err := rdb.Ping(context.Background()).Err(); err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	defer rdb.Close()
	log.Info("Connected to Redis")

	// 创建调度器
	s, err := gocron.NewScheduler()
	if err != nil {
		log.Fatalf("Failed to create scheduler: %v", err)
	}

	// 注册任务
	registerJobs(s, cfg, pgPool, rdb)

	// 启动调度器
	s.Start()
	log.Info("Scheduler started")

	// 设置信号处理
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// 等待退出信号
	<-sigChan
	log.Info("Shutting down scheduler service...")

	// 停止调度器
	if err := s.Shutdown(); err != nil {
		log.Errorf("Error shutting down scheduler: %v", err)
	}

	log.Info("Scheduler service stopped")
}

// 注册定时任务
func registerJobs(s gocron.Scheduler, cfg Config, pgPool *pgxpool.Pool, rdb *redis.Client) {
	// 任务1: 每小时更新缓存的统计数据
	_, err := s.NewJob(
		gocron.DurationJob(
			gocron.DurationJobTimeUnit(
				gocron.NewDurationRandomJobTimeUnit(
					time.Hour,
					time.Hour+10*time.Minute,
				),
			),
		),
		gocron.NewTask(func() {
			updateStatsCache(pgPool, rdb)
		}),
		gocron.WithName("update-stats-cache"),
		gocron.WithIdentifier("update-stats-cache"),
	)
	if err != nil {
		log.Fatalf("Failed to register update-stats-cache job: %v", err)
	}
	log.Info("Registered job: update-stats-cache")

	// 任务2: 每天生成日报
	_, err = s.NewJob(
		gocron.DailyJob(
			1,
			gocron.NewAtTimes(
				gocron.NewAtTime(8, 0, 0),
			),
		),
		gocron.NewTask(func() {
			generateDailyReport(pgPool)
		}),
		gocron.WithName("generate-daily-report"),
		gocron.WithIdentifier("generate-daily-report"),
	)
	if err != nil {
		log.Fatalf("Failed to register generate-daily-report job: %v", err)
	}
	log.Info("Registered job: generate-daily-report")

	// 任务3: 清理旧数据 (每周日凌晨2点)
	_, err = s.NewJob(
		gocron.WeeklyJob(
			1,
			gocron.NewWeekdays(time.Sunday),
			gocron.NewAtTimes(
				gocron.NewAtTime(2, 0, 0),
			),
		),
		gocron.NewTask(func() {
			cleanupOldData(pgPool)
		}),
		gocron.WithName("cleanup-old-data"),
		gocron.WithIdentifier("cleanup-old-data"),
	)
	if err != nil {
		log.Fatalf("Failed to register cleanup-old-data job: %v", err)
	}
	log.Info("Registered job: cleanup-old-data")

	// 任务4: 触发数据采集 (每5分钟)
	_, err = s.NewJob(
		gocron.DurationJob(
			gocron.DurationJobTimeUnit(
				time.Duration(5*time.Minute),
			),
		),
		gocron.NewTask(func() {
			triggerCollector(cfg)
		}),
		gocron.WithName("trigger-collector"),
		gocron.WithIdentifier("trigger-collector"),
	)
	if err != nil {
		log.Fatalf("Failed to register trigger-collector job: %v", err)
	}
	log.Info("Registered job: trigger-collector")
}

// 更新缓存的统计数据
func updateStatsCache(pgPool *pgxpool.Pool, rdb *redis.Client) {
	log.Info("Running job: update-stats-cache")
	ctx := context.Background()

	// 记录任务开始
	_, err := pgPool.Exec(ctx, `
		INSERT INTO job_logs (job_name, job_type, status, started_at)
		VALUES ('update-stats-cache', 'cache', 'running', NOW())
	`)
	if err != nil {
		log.Errorf("Failed to log job start: %v", err)
	}

	// 获取24小时统计
	var stats struct {
		Total         int64   `db:"total"`
		AvgSentiment  float64 `db:"avg_sentiment"`
		Positive      int64   `db:"positive"`
		Neutral       int64   `db:"neutral"`
		Negative      int64   `db:"negative"`
	}

	err = pgPool.QueryRow(ctx, `
		SELECT 
			COUNT(*) as total,
			COALESCE(AVG(sr.sentiment_score), 0) as avg_sentiment,
			COUNT(CASE WHEN sr.sentiment_label = 'positive' THEN 1 END) as positive,
			COUNT(CASE WHEN sr.sentiment_label = 'neutral' THEN 1 END) as neutral,
			COUNT(CASE WHEN sr.sentiment_label = 'negative' THEN 1 END) as negative
		FROM raw_news rn
		LEFT JOIN sentiment_results sr ON rn.id = sr.news_id
		WHERE rn.published_at >= NOW() - INTERVAL '24 hours'
	`).Scan(&stats.Total, &stats.AvgSentiment, &stats.Positive, &stats.Neutral, &stats.Negative)

	if err != nil {
		log.Errorf("Failed to query stats: %v", err)
		// 记录失败
		pgPool.Exec(ctx, `
			UPDATE job_logs SET status = 'failed', completed_at = NOW(), error_message = $1
			WHERE job_name = 'update-stats-cache' AND status = 'running'
		`, err.Error())
		return
	}

	// 写入 Redis
	statsJSON := fmt.Sprintf(`{
		"total": %d,
		"avg_sentiment": %f,
		"positive": %d,
		"neutral": %d,
		"negative": %d,
		"updated_at": "%s"
	}`, stats.Total, stats.AvgSentiment, stats.Positive, stats.Neutral, stats.Negative, time.Now().Format(time.RFC3339))

	if err := rdb.Set(ctx, "stats:24h", statsJSON, time.Hour).Err(); err != nil {
		log.Errorf("Failed to set Redis key: %v", err)
		// 记录失败
		pgPool.Exec(ctx, `
			UPDATE job_logs SET status = 'failed', completed_at = NOW(), error_message = $1
			WHERE job_name = 'update-stats-cache' AND status = 'running'
		`, err.Error())
		return
	}

	// 记录成功
	_, err = pgPool.Exec(ctx, `
		UPDATE job_logs SET status = 'success', completed_at = NOW(), records_processed = $1
		WHERE job_name = 'update-stats-cache' AND status = 'running'
	`, stats.Total)

	if err != nil {
		log.Errorf("Failed to log job completion: %v", err)
	}

	log.Infof("Updated stats cache: total=%d, positive=%d, negative=%d", 
		stats.Total, stats.Positive, stats.Negative)
}

// 生成日报
func generateDailyReport(pgPool *pgxpool.Pool) {
	log.Info("Running job: generate-daily-report")
	ctx := context.Background()

	// 记录任务开始
	_, err := pgPool.Exec(ctx, `
		INSERT INTO job_logs (job_name, job_type, status, started_at)
		VALUES ('generate-daily-report', 'report', 'running', NOW())
	`)
	if err != nil {
		log.Errorf("Failed to log job start: %v", err)
	}

	yesterday := time.Now().AddDate(0, 0, -1).Format("2006-01-02")

	// 生成报告内容
	// 这里可以生成更详细的报告，包括趋势分析等
	reportContent := fmt.Sprintf("Daily Report for %s generated at %s", yesterday, time.Now().Format(time.RFC3339))

	log.Info(reportContent)

	// 记录成功
	_, err = pgPool.Exec(ctx, `
		UPDATE job_logs SET status = 'success', completed_at = NOW()
		WHERE job_name = 'generate-daily-report' AND status = 'running'
	`)

	if err != nil {
		log.Errorf("Failed to log job completion: %v", err)
	}

	log.Info("Daily report generated successfully")
}

// 清理旧数据
func cleanupOldData(pgPool *pgxpool.Pool) {
	log.Info("Running job: cleanup-old-data")
	ctx := context.Background()

	// 记录任务开始
	_, err := pgPool.Exec(ctx, `
		INSERT INTO job_logs (job_name, job_type, status, started_at)
		VALUES ('cleanup-old-data', 'maintenance', 'running', NOW())
	`)
	if err != nil {
		log.Errorf("Failed to log job start: %v", err)
	}

	// 获取保留天数
	var retentionDays int
	err = pgPool.QueryRow(ctx, `
		SELECT CAST(config_value AS INTEGER) FROM system_configs WHERE config_key = 'data_retention_days'
	`).Scan(&retentionDays)

	if err != nil {
		retentionDays = 90 // 默认90天
	}

	// 删除旧数据
	result, err := pgPool.Exec(ctx, `
		DELETE FROM raw_news WHERE collected_at < NOW() - INTERVAL '1 day' * $1
	`, retentionDays)

	if err != nil {
		log.Errorf("Failed to cleanup old data: %v", err)
		pgPool.Exec(ctx, `
			UPDATE job_logs SET status = 'failed', completed_at = NOW(), error_message = $1
			WHERE job_name = 'cleanup-old-data' AND status = 'running'
		`, err.Error())
		return
	}

	rowsAffected := result.RowsAffected()

	// 记录成功
	_, err = pgPool.Exec(ctx, `
		UPDATE job_logs SET status = 'success', completed_at = NOW(), records_processed = $1
		WHERE job_name = 'cleanup-old-data' AND status = 'running'
	`, rowsAffected)

	if err != nil {
		log.Errorf("Failed to log job completion: %v", err)
	}

	log.Infof("Cleaned up %d old records", rowsAffected)
}

// 触发数据采集
func triggerCollector(cfg Config) {
	log.Info("Running job: trigger-collector")

	// 调用 collector 的健康检查接口
	resp, err := http.Get(fmt.Sprintf("%s/health", cfg.CollectorAPIURL))
	if err != nil {
		log.Warnf("Collector health check failed: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Warnf("Collector returned non-OK status: %d", resp.StatusCode)
		return
	}

	log.Info("Collector health check passed")
}