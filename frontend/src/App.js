import React, { useState, useEffect } from 'react';
import PlannerForm from './components/PlannerForm';
import MealPlanView from './components/MealPlanView';
import GroceryList from './components/GroceryList';
import StatsBar from './components/StatsBar';
import Summary from './components/Summary';
import { getStats } from './utils/api';
import { ChefHat, RefreshCw } from 'lucide-react';
import './App.css';

export default function App() {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('plan');
  const [stats, setStats] = useState(null);
  const [formData, setFormData] = useState(null);

  useEffect(() => {
    getStats().then(setStats).catch(() => {});
  }, []);

  const tabs = [
    { id: 'plan', label: '📅 Meal Plan' },
    { id: 'grocery', label: '🛒 Grocery List' },
  ];

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <ChefHat size={28} color="#3b82f6" />
            <div>
              <h1>AI Meal Planner</h1>
              <p>Personalized nutrition powered by AI</p>
            </div>
          </div>
          {stats && <StatsBar stats={stats} />}
        </div>
      </header>

      <main className="main">
        {/* Left: Form */}
        <aside className="sidebar">
          <PlannerForm
            onPlan={(p, fd) => { setPlan(p); setFormData(fd); setActiveTab('plan'); }}
            loading={loading}
            setLoading={setLoading}
            existingFormData={formData}
          />
        </aside>

        {/* Right: Results */}
        <section className="content">
          {!plan && !loading && (
            <div className="empty-state">
              <ChefHat size={64} color="#334155" />
              <h2>Ready to plan your meals?</h2>
              <p>Fill in your preferences on the left and click <strong>Generate Plan</strong> to get started.</p>
            </div>
          )}

          {loading && (
            <div className="loading-state">
              <RefreshCw size={48} className="spin" color="#3b82f6" />
              <h2>AI is crafting your meal plan…</h2>
              <p>Analysing 500+ meals, optimising for your budget and health.</p>
            </div>
          )}

          {plan && !loading && (
            <>
              <Summary summary={plan.summary} />
              <div className="tabs">
                {tabs.map(t => (
                  <button
                    key={t.id}
                    className={`tab-btn ${activeTab === t.id ? 'active' : ''}`}
                    onClick={() => setActiveTab(t.id)}
                  >{t.label}</button>
                ))}
              </div>

              {activeTab === 'plan' && <MealPlanView plan={plan.plan} />}
              {activeTab === 'grocery' && <GroceryList grocery={plan.grocery_list} />}
            </>
          )}
        </section>
      </main>
    </div>
  );
}