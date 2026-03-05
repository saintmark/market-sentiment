#!/usr/bin/env python3
"""
测试 Kimi API 情感分析功能
"""
import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# 加载环境变量（覆盖系统环境变量）
load_dotenv(override=True)

# 测试新闻数据
test_news = [
    {
        "title": "苹果公司发布新款iPhone，股价大涨5%",
        "content": "苹果公司今日发布了最新款iPhone，市场反响热烈。分析师预计这将推动公司第四季度营收增长15%。受此消息影响，苹果股价今日大涨5%，创下历史新高。"
    },
    {
        "title": "某科技公司因数据泄露面临巨额罚款",
        "content": "某知名科技公司因用户数据泄露事件，被监管机构处以2亿美元罚款。该公司股价今日暴跌8%，投资者信心受到严重打击。"
    },
    {
        "title": "央行维持基准利率不变",
        "content": "央行今日宣布维持基准利率不变，符合市场预期。分析师认为这有助于稳定金融市场，为经济平稳运行提供支持。"
    }
]

async def test_sentiment_analysis():
    """测试情感分析"""
    api_key = os.getenv('KIMI_API_KEY')
    api_url = os.getenv('KIMI_API_URL', 'https://api.moonshot.cn/v1')
    model = os.getenv('NLP_MODEL', 'moonshot-v1-8k')
    
    if not api_key:
        print("❌ 错误: KIMI_API_KEY 未设置")
        return False
    
    print(f"✓ API Key 已加载: {api_key[:20]}...")
    print(f"✓ API URL: {api_url}")
    print(f"✓ Model: {model}")
    print("-" * 60)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i, news in enumerate(test_news, 1):
            print(f"\n【测试 {i}】{news['title'][:40]}...")
            
            prompt = f"""请分析以下财经新闻的情感倾向和市场影响：

标题: {news['title']}

内容: {news['content']}

请严格按照以下JSON格式返回分析结果：
{{
    "sentiment_score": <float between -1 and 1>,
    "sentiment_label": "<positive|neutral|negative>",
    "confidence": <float between 0 and 1>,
    "entities": [<list of mentioned companies, products, or key entities>],
    "keywords": [<list of key terms related to market sentiment>],
    "market_impact_score": <integer between 0 and 100>
}}

注意：只返回JSON，不要有任何其他文字说明。"""

            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的金融市场情感分析专家。"
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
                response = await client.post(
                    f"{api_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                content = data['choices'][0]['message']['content']
                
                # 解析 JSON
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    print(f"  情感分数: {result.get('sentiment_score')}")
                    print(f"  情感标签: {result.get('sentiment_label')}")
                    print(f"  置信度: {result.get('confidence')}")
                    print(f"  市场影响: {result.get('market_impact_score')}")
                    print(f"  关键词: {', '.join(result.get('keywords', [])[:5])}")
                    print(f"  ✓ 测试通过")
                else:
                    print(f"  ❌ 无法解析响应: {content[:100]}")
                    
            except Exception as e:
                print(f"  ❌ 错误: {e}")
                return False
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过！Kimi 情感分析 API 工作正常。")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Kimi 情感分析 API 测试")
    print("=" * 60)
    success = asyncio.run(test_sentiment_analysis())
    exit(0 if success else 1)
