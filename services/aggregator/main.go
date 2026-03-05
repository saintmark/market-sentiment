package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/IBM/sarama"
	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/sirupsen/logrus"
)

// 配置结构体
type Config struct {
	// Kafka 配置
	KafkaBrokers      string
	KafkaInputTopic   string
	KafkaConsumerGroup string

	// ClickHouse 配置
	ClickHouseHost     string
	ClickHousePort     string
	ClickHouseDB       string
	ClickHouseUser     string
	ClickHousePassword string

	// PostgreSQL 配置
	PostgresHost     string
	PostgresPort     string
	PostgresUser     string
	PostgresPassword string
	PostgresDB       string
}

// 情感分析消息结构体
type SentimentMessage struct {
	NewsID            int64     `json:"news_id"`
	SentimentScore    float64   `json:"sentiment_score"`
	SentimentLabel    string    `json:"sentiment_label"`
	Confidence        float64   `json:"confidence"`
	Entities          []string  `json:"entities"`
	Keywords          []string  `json:"keywords"`
	MarketImpactScore int       `json:"market_impact_score"`
	OriginalData      NewsData  `json:"original_data"`
	AnalyzedAt        time.Time `json:"analyzed_at"`
}

type NewsData struct {
	ID          int64     `json:"id"`
	Title       string    `json:"title"`
	Content     string    `json:"content"`
	URL         string    `json:"url"`
	SourceID    int       `json:"source_id"`
	SourceName  string    `json:"source_name"`
	PublishedAt time.Time `json:"published_at"`
}

// ClickHouse 表结构
type ClickHouseNews struct {
	NewsID            int64     `ch:"news_id"`
	Title             string    `ch:"title"`
	SourceName        string    `ch:"source_name"`
	SentimentScore    float64   `ch:"sentiment_score"`
	SentimentLabel    string    `ch:"sentiment_label"`
	Confidence        float64   `ch:"confidence"`
	MarketImpactScore int       `ch:"market_impact_score"`
	PublishedAt       time.Time `ch:"published_at"`
	AnalyzedAt        time.Time `ch:"analyzed_at"`
	Date              time.Time `ch:"date"`
}

var log = logrus.New()

// 从环境变量加载配置
func loadConfig() Config {
	return Config{
		KafkaBrokers:       getEnv("KAFKA_BROKERS", "localhost:9092"),
		KafkaInputTopic:    getEnv("KAFKA_INPUT_TOPIC", "sentiment-news"),
		KafkaConsumerGroup: getEnv("KAFKA_CONSUMER_GROUP", "aggregator-group"),
		ClickHouseHost:     getEnv("CLICKHOUSE_HOST", "localhost"),
		ClickHousePort:     getEnv("CLICKHOUSE_PORT", "8123"),
		ClickHouseDB:       getEnv("CLICKHOUSE_DB", "market_sentiment"),
		ClickHouseUser:     getEnv("CLICKHOUSE_USER", "default"),
		ClickHousePassword: getEnv("CLICKHOUSE_PASSWORD", "clickhouse"),
		PostgresHost:       getEnv("POSTGRES_HOST", "localhost"),
		PostgresPort:       getEnv("POSTGRES_PORT", "5432"),
		PostgresUser:       getEnv("POSTGRES_USER", "postgres"),
		PostgresPassword:   getEnv("POSTGRES_PASSWORD", "postgres"),
		PostgresDB:         getEnv("POSTGRES_DB", "market_sentiment"),
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
	log.Info("Aggregator service starting...")

	// 连接 ClickHouse
	chConn, err := connectClickHouse(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to ClickHouse: %v", err)
	}
	defer chConn.Close()
	log.Info("Connected to ClickHouse")

	// 确保表存在
	if err := ensureClickHouseTables(chConn); err != nil {
		log.Fatalf("Failed to ensure ClickHouse tables: %v", err)
	}

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

	// 设置上下文和信号处理
	ctx, cancel = context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// 启动消费者
	go runConsumer(ctx, cfg, chConn, pgPool)

	log.Info("Aggregator service is running...")

	// 等待退出信号
	<-sigChan
	log.Info("Shutting down aggregator service...")
	cancel()

	time.Sleep(1 * time.Second)
	log.Info("Aggregator service stopped")
}

// 连接 ClickHouse
func connectClickHouse(cfg Config) (driver.Conn, error) {
	conn, err := clickhouse.Open(&clickhouse.Options{
		Addr: []string{fmt.Sprintf("%s:%s", cfg.ClickHouseHost, cfg.ClickHousePort)},
		Auth: clickhouse.Auth{
			Database: cfg.ClickHouseDB,
			Username: cfg.ClickHouseUser,
			Password: cfg.ClickHousePassword,
		},
		Settings: clickhouse.Settings{
			"max_execution_time": 60,
		},
		Compression: &clickhouse.Compression{
			Method: clickhouse.CompressionLZ4,
		},
		DialTimeout:      time.Second * 10,
		MaxOpenConns:     10,
		MaxIdleConns:     5,
		ConnMaxLifetime:  time.Hour,
		ConnOpenStrategy: clickhouse.ConnOpenInOrder,
	})

	if err != nil {
		return nil, err
	}

	// 测试连接
	if err := conn.Ping(context.Background()); err != nil {
		return nil, err
	}

	return conn, nil
}

// 确保 ClickHouse 表存在
func ensureClickHouseTables(conn driver.Conn) error {
	ctx := context.Background()

	// 创建新闻数据表
	err := conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS news_sentiment (
			news_id Int64,
			title String,
			source_name String,
			sentiment_score Float64,
			sentiment_label String,
			confidence Float64,
			market_impact_score Int32,
			published_at DateTime,
			analyzed_at DateTime,
			date Date
		) ENGINE = MergeTree()
		ORDER BY (date, news_id)
		PARTITION BY toYYYYMM(date)
	`)

	if err != nil {
		return fmt.Errorf("failed to create news_sentiment table: %w", err)
	}

	// 创建按小时聚合表
	err = conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS hourly_sentiment_summary (
			hour DateTime,
			news_count Int64,
			avg_sentiment Float64,
			positive_count Int64,
			neutral_count Int64,
			negative_count Int64,
			source_name String
		) ENGINE = SummingMergeTree()
		ORDER BY (hour, source_name)
	`)

	if err != nil {
		return fmt.Errorf("failed to create hourly_sentiment_summary table: %w", err)
	}

	return nil
}

