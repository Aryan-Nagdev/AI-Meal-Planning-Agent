import React from 'react';
import './StatsBar.css';

export default function StatsBar({ stats }) {
  return (
    <div className="stats-bar">
      <StatItem label="Total Meals" value={stats.total_meals} />
      <StatItem label="🥦 Veg" value={stats.veg_meals} />
      <StatItem label="🍗 Non-veg" value={stats.non_veg_meals} />
      <StatItem label="✅ Healthy" value={stats.healthy_meals} />
      <StatItem label="Cost Range" value={`₹${stats.cost_range?.min}–₹${stats.cost_range?.max}`} />
    </div>
  );
}

function StatItem({ label, value }) {
  return (
    <div className="stat-item">
      <span className="stat-val">{value}</span>
      <span className="stat-lbl">{label}</span>
    </div>
  );
}
