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
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/mmcdole/gofeed"
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

	// Kafka 配置
	KafkaBrokers string
	KafkaTopic   string

	// 采集配置
	RSSFeedURL      string
	CollectInterval int // 秒
}

// 新闻消息结构体 (用于发送到 Kafka)
type NewsMessage struct {
	ID          int64     `json:"id"`
	Title       string    `json:"title"`
	Content     string    `json:"content"`
	Summary     string    `json:"summary"`
	URL         string    `json:"url"`
	Author      string    `json:"author"`
	SourceID    int       `json:"source_id"`
	SourceName  string    `json:"source_name"`
	PublishedAt time.Time `json:"published_at"`
	CollectedAt time.Time `json:"collected_at"`
}

var (
	log = logrus.New()
	cfg Config
)

// 从环境变量加载配置
func loadConfig() Config {
	interval := 300 // 默认5分钟
	if val := os.Getenv("COLLECT_INTERVAL"); val != "" {
		if i, err := fmt.Sscanf(val, "%d", &interval); err == nil && i > 0 {
			// 成功解析
		}
	}

	return Config{
		PostgresHost:     getEnv("POSTGRES_HOST", "localhost"),
		PostgresPort:     getEnv("POSTGRES_PORT", "5432"),
		PostgresUser:     getEnv("POSTGRES_USER", "postgres"),
		PostgresPassword: getEnv("POSTGRES_PASSWORD", "postgres"),
		PostgresDB:       getEnv("POSTGRES_DB", "market_sentiment"),
		KafkaBrokers:     getEnv("KAFKA_BROKERS", "localhost:9092"),
		KafkaTopic:       getEnv("KAFKA_TOPIC", "raw-news"),
		RSSFeedURL:       getEnv("RSS_FEED_URL", "https://36kr.com/feed"),
		CollectInterval:  interval,
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

	// 加载配置
	cfg = loadConfig()
	log.Info("Collector service starting...")

	// 构建 PostgreSQL 连接字符串
	pgConnStr := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		cfg.PostgresUser, cfg.PostgresPassword, cfg.PostgresHost, cfg.PostgresPort, cfg.PostgresDB)

	// 连接 PostgreSQL
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	pool, err := pgxpool.New(ctx, pgConnStr)
	if err != nil {
		log.Fatalf("Failed to connect to PostgreSQL: %v", err)
	}
	defer pool.Close()

	// 测试连接
	if err := pool.Ping(ctx); err != nil {
		log.Fatalf("Failed to ping PostgreSQL: %v", err)
	}
	log.Info("Connected to PostgreSQL")

	// 创建 Kafka 生产者
	producer, err := createKafkaProducer()
	if err != nil {
		log.Fatalf("Failed to create Kafka producer: %v", err)
	}
	defer producer.Close()
	log.Info("Kafka producer created")

	// 创建上下文和取消函数
	ctx, cancel = context.WithCancel(context.Background())
	defer cancel()

	// 设置信号处理
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// 启动采集循环
	go runCollector(ctx, pool, producer)

	log.Info("Collector service is running...")

	// 等待退出信号
	<-sigChan
	log.Info("Shutting down collector service...")
	cancel()

	// 等待清理完成
	time.Sleep(1 * time.Second)
	log.Info("Collector service stopped")
}

// 创建 Kafka 生产者
func createKafkaProducer() (sarama.SyncProducer, error) {
	config := sarama.NewConfig()
	config.Producer.RequiredAcks = sarama.WaitForAll
	config.Producer.Retry.Max = 3
	config.Producer.Return.Successes = true

	producer, err := sarama.NewSyncProducer([]string{cfg.KafkaBrokers}, config)
	if err != nil {
		return nil, fmt.Errorf("failed to create producer: %w", err)
	}

	return producer, nil
}

// 运行采集器
func runCollector(ctx context.Context, pool *pgxpool.Pool, producer sarama.SyncProducer) {
	ticker := time.NewTicker(time.Duration(cfg.CollectInterval) * time.Second)
	defer ticker.Stop()

	// 立即执行一次
	collectAndProcess(ctx, pool, producer)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			collectAndProcess(ctx, pool, producer)
		}
	}
}

