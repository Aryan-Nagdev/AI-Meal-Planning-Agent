from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
from agent import MealPlannerAgent

app = FastAPI(title="AI Meal Planner — Agentic API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = MealPlannerAgent()


class PlanRequest(BaseModel):
    budget:          float
    diet_type:       str
    num_days:        int
    disease:         Optional[str] = None
    cook_time:       Optional[str] = None       # "quick" | "normal" | None
    weight_goal:     Optional[str] = None       # "loss" | "gain" | "maintain"
    favorite_meal:   Optional[str] = None
    ingredient_pref: Optional[str] = None       # NEW – e.g. "chicken"


class RecipeRequest(BaseModel):
    meal_name:   str
    ingredients: list[str]


class SimilarRequest(BaseModel):
    meal_name: str
    top_n:     int = 5


class ChatRequest(BaseModel):
    message:      str
    plan_context: Optional[dict] = None


@app.get("/")
def root():
    return {"status": "AI Meal Planner Agentic API v2.0 running"}


@app.post("/api/plan")
def generate_plan(req: PlanRequest):
    try:
        return agent.generate_plan(
            budget=req.budget,
            diet_type=req.diet_type,
            num_days=req.num_days,
            disease=req.disease,
            cook_time=req.cook_time,
            weight_goal=req.weight_goal,
            favorite_meal=req.favorite_meal,
            ingredient_pref=req.ingredient_pref,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/replan")
def replan(req: PlanRequest):
    try:
        return agent.generate_plan(
            budget=req.budget,
            diet_type=req.diet_type,
            num_days=req.num_days,
            disease=req.disease,
            cook_time=req.cook_time,
            weight_goal=req.weight_goal,
            favorite_meal=req.favorite_meal,
            ingredient_pref=req.ingredient_pref,
            seed=None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recipe")
def get_recipe(req: RecipeRequest):
    """Generate or retrieve contextual recipe steps for a meal."""
    try:
        return agent.get_recipe(req.meal_name, req.ingredients)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/similar")
def get_similar(req: SimilarRequest):
    """Find meals similar to a given meal via ingredient Jaccard similarity."""
    try:
        return {"similar": agent.get_similar_meals(req.meal_name, req.top_n)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        return {"response": agent.chat(req.message, req.plan_context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def get_stats():
    return agent.get_dataset_stats()


@app.get("/api/diseases")
def get_diseases():
    return {"diseases": ["None", "Diabetes", "Hypertension", "Obesity",
                         "Heart Disease", "High Cholesterol"]}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)