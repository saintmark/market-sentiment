# 📈 市场情绪分析系统

基于 AI 的实时市场情绪分析平台，支持多数据源采集、情感分析、数据聚合和可视化展示。

[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docs.docker.com/compose/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-red)](https://redis.io/)
[![Kafka](https://img.shields.io/badge/Kafka-3.5-black)](https://kafka.apache.org/)

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         数据采集层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  RSS 采集   │  │  API 采集   │  │      Web 爬虫           │ │
│  │  (36氪等)   │  │  (财新网等) │  │                         │ │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘ │
└─────────┼────────────────┼─────────────────────┼───────────────┘
          │                │                     │
          └────────────────┴─────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      消息队列 (Kafka)                            │
│              ┌─────────────────────────────┐                   │
│              │  Topics: raw-news,          │                   │
│              │          sentiment-news     │                   │
│              └─────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
│  数据处理   │  │  数据存储   │  │   聚合分析      │
│  (NLP)      │  │             │  │  (Aggregator)   │
│  • 情感分析 │  │ PostgreSQL  │  │                 │
│  • 实体提取 │  │ • 关系数据  │  │ ClickHouse      │
│  • 关键词   │  │ • 元数据    │  │ • 时序数据      │
└──────┬──────┘  └──────┬──────┘  └────────┬────────┘
       │                │                   │
       └────────────────┴───────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API 网关层                                │
│                    FastAPI + Uvicorn                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  REST API   │  │  WebSocket  │  │   数据查询接口          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       前端展示层                                 │
│                   React + Recharts                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  情感趋势   │  │  领域分析   │  │     实时监控            │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| **数据采集** | Go + gofeed | RSS/新闻采集 |
| **消息队列** | Apache Kafka | 数据流处理 |
| **NLP 分析** | Python + Moonshot API | 情感分析 |
| **数据库** | PostgreSQL | 关系数据存储 |
| **时序数据库** | ClickHouse | 聚合数据存储 |
| **缓存** | Redis | 缓存和消息队列 |
| **API 网关** | FastAPI | REST API |
| **前端** | React + Vite | 用户界面 |
| **部署** | Docker Compose | 容器编排 |

## 🚀 快速开始

### 环境要求

- Docker Engine 20.10+
- Docker Compose 2.0+
- 至少 4GB 可用内存

### 1. 克隆项目

```bash
git clone https://github.com/your-org/market-sentiment.git
cd market-sentiment
```

### 2. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，配置必要的参数
vim .env
```

**重要配置项：**

```bash
# AI API 密钥（必须配置）
KIMI_API_KEY=your-moonshot-api-key-here

# 数据库密码（生产环境请修改）
POSTGRES_PASSWORD=your-secure-password
CLICKHOUSE_PASSWORD=your-secure-password

# JWT 密钥（生产环境必须修改）
JWT_SECRET_KEY=your-random-secret-key
```

### 3. 启动系统

```bash
# 一键启动所有服务
./start.sh

# 或后台运行
./start.sh -d

# 开发模式（包含 Kafka UI）
./start.sh --dev
```

### 4. 访问系统

启动完成后，可以通过以下地址访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| Web 前端 | http://localhost:3000 | 主界面 |
| API 接口 | http://localhost:8000 | REST API |
| API 文档 | http://localhost:8000/docs | Swagger 文档 |
| Kafka UI | http://localhost:8080 | 消息队列管理 |

## 📋 使用指南

### 启动脚本

```bash
# 显示帮助
./start.sh --help

# 启动所有服务（后台）
./start.sh

# 前台运行，查看实时日志
./start.sh -f

# 强制重新构建镜像
./start.sh -b

# 清理数据并重新启动
./start.sh --clean

# 开发模式（包含 Kafka UI）
./start.sh --dev

# 仅启动数据库服务
./start.sh postgres redis
```

### 停止脚本

```bash
# 停止所有服务
./stop.sh

# 停止并删除容器
./stop.sh -r

# 停止并删除数据（⚠️ 危险操作）
./stop.sh -v

# 完全清理（容器+数据+镜像）
./stop.sh -a
```

### 日志查看

```bash
# 查看所有服务日志
./logs.sh

# 实时跟踪日志
./logs.sh -f

# 查看最近 200 行
./logs.sh -n 200

# 查看最近 30 分钟日志
./logs.sh -s 30m

# 查看特定服务日志
./logs.sh -f api nlp

# 列出所有服务
./logs.sh --services
```

## 🛠️ 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `POSTGRES_PASSWORD` | postgres123 | PostgreSQL 密码 |
| `CLICKHOUSE_PASSWORD` | clickhouse123 | ClickHouse 密码 |
| `KIMI_API_KEY` | - | Moonshot API 密钥 |
| `RSS_FEED_URL` | https://36kr.com/feed | 默认 RSS 源 |
| `COLLECT_INTERVAL` | 300 | 采集间隔（秒） |
| `API_PORT` | 8000 | API 服务端口 |
| `WEB_PORT` | 3000 | Web 服务端口 |

### 服务配置

编辑 `.env` 文件可以调整各项服务的配置：

```bash
# NLP 批处理大小
NLP_BATCH_SIZE=10

# 聚合窗口（小时）
AGGREGATION_WINDOW_HOURS=24

# 数据保留天数
RAW_DATA_RETENTION_DAYS=90
```

## 🔧 故障排查

### 常见问题

#### 1. 服务启动失败

```bash
# 检查 Docker 状态
docker info

# 查看服务日志
./logs.sh -f

# 检查容器状态
docker-compose ps
```

#### 2. 数据库连接失败

```bash
# 检查 PostgreSQL 是否健康
docker-compose ps postgres

# 查看 PostgreSQL 日志
./logs.sh -f postgres

# 手动连接测试
docker-compose exec postgres pg_isready -U postgres
```

#### 3. Kafka 连接问题

```bash
# 检查 Kafka 状态
./logs.sh -f kafka

# 测试 Kafka 连接
docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

#### 4. NLP 服务无法调用 API

```bash
# 检查 API 密钥配置
grep KIMI_API_KEY .env

# 查看 NLP 服务日志
./logs.sh -f nlp
```

### 重置数据

如果系统出现问题，可以重置数据：

```bash
# 警告：这将删除所有数据！
./start.sh --clean
```

### 性能优化

#### 调整资源限制

在 `docker-compose.yml` 中修改资源限制：

```yaml
deploy:
  resources:
    limits:
      memory: 1G
    reservations:
      memory: 256M
```

#### 数据库优化

```bash
# 进入 PostgreSQL
docker-compose exec postgres psql -U postgres -d market_sentiment

# 查看表大小
\dt+

# 查看索引
\di
```

## 📊 系统监控

### 查看服务健康状态

```bash
# 所有服务状态
docker-compose ps

# 资源使用
docker stats --no-stream

# 查看网络
docker network ls
docker network inspect market-sentiment_ms-network
```

### 日志分析

```bash
# 统计错误日志
./logs.sh -n 1000 | grep ERROR

# 查看特定时间段的日志
./logs.sh --since 1h
```

## 🏗️ 开发指南

### 本地开发

```bash
# 仅启动基础设施服务
./start.sh postgres redis kafka clickhouse

# 在本地运行 API 服务
cd api
pip install -r requirements.txt
uvicorn main:app --reload

# 在本地运行前端
cd web
npm install
npm run dev
```

### 添加新的数据源

1. 在 `init.sql` 中添加新闻源配置：

```sql
INSERT INTO news_sources (name, url, type, is_active) 
VALUES ('新数据源', 'https://example.com/rss', 'rss', true);
```

2. 重启 collector 服务：

```bash
./stop.sh collector
./start.sh collector
```

### 自定义 NLP 模型

编辑 `services/nlp/main.py`，修改模型配置：

```python
# 使用不同的模型
NLP_MODEL = "moonshot-v1-32k"  # 或其他支持的模型
```

## 📁 项目结构

```
market-sentiment/
├── docker-compose.yml      # Docker Compose 配置
├── .env                    # 环境变量配置
├── .env.example            # 环境变量示例
├── init.sql                # 数据库初始化脚本
├── start.sh                # 启动脚本
├── stop.sh                 # 停止脚本
├── logs.sh                 # 日志查看脚本
├── README.md               # 项目说明
├── api/                    # API 网关服务
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── web/                    # Web 前端
│   ├── Dockerfile
│   ├── package.json
│   ├── index.html
│   ├── nginx.conf
│   └── src/
└── services/               # 微服务
    ├── collector/          # 数据采集服务
    │   ├── Dockerfile
    │   ├── main.go
    │   └── go.mod
    ├── nlp/                # NLP 分析服务
    │   ├── Dockerfile
    │   ├── main.py
    │   └── requirements.txt
    ├── aggregator/         # 数据聚合服务
    │   ├── Dockerfile
    │   ├── main.go
    │   └── go.mod
    └── scheduler/          # 定时任务服务
        ├── Dockerfile
        ├── main.go
        └── go.mod
```

## 🔒 安全说明

1. **生产环境必须修改默认密码**
   - PostgreSQL 密码
   - ClickHouse 密码
   - JWT 密钥

2. **保护 API 密钥**
   - 不要将 `.env` 文件提交到 Git
   - 使用 Docker Secrets 或环境变量注入

3. **网络隔离**
   - 默认使用 Docker 内部网络
   - 只暴露必要的端口到宿主机

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

[MIT](LICENSE) © 2024 Market Sentiment Team

## 🙏 致谢

- [Moonshot AI](https://www.moonshot.cn/) - 提供 NLP 能力
- [Apache Kafka](https://kafka.apache.org/) - 消息队列
- [ClickHouse](https://clickhouse.com/) - 时序数据库
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
