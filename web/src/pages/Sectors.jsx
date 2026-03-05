import React, { useState, useEffect } from 'react';
import './Sectors.css';

function Sectors() {
  const [sectors, setSectors] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSectors();
  }, []);

  const fetchSectors = () => {
    setLoading(true);
    fetch('/api/v1/sectors?period=24h')
      .then(res => res.json())
      .then(data => {
        setSectors(data || []);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch sectors:', err);
        setLoading(false);
      });
  };

  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'positive': return '📈';
      case 'negative': return '📉';
      default: return '➡️';
    }
  };

  const getSentimentColor = (score) => {
    if (score > 0.3) return '#52c41a';
    if (score < -0.3) return '#f5222d';
    return '#faad14';
  };

  return (
    <div className="sectors-page">
      <h2>行业分析</h2>
      
      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
        <div className="sectors-grid">
          {sectors.map(sector => (
            <div key={sector.sector_id} className="sector-card">
              <div className="sector-header">
                <h3>{sector.sector_name}</h3>
                <span className="trend-icon">{getTrendIcon(sector.sentiment_trend)}</span>
              </div>
              
              <div className="sector-stats">
                <div className="stat-item">
                  <span className="stat-label">新闻数</span>
                  <span className="stat-value">{sector.news_count}</span>
                </div>
                
                <div className="stat-item">
                  <span className="stat-label">情感分数</span>
                  <span 
                    className="stat-value sentiment-score"
                    style={{ color: getSentimentColor(sector.avg_sentiment) }}
                  >
                    {sector.avg_sentiment?.toFixed(2) || 0}
                  </span>
                </div>
              </div>

              <div className="sentiment-bar">
                <div 
                  className="sentiment-progress"
                  style={{
                    width: `${((sector.avg_sentiment + 1) / 2) * 100}%`,
                    backgroundColor: getSentimentColor(sector.avg_sentiment)
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Sectors;