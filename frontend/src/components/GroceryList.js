import React, { useState } from 'react';
import './GroceryList.css';

export default function GroceryList({ grocery }) {
  const [checked, setChecked] = useState({});
  const [search, setSearch] = useState('');

  const toggle = (ing) =>
    setChecked(prev => ({ ...prev, [ing]: !prev[ing] }));

  const clearChecked = () => setChecked({});

  const filtered = grocery.filter(g =>
    g.ingredient.toLowerCase().includes(search.toLowerCase())
  );

  const done = Object.values(checked).filter(Boolean).length;
  const pct = grocery.length ? Math.round((done / grocery.length) * 100) : 0;

  return (
    <div className="grocery-wrapper">
      <div className="grocery-header">
        <div>
          <h3>🛒 Grocery List</h3>
          <p className="grocery-sub">{grocery.length} unique ingredients · {done} checked</p>
        </div>
        <div className="grocery-actions">
          <button className="clear-btn" onClick={clearChecked}>Clear All</button>
        </div>
      </div>

      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="progress-label">{pct}% done</p>

      <input
        className="search-box"
        placeholder="🔍 Search ingredients…"
        value={search}
        onChange={e => setSearch(e.target.value)}
      />

      <div className="grocery-grid">
        {filtered.map(({ ingredient, frequency }) => (
          <div
            key={ingredient}
            className={`grocery-item ${checked[ingredient] ? 'checked' : ''}`}
            onClick={() => toggle(ingredient)}
          >
            <div className="grocery-check">{checked[ingredient] ? '✅' : '⬜'}</div>
            <div className="grocery-info">
              <span className="grocery-name">{ingredient}</span>
              <span className="grocery-freq">×{frequency}</span>
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <p style={{ color: '#64748b', textAlign: 'center', marginTop: 16 }}>No ingredients match your search.</p>
      )}
    </div>
  );
}
