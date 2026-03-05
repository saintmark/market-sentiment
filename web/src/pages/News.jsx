import React, { useState, useEffect } from 'react';
import './News.css';

function News() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  useEffect(() => {
    fetchNews();
  }, [page]);

  const fetchNews = () => {
    setLoading(true);
    fetch(`/api/v1/news?page=${page}&page_size=${pageSize}`)
      .then(res => res.json())
      .then(data => {
        setNews(data.items || []);
        setTotal(data.total || 0);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch news:', err);
        setLoading(false);
      });
  };

  const getSentimentClass = (label) => {
    switch (label) {
      case 'positive': return 'sentiment-positive';
      case 'negative': return 'sentiment-negative';
      default: return 'sentiment-neutral';
    }
  };

  const getSentimentText = (label) => {
    switch (label) {
      case 'positive': return '正面';
      case 'negative': return '负面';
      default: return '中性';
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="news-page">
      <h2>新闻列表</h2>
      
      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
        <>
          <div className="news-list">
            {news.map(item => (
              <div key={item.id} className="news-item">
                <div className="news-header">
                  <h3><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title}</a></h3>
                  <span className={`sentiment-badge ${getSentimentClass(item.sentiment_label)}`}>
                    {getSentimentText(item.sentiment_label)}
                  </span>
                </div>
                <p className="news-summary">{item.summary}</p>
                <div className="news-meta">
                  <span>{item.source_name}</span>
                  <span>{item.author}</span>
                  <span>{new Date(item.published_at).toLocaleString()}</span>
                  {item.confidence && (
                    <span>置信度: {(item.confidence * 100).toFixed(1)}%</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="pagination">
            <button 
              disabled={page === 1} 
              onClick={() => setPage(page - 1)}
            >
              上一页
            </button>
            <span>第 {page} / {totalPages} 页 (共 {total} 条)</span>
            <button 
              disabled={page >= totalPages} 
              onClick={() => setPage(page + 1)}
            >
              下一页
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default News;