// 运行 Kafka 消费者
func runConsumer(ctx context.Context, cfg Config, chConn driver.Conn, pgPool *pgxpool.Pool) {
	config := sarama.NewConfig()
	config.Consumer.Group.Rebalance.Strategy = sarama.BalanceStrategyRoundRobin
	config.Consumer.Offsets.Initial = sarama.OffsetOldest

	consumerGroup, err := sarama.NewConsumerGroup([]string{cfg.KafkaBrokers}, cfg.KafkaConsumerGroup, config)
	if err != nil {
		log.Fatalf("Failed to create consumer group: %v", err)
	}
	defer consumerGroup.Close()

	handler := &ConsumerHandler{
		chConn: chConn,
		pgPool: pgPool,
	}

	for {
		if err := consumerGroup.Consume(ctx, []string{cfg.KafkaInputTopic}, handler); err != nil {
			log.Errorf("Error from consumer: %v", err)
		}

		if ctx.Err() != nil {
			return
		}
	}
}

// 消费者处理器
type ConsumerHandler struct {
	chConn driver.Conn
	pgPool *pgxpool.Pool
}

func (h *ConsumerHandler) Setup(sarama.ConsumerGroupSession) error   { return nil }
func (h *ConsumerHandler) Cleanup(sarama.ConsumerGroupSession) error { return nil }

func (h *ConsumerHandler) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for message := range claim.Messages() {
		var sentimentMsg SentimentMessage
		if err := json.Unmarshal(message.Value, &sentimentMsg); err != nil {
			log.Errorf("Failed to unmarshal message: %v", err)
			session.MarkMessage(message, "")
			continue
		}

		// 写入 ClickHouse
		if err := h.writeToClickHouse(&sentimentMsg); err != nil {
			log.Errorf("Failed to write to ClickHouse: %v", err)
			continue
		}

		// 更新 PostgreSQL 统计
		if err := h.updateStats(&sentimentMsg); err != nil {
			log.Errorf("Failed to update stats: %v", err)
		}

		session.MarkMessage(message, "")
		log.Infof("Processed sentiment message: news_id=%d, label=%s", 
			sentimentMsg.NewsID, sentimentMsg.SentimentLabel)
	}

	return nil
}

// 写入 ClickHouse
func (h *ConsumerHandler) writeToClickHouse(msg *SentimentMessage) error {
	ctx := context.Background()

	data := ClickHouseNews{
		NewsID:            msg.NewsID,
		Title:             msg.OriginalData.Title,
		SourceName:        msg.OriginalData.SourceName,
		SentimentScore:    msg.SentimentScore,
		SentimentLabel:    msg.SentimentLabel,
		Confidence:        msg.Confidence,
		MarketImpactScore: msg.MarketImpactScore,
		PublishedAt:       msg.OriginalData.PublishedAt,
		AnalyzedAt:        msg.AnalyzedAt,
		Date:              msg.AnalyzedAt.Truncate(24 * time.Hour),
	}

	batch, err := h.chConn.PrepareBatch(ctx, "INSERT INTO news_sentiment")
	if err != nil {
		return fmt.Errorf("failed to prepare batch: %w", err)
	}

	if err := batch.AppendStruct(&data); err != nil {
		return fmt.Errorf("failed to append to batch: %w", err)
	}

	if err := batch.Send(); err != nil {
		return fmt.Errorf("failed to send batch: %w", err)
	}

	return nil
}

// 更新 PostgreSQL 统计
func (h *ConsumerHandler) updateStats(msg *SentimentMessage) error {
	ctx := context.Background()

	// 获取日期
	statDate := msg.AnalyzedAt.Truncate(24 * time.Hour)

	// 更新或插入日统计
	_, err := h.pgPool.Exec(ctx, `
		INSERT INTO daily_sentiment_stats 
		(sector_id, stat_date, news_count, avg_sentiment, positive_count, neutral_count, negative_count)
		VALUES (NULL, $1, 1, $2, 
			CASE WHEN $3 = 'positive' THEN 1 ELSE 0 END,
			CASE WHEN $3 = 'neutral' THEN 1 ELSE 0 END,
			CASE WHEN $3 = 'negative' THEN 1 ELSE 0 END)
		ON CONFLICT (sector_id, stat_date) DO UPDATE SET
			news_count = daily_sentiment_stats.news_count + 1,
			avg_sentiment = (daily_sentiment_stats.avg_sentiment * daily_sentiment_stats.news_count + $2) / (daily_sentiment_stats.news_count + 1),
			positive_count = daily_sentiment_stats.positive_count + CASE WHEN $3 = 'positive' THEN 1 ELSE 0 END,
			neutral_count = daily_sentiment_stats.neutral_count + CASE WHEN $3 = 'neutral' THEN 1 ELSE 0 END,
			negative_count = daily_sentiment_stats.negative_count + CASE WHEN $3 = 'negative' THEN 1 ELSE 0 END
	`, statDate, msg.SentimentScore, msg.SentimentLabel)

	if err != nil {
		return fmt.Errorf("failed to update daily stats: %w", err)
	}

	return nil
}