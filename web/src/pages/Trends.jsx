import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './Trends.css';

function Trends() {
  const [trends, setTrends] = useState([]);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTrends();
  }, [days]);

  const fetchTrends = () => {
    setLoading(true);
    fetch(`/api/v1/trends?days=${days}`)
      .then(res => res.json())
      .then(data => {
        setTrends(data.trends || []);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch trends:', err);
        setLoading(false);
      });
  };

  return (
    <div className="trends-page">
      <div className="trends-header">
        <h2>情感趋势</h2>
        <div className="days-selector">
          <button 
            className={days === 7 ? 'active' : ''} 
            onClick={() => setDays(7)}
          >
            7天
          </button>
          <button 
            className={days === 30 ? 'active' : ''} 
            onClick={() => setDays(30)}
          >
            30天
          </button>
          <button 
            className={days === 90 ? 'active' : ''} 
            onClick={() => setDays(90)}
          >
            90天
          </button>
        </div>
      </div>
      
      {loading ? (
        <div className="loading">加载中...</div>
      ) : (
        <div className="chart-container">
          <h3>平均情感分数趋势</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="date" 
                tickFormatter={(date) => new Date(date).toLocaleDateString()}
              />
              <YAxis domain={[-1, 1]} />
              <Tooltip 
                labelFormatter={(date) => new Date(date).toLocaleDateString()}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="avg_sentiment" 
                name="平均情感分数" 
                stroke="#8884d8" 
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>

          <h3>新闻数量趋势</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="date" 
                tickFormatter={(date) => new Date(date).toLocaleDateString()}
              />
              <YAxis />
              <Tooltip 
                labelFormatter={(date) => new Date(date).toLocaleDateString()}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="positive" 
                name="正面" 
                stroke="#52c41a" 
                strokeWidth={2}
              />
              <Line 
                type="monotone" 
                dataKey="neutral" 
                name="中性" 
                stroke="#faad14" 
                strokeWidth={2}
              />
              <Line 
                type="monotone" 
                dataKey="negative" 
                name="负面" 
                stroke="#f5222d" 
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default Trends;