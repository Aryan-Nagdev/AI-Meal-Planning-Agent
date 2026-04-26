import React, { useState } from 'react';
import { generatePlan, replan } from '../utils/api';
import { Sparkles, RefreshCw, Info } from 'lucide-react';
import './PlannerForm.css';

const DISEASES = ['None','Diabetes','Hypertension','Obesity','Heart Disease','High Cholesterol'];

const WEIGHT_GOALS = [
  { value:'loss',     label:'📉 Weight Loss',  hint:'Low-cal meals prioritised' },
  { value:'maintain', label:'⚖️ Maintain',      hint:'Balanced calorie selection' },
  { value:'gain',     label:'📈 Weight Gain',   hint:'High-cal meals prioritised' },
];

const FAVORITE_MEALS = [
  { label:'🧀 Paneer Butter Masala', value:'Paneer Butter Masala' },
  { label:'🍗 Chicken Tikka Masala', value:'Chicken Tikka Masala' },
  { label:'🍚 Vegetable Biryani',    value:'Vegetable Biryani'    },
  { label:'🐟 Grilled Salmon',       value:'Grilled Salmon'       },
  { label:'🥗 Quinoa Salad',         value:'Quinoa Salad'         },
  { label:'🍳 Keto Omelette',        value:'Keto Omelette'        },
];

