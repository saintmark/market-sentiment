import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import News from './pages/News';
import Trends from './pages/Trends';
import Sectors from './pages/Sectors';
import './App.css';

function App() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 获取统计数据
    fetch('/api/v1/sentiment/stats?period=24h')
      .then(res => res.json())
      .then(data => {
        setStats(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch stats:', err);
        setLoading(false);
      });
  }, []);

  return (
    <Router>
      <div className="app">
        <header className="header">
          <div className="header-content">
            <h1>市场情绪分析系统</h1>
            <nav className="nav">
              <Link to="/" className="nav-link">仪表盘</Link>
              <Link to="/news" className="nav-link">新闻</Link>
              <Link to="/trends" className="nav-link">趋势</Link>
              <Link to="/sectors" className="nav-link">行业</Link>
            </nav>
          </div>
        </header>

        <main className="main">
          <Routes>
            <Route path="/" element={<Dashboard stats={stats} loading={loading} />} />
            <Route path="/news" element={<News />} />
            <Route path="/trends" element={<Trends />} />
            <Route path="/sectors" element={<Sectors />} />
          </Routes>
        </main>

        <footer className="footer">
          <p>市场情绪分析系统 © 2024</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;