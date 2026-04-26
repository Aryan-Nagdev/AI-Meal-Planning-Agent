import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Flame, BookOpen, Layers, X } from 'lucide-react';
import { getRecipe, getSimilar } from '../utils/api';
import './MealPlanView.css';

const SLOT_ICONS  = { Breakfast:'🌅', Lunch:'☀️', Dinner:'🌙' };
const SLOT_COLORS = { Breakfast:'#f59e0b', Lunch:'#10b981', Dinner:'#6366f1' };

export default function MealPlanView({ plan }) {
  const [expanded, setExpanded] = useState({ 1: true });
  const toggle = (day) => setExpanded(p => ({ ...p, [day]: !p[day] }));

  return (
    <div className="plan-view">
      {plan.map(d => (
        <div key={d.day} className="day-card">
          <div className="day-header" onClick={() => toggle(d.day)}>
            <div className="day-title">
              <span className="day-badge">Day {d.day}</span>
              <span className="day-stats">
                <Flame size={13} color="#f87171" /> {d.day_calories_kcal} kcal
                &nbsp;·&nbsp;
                <span style={{color:'#4ade80'}}>₹{d.day_cost_inr}</span>
              </span>
            </div>
            {expanded[d.day] ? <ChevronUp size={18}/> : <ChevronDown size={18}/>}
          </div>
          {expanded[d.day] && (
            <div className="day-meals">
              {Object.entries(d.meals).map(([slot, meal]) => (
                <MealCard key={slot} slot={slot} meal={meal} />
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function MealCard({ slot, meal }) {
  const [open,        setOpen]        = useState(false);
  const [recipeData,  setRecipeData]  = useState(null);
  const [similarData, setSimilarData] = useState(null);
  const [recipeLoading, setRecLoading]= useState(false);
  const [simLoading,  setSimLoading]  = useState(false);
  const color = SLOT_COLORS[slot];

  const loadRecipe = async (e) => {
    e.stopPropagation();
    if (recipeData) { setRecipeData(null); return; }
    setRecLoading(true);
    try {
      const r = await getRecipe(meal.meal_name, meal.ingredients);
      setRecipeData(r);
    } catch { setRecipeData({steps:['Could not load recipe.'], source:'error'}); }
    finally  { setRecLoading(false); }
  };

  const loadSimilar = async (e) => {
    e.stopPropagation();
    if (similarData) { setSimilarData(null); return; }
    setSimLoading(true);
    try {
      const r = await getSimilar(meal.meal_name, 4);
      setSimilarData(r.similar);
    } catch { setSimilarData([]); }
    finally  { setSimLoading(false); }
  };

  return (
    <div className="meal-card" style={{borderLeftColor: color}}>
      {/* ── header row ── */}
      <div className="meal-header" onClick={() => setOpen(v => !v)}>
        <div className="meal-slot-info">
          <span className="slot-icon">{SLOT_ICONS[slot]}</span>
          <div>
            <div className="slot-name" style={{color}}>{slot}</div>
            <div className="meal-name">{meal.meal_name}</div>
          </div>
        </div>
        <div className="meal-quick-stats">
          <span className="qs"><Flame size={11} color="#f87171"/> {meal.estimated_calories_kcal} kcal</span>
          <span className="qs" style={{color:'#4ade80'}}>₹{meal.cost_inr}</span>
          {meal.is_favorite && <span className="badge fav-badge">⭐ Fav</span>}
          {meal.is_quick    && <span className="badge quick-badge">⚡</span>}
          {meal.is_healthy  && <span className="badge health-badge">✅</span>}
        </div>
        <span className="expand-icon">{open ? '▲' : '▼'}</span>
      </div>

      {/* ── detail panel ── */}
      {open && (
        <div className="meal-details">
          <div className="macros-row">
            <MacroBar label="Protein" value={meal.protein} color="#3b82f6"/>
            <MacroBar label="Fat"     value={meal.fat}     color="#f59e0b"/>
            <MacroBar label="Carbs"   value={meal.carbs}   color="#10b981"/>
          </div>
          <div className="ingredients-section">
            <div className="ing-label">🧂 Ingredients</div>
            <div className="ing-list">
              {meal.ingredients.map((ing,i) => (
                <span key={i} className="ing-chip">{ing}</span>
              ))}
            </div>
          </div>
          <div className="score-row">
            <span>Agent Score: <strong style={{color:'#818cf8'}}>{(meal.score*100).toFixed(1)}</strong>/100</span>
            <span>Prep: <strong>{meal.is_quick ? '⚡ Quick' : '🍳 Normal'}</strong></span>
          </div>

          {/* ── action buttons ── */}
          <div className="action-row">
            <button className={`action-btn ${recipeData ? 'active-btn' : ''}`}
              onClick={loadRecipe} disabled={recipeLoading}>
              <BookOpen size={13}/>
              {recipeLoading ? 'Loading…' : recipeData ? 'Hide Recipe' : 'View Recipe'}
            </button>
            <button className={`action-btn ${similarData ? 'active-btn' : ''}`}
              onClick={loadSimilar} disabled={simLoading}>
              <Layers size={13}/>
              {simLoading ? 'Loading…' : similarData ? 'Hide Similar' : 'Similar Meals'}
            </button>
          </div>

          {/* ── recipe panel ── */}
          {recipeData && (
            <div className="recipe-panel">
              <div className="panel-header">
                📋 Recipe
                <span className="panel-source">{recipeData.source === 'dataset' ? '✅ From dataset' : '🤖 Agent-generated'}</span>
              </div>
              <ol className="recipe-steps">
                {recipeData.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </div>
          )}

          {/* ── similar meals panel ── */}
          {similarData && (
            <div className="similar-panel">
              <div className="panel-header">🔍 Similar Meals (ingredient match)</div>
              {similarData.length === 0
                ? <p style={{color:'#64748b',fontSize:'0.8rem'}}>No similar meals found.</p>
                : similarData.map((s,i) => (
                  <div key={i} className="similar-item">
                    <div>
                      <div className="similar-name">{s.meal_name}</div>
                      <div className="similar-meta">{s.diet_type} · ₹{s.cost_inr}</div>
                    </div>
                    <div className="sim-score">{Math.round(s.similarity*100)}% match</div>
                  </div>
                ))
              }
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MacroBar({ label, value, color }) {
  const pct = Math.min(100, Math.round(value * 100));
  return (
    <div className="macro-bar">
      <div className="macro-label">{label}</div>
      <div className="macro-track">
        <div className="macro-fill" style={{width:`${pct}%`, background:color}}/>
      </div>
      <div className="macro-val">{pct}%</div>
    </div>
  );
}