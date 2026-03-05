import React from 'react';
import './StatsCard.css';

function StatsCard({ title, value, icon, trend, color }) {
  const getTrendIcon = () => {
    switch (trend) {
      case 'positive': return '↑';
      case 'negative': return '↓';
      default: return '→';
    }
  };

  const getTrendColor = () => {
    switch (trend) {
      case 'positive': return '#52c41a';
      case 'negative': return '#f5222d';
      default: return '#faad14';
    }
  };

  return (
    <div className="stats-card">
      <div className="stats-icon" style={{ color: color || '#667eea' }}>
        {icon}
      </div>
      <div className="stats-content">
        <div className="stats-title">{title}</div>
        <div className="stats-value-row">
          <span className="stats-value">{value}</span>
          {trend && (
            <span 
              className="stats-trend" 
              style={{ color: getTrendColor() }}
            >
              {getTrendIcon()}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default StatsCard;