// 采集和处理 RSS 数据
func collectAndProcess(ctx context.Context, pool *pgxpool.Pool, producer sarama.SyncProducer) {
	log.Info("Starting RSS collection...")

	// 解析 RSS Feed
	fp := gofeed.NewParser()
	feed, err := fp.ParseURL(cfg.RSSFeedURL)
	if err != nil {
		log.Errorf("Failed to parse RSS feed: %v", err)
		return
	}

	log.Infof("Fetched %d items from RSS feed", len(feed.Items))

	// 获取 36氪的 source_id
	var sourceID int
	err = pool.QueryRow(ctx, 
		"SELECT id FROM news_sources WHERE name = $1", "36氪").Scan(&sourceID)
	if err != nil {
		log.Errorf("Failed to get source ID: %v", err)
		return
	}

	// 处理每个新闻项
	processedCount := 0
	for _, item := range feed.Items {
		if err := processNewsItem(ctx, pool, producer, item, sourceID); err != nil {
			log.Errorf("Failed to process news item: %v", err)
			continue
		}
		processedCount++
	}

	// 更新最后获取时间
	_, err = pool.Exec(ctx, 
		"UPDATE news_sources SET last_fetch_at = $1 WHERE id = $2",
		time.Now(), sourceID)
	if err != nil {
		log.Errorf("Failed to update last_fetch_at: %v", err)
	}

	log.Infof("Collection completed. Processed %d/%d items", processedCount, len(feed.Items))
}

// 处理单个新闻项
func processNewsItem(ctx context.Context, pool *pgxpool.Pool, producer sarama.SyncProducer, item *gofeed.Item, sourceID int) error {
	// 使用 GUID 或 Link 作为 external_id
	externalID := item.GUID
	if externalID == "" {
		externalID = item.Link
	}

	// 检查是否已存在
	var existingID int64
	err := pool.QueryRow(ctx,
		"SELECT id FROM raw_news WHERE source_id = $1 AND external_id = $2",
		sourceID, externalID).Scan(&existingID)

	if err == nil {
		// 已存在，跳过
		log.Debugf("News item already exists: %s", externalID)
		return nil
	}

	// 解析发布时间
	publishedAt := time.Now()
	if item.PublishedParsed != nil {
		publishedAt = *item.PublishedParsed
	}

	// 构建内容 (优先使用 Description，如果没有则使用 Content)
	content := item.Content
	if content == "" {
		content = item.Description
	}

	// 插入到数据库
	var newsID int64
	err = pool.QueryRow(ctx, `
		INSERT INTO raw_news (source_id, external_id, title, content, summary, url, author, published_at, raw_data)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT (source_id, external_id) DO NOTHING
		RETURNING id
	`, sourceID, externalID, item.Title, content, item.Description, item.Link, 
		getAuthor(item), publishedAt, marshalJSON(item)).Scan(&newsID)

	if err != nil {
		// 可能是重复键，忽略错误
		return nil
	}

	log.Infof("Inserted new news: ID=%d, Title=%s", newsID, truncateString(item.Title, 50))

	// 构建消息并发送到 Kafka
	newsMsg := NewsMessage{
		ID:          newsID,
		Title:       item.Title,
		Content:     content,
		Summary:     item.Description,
		URL:         item.Link,
		Author:      getAuthor(item),
		SourceID:    sourceID,
		SourceName:  "36氪",
		PublishedAt: publishedAt,
		CollectedAt: time.Now(),
	}

	// 序列化消息
	msgBytes, err := json.Marshal(newsMsg)
	if err != nil {
		return fmt.Errorf("failed to marshal news message: %w", err)
	}

	// 发送到 Kafka
	kafkaMsg := &sarama.ProducerMessage{
		Topic: cfg.KafkaTopic,
		Key:   sarama.StringEncoder(fmt.Sprintf("%d", newsID)),
		Value: sarama.ByteEncoder(msgBytes),
	}

	_, _, err = producer.SendMessage(kafkaMsg)
	if err != nil {
		return fmt.Errorf("failed to send message to Kafka: %w", err)
	}

	log.Infof("Sent message to Kafka: Topic=%s, ID=%d", cfg.KafkaTopic, newsID)
	return nil
}

// 获取作者信息
func getAuthor(item *gofeed.Item) string {
	if item.Author != nil && item.Author.Name != "" {
		return item.Author.Name
	}
	if len(item.Authors) > 0 && item.Authors[0].Name != "" {
		return item.Authors[0].Name
	}
	return ""
}

// JSON 序列化
func marshalJSON(v interface{}) []byte {
	b, _ := json.Marshal(v)
	return b
}

// 截断字符串
func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}