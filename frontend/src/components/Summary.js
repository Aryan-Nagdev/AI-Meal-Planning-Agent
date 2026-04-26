import React, { useState } from 'react';
import './Summary.css';

export default function Summary({ summary }) {
  const [showTrace, setShowTrace] = useState(false);
  if (!summary) return null;
  const within  = summary.within_budget;
  const trace   = summary.agent_trace || [];

  return (
    <div className={`summary-card ${within ? 'ok' : 'over'}`}>
      <div className="summary-grid">
        <Stat label="Total Cost"    value={`₹${summary.total_cost_inr?.toLocaleString()}`} />
        <Stat label="Budget"        value={`₹${summary.budget?.toLocaleString()}`} />
        <Stat label="Remaining"
          value={`₹${Math.abs(summary.budget_remaining_inr)?.toLocaleString()}`}
          sub={within ? '✅ Saved' : '⚠️ Over'} />
        <Stat label="Avg/Day"       value={`₹${summary.avg_daily_cost_inr}`} />
        <Stat label="Total Cal"     value={`${summary.total_calories_kcal?.toLocaleString()} kcal`} />
        <Stat label="Avg Cal/Day"   value={`${summary.avg_daily_calories_kcal?.toLocaleString()} kcal`} />
      </div>

      {summary.ai_summary && (
        <div className="ai-summary">
          <span className="ai-badge">🤖 Agent Summary</span>
          <p>{summary.ai_summary}</p>
        </div>
      )}

      {summary.disease_note && (
        <div className="disease-info">⚕️ {summary.disease_note}</div>
      )}

      {/* Agent Reasoning Trace */}
      {trace.length > 0 && (
        <div className="trace-section">
          <button className="trace-toggle" onClick={() => setShowTrace(v => !v)}>
            🧠 Agent Reasoning Trace
            <span className="trace-count">{trace.length} steps</span>
            <span>{showTrace ? '▲' : '▼'}</span>
          </button>
          {showTrace && (
            <div className="trace-log">
              {trace.map((t, i) => {
                const color = t.includes('ANALYZE') ? '#818cf8'
                  : t.includes('PLAN')    ? '#60a5fa'
                  : t.includes('SCORE')   ? '#34d399'
                  : t.includes('SELECT')  ? '#fbbf24'
                  : t.includes('REPLAN')  ? '#f87171'
                  : t.includes('VALIDATE')? '#a78bfa'
                  : t.includes('REFLECT') ? '#6ee7b7'
                  : '#94a3b8';
                return (
                  <div key={i} className="trace-line" style={{borderLeftColor: color}}>
                    <span className="trace-text">{t}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}