export default function PlannerForm({ onPlan, loading, setLoading, existingFormData }) {
  const [budget,      setBudget]      = useState(3000);
  const [dietType,    setDietType]    = useState('Veg');
  const [numDays,     setNumDays]     = useState(5);    // default 5, max 7
  const [disease,     setDisease]     = useState('None');
  const [cookTime,    setCookTime]    = useState('normal');
  const [weightGoal,  setWeightGoal]  = useState('maintain');
  const [favMeal,     setFavMeal]     = useState('');
  const [ingPref,     setIngPref]     = useState('');   // NEW
  const [error,       setError]       = useState('');

  const isReplanning = !!existingFormData;

  const buildPayload = () => ({
    budget:          parseFloat(budget),
    diet_type:       dietType,
    num_days:        Math.min(parseInt(numDays), 7),  // agent enforces MAX_DAYS=7
    disease:         disease === 'None' ? null : disease,
    cook_time:       cookTime === 'normal' ? null : cookTime,
    weight_goal:     weightGoal === 'maintain' ? null : weightGoal,
    favorite_meal:   favMeal || null,
    ingredient_pref: ingPref.trim() || null,
  });

  const handleSubmit = async (isReplan = false) => {
    setError('');
    setLoading(true);
    try {
      const payload = buildPayload();
      const result  = await (isReplan ? replan : generatePlan)(payload);
      onPlan(result, payload);
    } catch (e) {
      setError(e.response?.data?.detail || 'Something went wrong. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const toggleFav = (val) => setFavMeal(prev => prev === val ? '' : val);

  const clampedDays = Math.min(parseInt(numDays) || 1, 7);

  return (
    <div className="form-card">
      <div className="form-header">
        <Sparkles size={20} color="#3b82f6" />
        <h2>Plan My Meals</h2>
        <span className="agent-badge">🤖 Agentic</span>
      </div>

      {/* Budget */}
      <div className="form-group">
        <label>Total Budget (₹)</label>
        <input type="number" min="500" max="50000" step="100"
          value={budget} onChange={e => setBudget(e.target.value)} />
        <div className="hint">~₹{Math.round(budget / (clampedDays * 3))} per meal over {clampedDays} days</div>
      </div>

      {/* Diet Type */}
      <div className="form-group">
        <label>Diet Type</label>
        <div className="toggle-group">
          {['Veg','Non-veg'].map(d => (
            <button key={d}
              className={`toggle-btn ${dietType === d ? 'active' : ''}`}
              onClick={() => setDietType(d)}>
              {d === 'Veg' ? '🥦' : '🍗'} {d}
            </button>
          ))}
        </div>
      </div>

      {/* Days — capped at 7 */}
      <div className="form-group">
        <label>
          Number of Days: <strong>{clampedDays}</strong>
          <span className="cap-badge">max 7</span>
        </label>
        <input type="range" min="1" max="7" value={clampedDays}
          onChange={e => setNumDays(parseInt(e.target.value))} className="slider" />
        <div className="range-labels"><span>1 day</span><span>7 days</span></div>
      </div>

      {/* Cooking Time */}
      <div className="form-group">
        <label>Cooking Time</label>
        <div className="toggle-group">
          <button className={`toggle-btn ${cookTime==='quick'?'active':''}`}
            onClick={() => setCookTime('quick')}>⚡ Quick (&lt;30 min)</button>
          <button className={`toggle-btn ${cookTime==='normal'?'active':''}`}
            onClick={() => setCookTime('normal')}>🍳 Any Time</button>
        </div>
        {cookTime==='quick' && <div className="info-note">Agent prioritises fast-prep meals.</div>}
      </div>

      {/* Weight Goal */}
      <div className="form-group">
        <label>Weight Goal</label>
        <div className="weight-goal-group">
          {WEIGHT_GOALS.map(wg => (
            <button key={wg.value}
              className={`wg-btn ${weightGoal===wg.value?'active':''}`}
              onClick={() => setWeightGoal(wg.value)} title={wg.hint}>
              {wg.label}
            </button>
          ))}
        </div>
        <div className="hint">{WEIGHT_GOALS.find(w => w.value===weightGoal)?.hint}</div>
      </div>

      {/* Favourite Meal chips */}
      <div className="form-group">
        <label>
          Favourite Meal
          <span className="optional-tag">optional · similarity scored</span>
        </label>
        <div className="fav-chip-grid">
          {FAVORITE_MEALS.map(m => {
            const active = favMeal === m.value;
            return (
              <button key={m.value}
                className={`fav-chip ${active ? 'fav-active' : ''}`}
                onClick={() => toggleFav(m.value)}
                title={active ? 'Click to deselect' : 'Agent will score similar meals higher'}>
                {m.label}{active && ' ✕'}
              </button>
            );
          })}
        </div>
        {favMeal && (
          <div className="info-note">⭐ Agent will boost meals similar to <strong>{favMeal}</strong>.</div>
        )}
      </div>

      {/* ── NEW: Ingredient Preference ── */}
      <div className="form-group">
        <label>
          Ingredient Preference
          <span className="optional-tag">optional</span>
        </label>
        <div className="ing-pref-wrap">
          <input type="text"
            placeholder="e.g. chicken, spinach, lentil…"
            value={ingPref}
            onChange={e => setIngPref(e.target.value)}
            className="ing-pref-input"
          />
          {ingPref.trim() && (
            <button className="ing-clear" onClick={() => setIngPref('')} title="Clear">✕</button>
          )}
        </div>
        {ingPref.trim() && (
          <div className="info-note">
            🧂 Agent will semantically match meals containing <strong>{ingPref.trim()}</strong>.
          </div>
        )}
      </div>

      {/* Disease */}
      <div className="form-group">
        <label>Health Condition <span className="optional-tag">optional</span></label>
        <select value={disease} onChange={e => setDisease(e.target.value)}>
          {DISEASES.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        {disease !== 'None' && (
          <div className="disease-note">⚕️ Agent filters &amp; scores meals for {disease} management.</div>
        )}
      </div>

      {error && <div className="error-msg">⚠️ {error}</div>}

      <button className="submit-btn" onClick={() => handleSubmit(false)} disabled={loading}>
        {loading
          ? <><RefreshCw size={16} className="spin" /> Agent Planning…</>
          : <><Sparkles size={16} /> Generate Plan</>}
      </button>

      {isReplanning && (
        <button className="replan-btn" onClick={() => handleSubmit(true)} disabled={loading}>
          <RefreshCw size={16} /> Re-plan (fresh agent run)
        </button>
      )}
    </div>
  );
}