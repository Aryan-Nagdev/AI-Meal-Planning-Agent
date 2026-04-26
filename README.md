# 🍽️ AI Meal Planner Agent

A full-stack AI-powered meal planning system with a FastAPI backend and React frontend.
Uses heuristic scoring + Claude AI to generate personalized meal plans, grocery lists,
and nutritional insights based on budget, diet type, and health conditions.

---

## 📁 Project Structure

```
meal_planner/
├── backend/
│   ├── main.py             ← FastAPI app & routes
│   ├── agent.py            ← Core AI scoring/planning logic
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.js / App.css
│   │   ├── index.js / index.css
│   │   ├── utils/
│   │   │   └── api.js
│   │   └── components/
│   │       ├── PlannerForm.js/.css
│   │       ├── MealPlanView.js/.css
│   │       ├── GroceryList.js/.css
│   │       ├── ChatBot.js/.css
│   │       ├── Summary.js/.css
│   │       └── StatsBar.js/.css
│   └── package.json
└── data/
    ├── healthy_meal_plans_updated.csv
    └── calories.csv
```

---

## ⚙️ Prerequisites

- Python 3.10+
- Node.js 18+
- npm 9+
- An Anthropic API key (for AI chat + AI summaries — the planner works without it too)

---

## 🚀 Setup & Run

### 1. Clone / Extract the project

```bash
# If you downloaded a zip:
unzip meal_planner.zip && cd meal_planner
```

### 2. Place Dataset Files

Make sure these two files are in the `data/` folder:
```
data/healthy_meal_plans_updated.csv
data/calories.csv
```

---

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key (optional but recommended)
cp .env.example .env
# Open .env and set:  ANTHROPIC_API_KEY=sk-ant-xxxxx

# Start the backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be live at: http://localhost:8000
API docs at: http://localhost:8000/docs

---

### 4. Frontend Setup

Open a **new terminal**:

```bash
cd frontend

# Install Node dependencies
npm install

# Start the React dev server
npm start
```

Frontend will open at: http://localhost:3000

---

## 🔑 Environment Variables

| Variable            | Required | Description                            |
|---------------------|----------|----------------------------------------|
| ANTHROPIC_API_KEY   | No*      | Enables AI chat + AI plan summaries    |

*Without the API key the planner still fully works — AI chat and summaries are disabled.

---

## 🌟 Features

### Meal Planning
- Heuristic AI scoring (cost 40% + nutrition 35% + health 15% + calories 10%)
- No meal repetition across the plan
- Weighted random sampling proportional to AI score

### Health-Aware Filtering
| Condition       | What it does                                          |
|-----------------|-------------------------------------------------------|
| Diabetes        | Avoids sugar/refined carbs; prefers high-protein      |
| Hypertension    | Avoids sodium/processed; low-fat preference           |
| Obesity         | Caps calories; avoids fried/butter                    |
| Heart Disease   | Avoids saturated fats and processed meats             |
| High Cholesterol| Avoids egg yolk, cream, fried foods                   |

### Grocery List
- Aggregates all ingredients from the plan
- Removes duplicates, shows frequency (how many meals need it)
- Interactive check-off with progress bar

### AI Chat (requires API key)
- Ask questions about your plan
- Get meal substitution suggestions
- Nutritional advice based on your health condition

### Re-planning
- Click "Re-plan" to get a fresh randomized selection
- Change any parameter and regenerate instantly

---

## 📡 API Endpoints

| Method | Endpoint        | Description                        |
|--------|-----------------|------------------------------------|
| GET    | /               | Health check                       |
| POST   | /api/plan       | Generate a new meal plan           |
| POST   | /api/replan     | Re-generate (fresh random seed)    |
| POST   | /api/chat       | AI chat with plan context          |
| GET    | /api/stats      | Dataset statistics                 |
| GET    | /api/diseases   | List of supported health conditions|

### Example POST /api/plan

```json
{
  "budget": 3000,
  "diet_type": "Veg",
  "num_days": 7,
  "disease": "Diabetes"
}
```

---

## 🧠 AI Scoring Formula

```
score = 0.40 × cost_score
      + 0.35 × nutrition_score
      + 0.15 × health_score
      + 0.10 × calorie_score

cost_score      = max(0, 1 - meal_cost / budget_per_meal)
nutrition_score = 0.6 × preferred_macro + 0.4 × (1 - penalised_macro)
health_score    = is_healthy flag (0 or 1)
calorie_score   = 1 - |normalised_calories - 0.45|

# Disease modifier: multiply by 0.05 if banned ingredient found
```

---

## 🛠️ Troubleshooting

**Backend won't start?**
- Ensure Python 3.10+ and all pip packages installed
- Check `data/` folder has both CSVs

**Frontend shows "Something went wrong"?**
- Make sure backend is running on port 8000
- Check browser console for CORS errors
- Verify proxy in package.json points to `http://localhost:8000`

**AI chat not working?**
- Set `ANTHROPIC_API_KEY` in `backend/.env`
- Restart the backend after adding the key

**No meals found?**
- Try increasing budget
- Try "Non-veg" diet type (more meals available)
- Remove the disease filter temporarily
