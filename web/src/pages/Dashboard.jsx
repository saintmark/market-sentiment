import React from 'react';
import SentimentChart from '../components/SentimentChart';
import StatsCard from '../components/StatsCard';
import './Dashboard.css';

function Dashboard({ stats, loading }) {
  if (loading) {
    return <div className="loading">加载中...</div>;
  }

  return (
    <div className="dashboard">
      <h2>仪表盘</h2>
      
      <div className="stats-grid">
        <StatsCard 
          title="24小时新闻数" 
          value={stats?.news_count || 0} 
          icon="📰"
        />
        <StatsCard 
          title="平均情感分数" 
          value={stats?.avg_sentiment?.toFixed(2) || 0} 
          icon="📊"
          trend={stats?.avg_sentiment > 0 ? 'positive' : stats?.avg_sentiment < 0 ? 'negative' : 'neutral'}
        />
        <StatsCard 
          title="正面新闻" 
          value={`${stats?.positive_ratio?.toFixed(1) || 0}%`} 
          icon="😊"
          color="#52c41a"
        />
        <StatsCard 
          title="负面新闻" 
          value={`${stats?.negative_ratio?.toFixed(1) || 0}%`} 
          icon="😔"
          color="#f5222d"
        />
      </div>

      <div className="chart-section">
        <h3>情感分布</h3>
        <SentimentChart data={[
          { name: '正面', value: stats?.positive_count || 0, fill: '#52c41a' },
          { name: '中性', value: stats?.neutral_count || 0, fill: '#faad14' },
          { name: '负面', value: stats?.negative_count || 0, fill: '#f5222d' },
        ]} />
      </div>
    </div>
  );
}

export default Dashboard;