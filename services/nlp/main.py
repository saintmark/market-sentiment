"""
市场情绪分析 NLP 服务
从 Kafka 读取原始新闻，调用 Kimi API 进行情感分析，结果写回 Kafka
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

import httpx
import psycopg2
import psycopg2.extras
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from tenacity import retry, stop_after_attempt, wait_exponential

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """配置类"""
    # Kimi API 配置
    kimi_api_key: str
    kimi_api_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"
    
    # Kafka 配置
    kafka_brokers: str = "localhost:9092"
    kafka_input_topic: str = "raw-news"
    kafka_output_topic: str = "sentiment-news"
    kafka_group_id: str = "nlp-processor"
    
    # PostgreSQL 配置
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "market_sentiment"
    
    # 处理配置
    batch_size: int = 10
    max_retries: int = 3


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.conn = None
    
    def connect(self):
        """连接数据库"""
        self.conn = psycopg2.connect(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            user=self.config.postgres_user,
            password=self.config.postgres_password,
            dbname=self.config.postgres_db
        )
        self.conn.autocommit = True
        logger.info("Connected to PostgreSQL")
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from PostgreSQL")
    
    def save_sentiment_result(self, news_id: int, result: Dict[str, Any], raw_response: str):
        """保存情感分析结果到数据库"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO sentiment_results 
                (news_id, sentiment_score, sentiment_label, confidence, entities, keywords, 
                 market_impact_score, model_version, raw_response)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (news_id) DO UPDATE SET
                    sentiment_score = EXCLUDED.sentiment_score,
                    sentiment_label = EXCLUDED.sentiment_label,
                    confidence = EXCLUDED.confidence,
                    entities = EXCLUDED.entities,
                    keywords = EXCLUDED.keywords,
                    market_impact_score = EXCLUDED.market_impact_score,
                    analyzed_at = CURRENT_TIMESTAMP,
                    model_version = EXCLUDED.model_version,
                    raw_response = EXCLUDED.raw_response
            """, (
                news_id,
                result.get('sentiment_score'),
                result.get('sentiment_label'),
                result.get('confidence'),
                json.dumps(result.get('entities', [])),
                json.dumps(result.get('keywords', [])),
                result.get('market_impact_score'),
                result.get('model_version', self.config.kimi_model),
                raw_response
            ))
            logger.info(f"Saved sentiment result for news_id={news_id}")
        except Exception as e:
            logger.error(f"Failed to save sentiment result: {e}")
            raise
        finally:
            cursor.close()


class KimiClient:
    """Kimi API 客户端"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def analyze_sentiment(self, title: str, content: str) -> Dict[str, Any]:
        """
        调用 Kimi API 分析新闻情感
        
        返回:
            {
                "sentiment_score": float,  # -1 到 1
                "sentiment_label": str,    # positive, neutral, negative
                "confidence": float,       # 0 到 1
                "entities": list,          # 提取的实体
                "keywords": list,          # 关键词
                "market_impact_score": int # 0-100
            }
        """
        # 构建提示词
        prompt = self._build_prompt(title, content)
        
        headers = {
            "Authorization": f"Bearer {self.config.kimi_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.config.kimi_model,
            "messages": [
                {
                    "role": "system",
                    "content": """你是一个专业的金融市场情感分析专家。你的任务是分析新闻内容的情感倾向和市场影响。

请严格按照以下JSON格式返回分析结果：
{
    "sentiment_score": <float between -1 and 1>,
    "sentiment_label": "<positive|neutral|negative>",
    "confidence": <float between 0 and 1>,
    "entities": [<list of mentioned companies, products, or key entities>],
    "keywords": [<list of key terms related to market sentiment>],
    "market_impact_score": <integer between 0 and 100>
}

注意：
- sentiment_score: -1表示极度负面，0表示中性，1表示极度正面
- sentiment_label: 基于sentiment_score，negative(<-0.3), neutral(-0.3~0.3), positive(>0.3)
- market_impact_score: 评估该新闻对市场的潜在影响程度，0为无影响，100为重大影响
- 只返回JSON，不要有任何其他文字说明"""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        try:
            response = await self.client.post(
                f"{self.config.kimi_api_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            # 解析 JSON 响应
            result = self._parse_response(content)
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Kimi API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Kimi API error: {e}")
            raise
    
    def _build_prompt(self, title: str, content: str) -> str:
        """构建分析提示词"""
        # 截断内容以防过长
        max_content_len = 2000
        if len(content) > max_content_len:
            content = content[:max_content_len] + "..."
        
        return f"""请分析以下财经新闻的情感倾向和市场影响：

标题: {title}

内容: {content}

请返回JSON格式的分析结果。"""
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """解析 API 响应"""
        import re
        
        # 尝试提取 JSON
        try:
            # 查找 JSON 块
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ['sentiment_score', 'sentiment_label', 'confidence']
                for field in required_fields:
                    if field not in result:
                        result[field] = 0.0 if field != 'sentiment_label' else 'neutral'
                
                return result
            else:
                raise ValueError("No JSON found in response")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}, content: {content}")
            # 返回默认结果
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "confidence": 0.5,
                "entities": [],
                "keywords": [],
                "market_impact_score": 50
            }


class NLPService:
    """NLP 服务主类"""
    
    def __init__(self, config: Config):
        self.config = config
        self.db = DatabaseManager(config)
        self.kimi = KimiClient(config)
        self.consumer: Optional[KafkaConsumer] = None
        self.producer: Optional[KafkaProducer] = None
    
    def start(self):
        """启动服务"""
        logger.info("Starting NLP service...")
        
        # 连接数据库
        self.db.connect()
        
        # 初始化 Kafka 消费者
        self.consumer = KafkaConsumer(
            self.config.kafka_input_topic,
            bootstrap_servers=self.config.kafka_brokers,
            group_id=self.config.kafka_group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            max_poll_records=self.config.batch_size
        )
        
        # 初始化 Kafka 生产者
        self.producer = KafkaProducer(
            bootstrap_servers=self.config.kafka_brokers,
            value_serializer=lambda m: json.dumps(m, default=str).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8') if k else None
        )
        
        logger.info(f"Connected to Kafka. Listening on topic: {self.config.kafka_input_topic}")
    
    def stop(self):
        """停止服务"""
        logger.info("Stopping NLP service...")
        
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()
        
        asyncio.run(self.kimi.close())
        self.db.close()
        
        logger.info("NLP service stopped")
    
    async def process_message(self, message) -> Optional[Dict[str, Any]]:
        """处理单条消息"""
        try:
            news_data = message.value
            news_id = news_data.get('id')
            title = news_data.get('title', '')
            content = news_data.get('content', '')
            
            logger.info(f"Processing news: ID={news_id}, Title={title[:50]}...")
            
            # 调用 Kimi API 进行情感分析
            sentiment_result = await self.kimi.analyze_sentiment(title, content)
            
            # 添加元数据
            sentiment_result['news_id'] = news_id
            sentiment_result['original_data'] = news_data
            sentiment_result['analyzed_at'] = datetime.now().isoformat()
            
            # 保存到数据库
            raw_response = json.dumps(sentiment_result)
            self.db.save_sentiment_result(news_id, sentiment_result, raw_response)
            
            logger.info(f"Sentiment analysis completed: news_id={news_id}, "
                       f"label={sentiment_result.get('sentiment_label')}, "
                       f"score={sentiment_result.get('sentiment_score')}")
            
            return sentiment_result
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            return None
    
    def run(self):
        """运行主循环"""
        self.start()
        
        try:
            for message in self.consumer:
                # 异步处理消息
                result = asyncio.run(self.process_message(message))
                
                if result:
                    # 发送到输出 topic
                    news_id = result.get('news_id')
                    self.producer.send(
                        self.config.kafka_output_topic,
                        key=news_id,
                        value=result
                    )
                    logger.info(f"Sent result to topic: {self.config.kafka_output_topic}")
                    
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.stop()


def load_config_from_env() -> Config:
    """从环境变量加载配置"""
    return Config(
        kimi_api_key=os.getenv('KIMI_API_KEY', ''),
        kimi_api_url=os.getenv('KIMI_API_URL', 'https://api.moonshot.cn/v1'),
        kimi_model=os.getenv('NLP_MODEL', 'moonshot-v1-8k'),
        kafka_brokers=os.getenv('KAFKA_BROKERS', 'localhost:9092'),
        kafka_input_topic=os.getenv('KAFKA_INPUT_TOPIC', 'raw-news'),
        kafka_output_topic=os.getenv('KAFKA_OUTPUT_TOPIC', 'sentiment-news'),
        kafka_group_id=os.getenv('KAFKA_GROUP_ID', 'nlp-processor'),
        postgres_host=os.getenv('POSTGRES_HOST', 'localhost'),
        postgres_port=int(os.getenv('POSTGRES_PORT', '5432')),
        postgres_user=os.getenv('POSTGRES_USER', 'postgres'),
        postgres_password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
        postgres_db=os.getenv('POSTGRES_DB', 'market_sentiment'),
        batch_size=int(os.getenv('BATCH_SIZE', '10')),
        max_retries=int(os.getenv('MAX_RETRIES', '3'))
    )


def main():
    """主函数"""
    # 加载配置
    config = load_config_from_env()
    
    if not config.kimi_api_key:
        logger.error("KIMI_API_KEY environment variable is required")
        return
    
    # 创建并运行服务
    service = NLPService(config)
    service.run()


if __name__ == "__main__":
    main()