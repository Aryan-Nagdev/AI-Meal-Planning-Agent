"""
AI Meal Planner — Agentic Core
==============================
Agent loop:
  1. Analyze()   – parse user intent, set goal weights
  2. Plan()      – build candidate pool with similarity + ingredient matching
  3. Score()     – multi-factor weighted scoring per meal
  4. Select()    – greedy optimal selection ensuring no repeats
  5. Validate()  – budget + constraint check; re-plan if violated
  6. Reflect()   – attach reasoning trace to response
"""

import os, re, random, textwrap
import pandas as pd
import numpy as np
from typing import Optional

# ── paths ────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── constants ─────────────────────────────────────────────────────────────────
SLOTS       = ["Breakfast", "Lunch", "Dinner"]
MAX_DAYS    = 7          # hard upper limit enforced by agent
CAL_LO, CAL_HI = 200, 900
PT_LO,  PT_HI  = 5, 90

# ── Ingredient canonicalization & noise filtering ─────────────────────────
# Maps surface forms → canonical grocery label
INGREDIENT_CANONICAL = {
    # oils → one entry
    "olive oil": "olive oil", "mustard oil": "mustard oil",
    "coconut oil": "coconut oil", "sesame oil": "sesame oil",
    "vegetable oil": "oil", "canola oil": "oil", "oil": "oil",
    "cooking oil": "oil", "sunflower oil": "oil",
    # ghee/butter
    "ghee": "ghee / butter", "butter": "ghee / butter",
    # onion variants
    "onion": "onion", "red onion": "onion", "spring onion": "spring onion",
    "shallots": "onion", "shallot": "onion", "green onion": "spring onion",
    "fried onions": "onion", "caramelised onion": "onion",
    "caramelised onions": "onion",
    # tomato variants
    "tomato": "tomato", "tomatoes": "tomato", "cherry tomatoes": "tomato",
    "canned tomatoes": "canned tomatoes", "tomato puree": "tomato puree",
    "tomato sauce": "tomato sauce", "tomato paste": "tomato paste",
    # garlic/ginger
    "garlic": "garlic", "ginger": "ginger",
    "ginger": "ginger", "ginger garlic": "garlic & ginger",
    # fresh herbs
    "coriander": "fresh coriander", "cilantro": "fresh coriander",
    "fresh coriander": "fresh coriander",
    "parsley": "fresh parsley", "fresh parsley": "fresh parsley",
    "basil": "fresh basil", "fresh basil": "fresh basil",
    # lemon/lime
    "lemon": "lemon / lime", "lime": "lemon / lime",
    "lemon juice": "lemon / lime",
    # rice
    "basmati rice": "basmati rice", "jasmine rice": "rice",
    "rice": "rice", "steamed rice": "rice", "brown rice": "rice",
    "sushi rice": "rice",
    # lentils
    "lentils": "lentils", "red lentils": "red lentils",
    "green lentils": "green lentils", "moong dal": "moong dal",
    "toor dal": "toor dal", "chana dal": "chana dal",
    # spices group (merge ultra-generic)
    "spices": "mixed spices", "mixed spices": "mixed spices",
    "whole spices": "mixed spices",
    # salt / water — always available, skip
    "salt": None, "water": None, "black pepper": "black pepper",
    "pepper": "black pepper",
}

# Ingredients so generic/always-at-home they clutter the list
SKIP_INGREDIENTS = {
    "salt", "water", "black pepper", "pepper", "sugar", "flour",
    "mixed spices", "spices", "herbs", "seasoning", "baking powder",
}

# Canonical spice tokens that appear in nearly every dish — keep but group
COMMON_SPICES = {
    "cumin", "turmeric", "coriander powder", "garam masala", "paprika",
    "chilli", "chilli powder", "red chilli", "green chilli", "bay leaf",
    "mustard seeds", "curry leaves", "cardamom", "cloves", "cinnamon",
    "allspice", "fenugreek", "ajwain",
}

def _canonical_ingredient(raw: str) -> Optional[str]:
    """
    Return the canonical grocery label for an ingredient, or None to skip.
    """
    key = raw.lower().strip()
    if key in SKIP_INGREDIENTS:
        return None
    if key in INGREDIENT_CANONICAL:
        return INGREDIENT_CANONICAL[key]   # may be None (skip)
    return key   # use as-is

# ── disease rules ─────────────────────────────────────────────────────────────
DISEASE_RULES = {
    "diabetes": {
        "avoid": ["sugar","sweet","candy","syrup","honey","jam","white rice",
                  "refined","dessert","cookie","cake","ice cream","chocolate","juice"],
        "prefer_high":"protein","prefer_low":"carbs",
        "note":"Low-carb, high-protein meals. Avoid sugars and refined carbs.",
    },
    "hypertension": {
        "avoid": ["salt","sodium","pickle","soy sauce","processed","canned","chips",
                  "bacon","ham","sausage"],
        "prefer_high":"protein","prefer_low":"fat",
        "note":"Low-sodium meals. Avoid processed/salty foods.",
    },
    "obesity": {
        "avoid": ["fried","butter","cream","cheese","mayo","bacon","dessert",
                  "fast food","pizza","burger"],
        "prefer_high":"protein","prefer_low":"fat",
        "max_cal_norm":0.45,
        "note":"Low-calorie, high-protein meals. Avoid high-fat foods.",
    },
    "heart disease": {
        "avoid": ["fried","butter","lard","bacon","sausage","processed",
                  "red meat","palm oil","cream"],
        "prefer_high":"protein","prefer_low":"fat",
        "note":"Heart-healthy meals. Avoid saturated fats.",
    },
    "high cholesterol": {
        "avoid": ["egg yolk","butter","cream","cheese","shrimp","fried",
                  "bacon","lard","coconut oil"],
        "prefer_high":"protein","prefer_low":"fat",
        "note":"Low-cholesterol meals. Avoid saturated fats.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
def _clean(obj):
    """Recursively convert numpy scalars to Python natives."""
    if isinstance(obj, dict):   return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):   return [_clean(i) for i in obj]
    if isinstance(obj, np.bool_):    return bool(obj)
    if isinstance(obj, np.integer):  return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    return obj

# ─────────────────────────────────────────────────────────────────────────────
class MealPlannerAgent:
    """Agentic meal planner with plan → score → select → validate loop."""

    def __init__(self):
        self.meals_df   = self._load_meals()
        self.cal_df     = self._load_calories()
        self._trace: list[str] = []   # agent reasoning trace

    # ═══════════════════════════════════════════════════════════════════════
    # DATA
    # ═══════════════════════════════════════════════════════════════════════
    def _load_meals(self) -> pd.DataFrame:
        """
        Loads and merges all 3 meal datasets:
          1. meals.csv                       – base dataset with recipe_steps (202 rows)
          2. healthy_meal_plans_updated.csv  – original full dataset (417 rows)
          3. calories.csv                    – loaded separately in _load_calories()
        Result: union deduplicated by meal_name; meals.csv rows take priority
        (they carry recipe_steps). Unique meal count grows significantly.
        """
        # ── Dataset 1: meals.csv (has recipe_steps) ──
        df1 = pd.read_csv(os.path.join(DATA_DIR, "meals.csv"))
        df1["_source"] = "meals_csv"

        # ── Dataset 2: healthy_meal_plans_updated.csv ──
        df2 = pd.read_csv(os.path.join(DATA_DIR, "healthy_meal_plans_updated.csv"))
        df2["_source"] = "healthy_meal_plans_updated"
        if "recipe_steps" not in df2.columns:
            df2["recipe_steps"] = ""

        # ── Merge: df1 first so its rows win on duplicate meal_name ──
        combined = pd.concat([df1, df2], ignore_index=True)
        combined["meal_name"] = combined["meal_name"].str.strip()
        combined = combined.drop_duplicates(subset="meal_name", keep="first")

        combined["diet_type"]    = combined["diet_type"].str.strip()
        combined["ingredients"]  = combined["ingredients"].fillna("").str.strip()
        combined["recipe_steps"] = combined["recipe_steps"].fillna("")
        combined["_ing_tokens"]  = combined["ingredients"].apply(
            lambda s: {t.strip().lower() for t in s.split(",") if t.strip()}
        )
        combined = combined.reset_index(drop=True)

        src = combined["_source"].value_counts().to_dict()
        print(f"[AGENT] 3 datasets merged → {len(combined)} unique meals "              f"(meals.csv: {src.get("meals_csv",0)}, "              f"healthy_meal_plans_updated: {src.get("healthy_meal_plans_updated",0)})")
        return combined

    def _load_calories(self) -> pd.DataFrame:
        df = pd.read_csv(os.path.join(DATA_DIR, "calories.csv"))
        df.columns = [c.strip() for c in df.columns]
        df["cal_value"] = (
            df["Cals_per100grams"].astype(str)
            .str.extract(r"(\d+\.?\d*)", expand=False).astype(float)
        )
        return df

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1 — ANALYZE user intent → goal weights
    # ═══════════════════════════════════════════════════════════════════════
    def _analyze(self, budget, diet_type, num_days, disease,
                 cook_time, weight_goal, favorite_meal, ingredient_pref):
        """Return a goals dict that drives all subsequent scoring."""
        num_days = min(int(num_days), MAX_DAYS)

        # calorie target by weight goal
        if weight_goal == "loss":
            cal_target, cal_label = 0.25, "low-cal (weight loss)"
        elif weight_goal == "gain":
            cal_target, cal_label = 0.70, "high-cal (weight gain)"
        else:
            cal_target, cal_label = 0.45, "balanced (maintain)"

        disease_key = (disease or "").lower()
        d_rules     = DISEASE_RULES.get(disease_key, {})
        prefer_high = d_rules.get("prefer_high", "protein")
        prefer_low  = d_rules.get("prefer_low",  "carbs")

        budget_per_meal = budget / max(num_days * len(SLOTS), 1)

        # favourite meal token set — filter short/stop words
        FAV_STOP = {"with","and","the","in","of","a","an","or","for","de"}
        fav_tokens = set()
        if favorite_meal:
            fav_tokens = {
                t.lower().strip() for t in favorite_meal.split()
                if len(t) > 2 and t.lower() not in FAV_STOP
            }

        # ingredient preference tokens — treat each comma-separated item as one token
        ing_tokens = set()
        if ingredient_pref:
            # Support both comma-separated ("paneer, chicken") and single ("paneer")
            ing_tokens = {t.lower().strip() for t in ingredient_pref.replace(",", " ").split() if t.strip()}

        goals = dict(
            budget=budget, num_days=num_days, diet_type=diet_type,
            disease=disease, disease_key=disease_key, d_rules=d_rules,
            prefer_high=prefer_high, prefer_low=prefer_low,
            cal_target=cal_target, cal_label=cal_label,
            budget_per_meal=budget_per_meal,
            cook_time=cook_time, weight_goal=weight_goal,
            favorite_meal=favorite_meal, fav_tokens=fav_tokens,
            ingredient_pref=ingredient_pref, ing_tokens=ing_tokens,
        )

        self._trace.append(
            f"[ANALYZE] goal='{cal_label}', budget_per_meal=₹{budget_per_meal:.0f}, "
            f"diet={diet_type}, disease={disease or 'none'}, "
            f"cook={cook_time or 'any'}, fav='{favorite_meal or 'none'}', "
            f"ing_pref='{ingredient_pref or 'none'}'"
        )
        return goals

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2 — PLAN: build candidate pool
    # ═══════════════════════════════════════════════════════════════════════
    def _plan_pool(self, goals: dict) -> pd.DataFrame:
        """
        Build the candidate meal pool.
        KEY GUARANTEE: meals that match the user's favourite_meal name OR
        ingredient_pref are ALWAYS kept in the pool regardless of cost,
        so the queue builders can always find them.
        """
        full_df = self.meals_df.copy()

        # ── identify fav / ingredient rows to protect from filters ────────
        fav_mask  = pd.Series(False, index=full_df.index)
        ing_mask  = pd.Series(False, index=full_df.index)

        if goals.get("favorite_meal"):
            base_tokens = self._get_base_tokens(goals["favorite_meal"])
            primary     = max(base_tokens, key=len) if base_tokens else ""
            if primary:
                # match on meal name OR ingredients (so 'paneer masala' also
                # finds paneer dishes even if the name says 'paneer tikka')
                fav_mask = full_df["meal_name"].str.lower().str.contains(primary, regex=False) |                            full_df["ingredients"].str.lower().str.contains(primary, regex=False)

        if goals.get("ing_tokens"):
            for tok in goals["ing_tokens"]:
                ing_mask |= full_df["ingredients"].str.lower().str.contains(tok, regex=False) |                             full_df["meal_name"].str.lower().str.contains(tok, regex=False)

        protected = full_df[fav_mask | ing_mask].copy()

        # ── 2a. Hard diet filter on whole dataset ─────────────────────────
        df = full_df.copy()
        if goals["diet_type"].lower() == "veg":
            df = df[df["diet_type"] == "Veg"]
            protected = protected[protected["diet_type"] == "Veg"]
            self._trace.append(f"[PLAN] Diet filter → {len(df)} veg meals")
        else:
            self._trace.append(f"[PLAN] Diet filter → {len(df)} all-diet meals")

        # ── 2b. Budget filter (does NOT apply to protected fav/ing rows) ──
        bpm    = goals["budget_per_meal"]
        strict = df[df["cost_inr"] <= bpm * 1.5]
        medium = df[df["cost_inr"] <= bpm * 2.5]
        if len(strict) >= 10:
            df = strict
            self._trace.append(f"[PLAN] Budget strict-filter (≤₹{bpm*1.5:.0f}) → {len(df)} meals")
        elif len(medium) >= 10:
            df = medium
            self._trace.append(f"[PLAN] Budget medium-filter (≤₹{bpm*2.5:.0f}) → {len(df)} meals")
        else:
            self._trace.append(f"[PLAN] Budget filter skipped (pool too small), keeping all")

        # ── 2c. Cook-time filter ──────────────────────────────────────────
        if goals["cook_time"] == "quick":
            quick = df[df["prep_time"] <= 0.40]
            df = quick if len(quick) >= 8 else df
            self._trace.append(f"[PLAN] Cook-time 'quick' filter → {len(df)} meals")

        # ── 2d. Disease filter ────────────────────────────────────────────
        if goals["d_rules"]:
            avoid  = goals["d_rules"].get("avoid", [])
            before = len(df)
            safe   = df[~df["ingredients"].str.lower().apply(
                lambda s: any(kw in s for kw in avoid)
            )]
            if len(safe) >= 12:
                df = safe
                self._trace.append(f"[PLAN] Disease '{goals['disease']}' filter: {before}→{len(df)} meals")

        # ── Merge protected rows back in (union, dedup) ───────────────────
        if not protected.empty:
            df = pd.concat([df, protected], ignore_index=True).drop_duplicates(
                subset="meal_name", keep="first"
            )
            self._trace.append(
                f"[PLAN] Protected {len(protected)} fav/ingredient meals kept in pool → total {len(df)}"
            )

        if df.empty:
            df = self.meals_df.copy()
            self._trace.append("[PLAN] ⚠ Pool empty — using full dataset as fallback")

        return df.reset_index(drop=True)

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3 — SCORE: multi-factor weighted scoring
    # ═══════════════════════════════════════════════════════════════════════
    def _score_row(self, row: pd.Series, goals: dict) -> float:
        """
        Score components (weights sum to 1.0):
          cost_score      0.35  – prefer under budget
          cal_score       0.20  – proximity to calorie target
          nutrition_score 0.15  – preferred macro (disease-aware)
          health_score    0.10  – is_healthy flag
          fav_sim_score   0.10  – similarity to favourite meal
          ing_pref_score  0.05  – ingredient preference match
          prep_score      0.05  – cooking time preference
        """
        bpm   = goals["budget_per_meal"]
        cal_n = float(row.get("calories", 0.5))
        pt_n  = float(row.get("prep_time", 0.5))

        # — cost score: hard penalty for meals over per-meal budget
        ratio = row["cost_inr"] / (bpm + 1e-9)
        if   ratio <= 0.5:  cost_score = 1.0
        elif ratio <= 0.8:  cost_score = 1.0 - (ratio - 0.5) * 1.2
        elif ratio <= 1.0:  cost_score = max(0.0, 0.64 - (ratio - 0.8) * 2.0)
        else:               cost_score = 0.0   # over per-meal budget → zero cost score

        # — calorie score: directional scoring based on weight goal
        #   loss   → lower cal_n = better  (linear: score = 1 - cal_n)
        #   gain   → higher cal_n = better (linear: score = cal_n)
        #   maintain → Gaussian around 0.40 (wide sigma)
        wg = goals.get("weight_goal")
        if wg == "loss":
            cal_score = 1.0 - cal_n            # 0.028 → 0.97, 0.90 → 0.10
        elif wg == "gain":
            cal_score = cal_n                  # 0.928 → 0.93, 0.028 → 0.03
        else:
            # Gaussian centred on mid-range (maintain = balanced)
            cal_score = np.exp(-((cal_n - 0.40) ** 2) / 0.12)

        # — nutrition score
        ph = goals["prefer_high"]; pl = goals["prefer_low"]
        high_v = float(row.get(ph, 0.5))
        low_v  = float(row.get(pl, 0.5))
        nutrition_score = high_v * 0.6 + (1 - low_v) * 0.4

        # — health flag
        health_score = float(row.get("is_healthy", 0))

        # — favourite meal SIMILARITY
        # Strategy: token overlap on meal NAME + raw ingredients string
        fav_sim = 0.0
        fav_tokens = goals["fav_tokens"]
        if fav_tokens:
            meal_name_lower = row["meal_name"].lower()
            raw_ings_lower  = str(row.get("ingredients", "")).lower()
            combined_text   = meal_name_lower + " " + raw_ings_lower
            matched = sum(1 for t in fav_tokens if t in combined_text)
            fav_sim = matched / len(fav_tokens)
            # Strong bonus for exact name substring match
            if goals["favorite_meal"] and goals["favorite_meal"].lower() in meal_name_lower:
                fav_sim = min(1.0, fav_sim + 0.6)

        # — ingredient preference score: direct substring match against raw ingredients
        # Uses the raw ingredients string for reliable matching (not tokenised set)
        ing_pref_score = 0.0
        if goals["ing_tokens"]:
            raw_ings = str(row.get("ingredients", "")).lower()
            matched = sum(1 for t in goals["ing_tokens"] if t in raw_ings)
            ing_pref_score = min(1.0, matched / len(goals["ing_tokens"]))

        # — prep time score
        if goals["cook_time"] == "quick":
            prep_score = 1.0 - pt_n          # lower prep = higher score
        else:
            prep_score = 1.0 - abs(pt_n - 0.45)   # prefer moderate

        score = (
            0.35 * cost_score
          + 0.15 * cal_score
          + 0.10 * nutrition_score
          + 0.06 * health_score
          + 0.18 * fav_sim
          + 0.11 * ing_pref_score
          + 0.05 * prep_score
        )

        # hard zero for meals that individually exceed 1.3× per-meal budget
        if ratio > 1.3:
            score *= 0.05

        # disease max-calorie penalty
        max_cal = goals["d_rules"].get("max_cal_norm", 1.0)
        if cal_n > max_cal:
            score *= 0.3

        return float(score)

    def _score_pool(self, pool: pd.DataFrame, goals: dict) -> pd.DataFrame:
        pool = pool.copy()
        pool["_score"] = pool.apply(lambda r: self._score_row(r, goals), axis=1)
        # Add small random jitter so identical-scoring meals get shuffled each run.
        # Jitter is ±6% of the score range — enough to reorder close competitors
        # without overriding meaningful quality differences.
        jitter = np.random.uniform(-0.06, 0.06, size=len(pool))
        pool["_score"] = (pool["_score"] + jitter).clip(0.0, 1.5)
        pool = pool.sort_values("_score", ascending=False).reset_index(drop=True)
        self._trace.append(
            f"[SCORE] Top-3 scored meals (post-jitter): "
            + ", ".join(f"{r.meal_name}({r._score:.3f})"
                        for _, r in pool.head(3).iterrows())
        )
        return pool

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4 — SELECT: 1 fav-similar dish per day + 1 ingredient dish per day
    # ═══════════════════════════════════════════════════════════════════════
    def _get_base_tokens(self, meal_name: str) -> set:
        """
        Extract the meaningful base words from a meal name.
        e.g. 'Paneer Butter Masala' → {'paneer', 'butter', 'masala'}
        Stop words are filtered out so 'paneer tikka' and 'paneer matar'
        both share the base token 'paneer'.
        """
        STOP = {"with", "and", "the", "in", "of", "a", "an", "or", "for",
                "de", "style", "indian", "special"}
        return {t.lower().strip() for t in meal_name.split()
                if len(t) > 2 and t.lower() not in STOP}

    def _build_fav_queue(self, pool: pd.DataFrame, goals: dict) -> list:
        """
        Build an ordered queue of fav-similar meals — one distinct dish per day.

        Strategy (most-to-least specific):
          1. Meals whose NAME contains the longest base token of the favourite
             (e.g. favourite='Paneer Masala' → primary='paneer' → 'Paneer Tikka',
              'Paneer Butter Masala', 'Matar Paneer', …)
          2. Meals whose INGREDIENTS contain the primary token (catches dishes
             like 'Shahi Paneer' or any paneer dish not using the word in the name)
          3. Exact name match is placed FIRST in the queue (Day 1 Lunch).

        Returns a deduplicated list of meal_names ordered best-first.
        """
        if not goals.get("favorite_meal"):
            return []

        fav_name    = goals["favorite_meal"]
        base_tokens = self._get_base_tokens(fav_name)
        if not base_tokens:
            return []

        # Use the longest token as primary (most specific noun, e.g. 'paneer')
        primary = max(base_tokens, key=len)

        pool = pool.copy()

        # Tier 1: meal NAME contains primary token
        name_match = pool["meal_name"].str.lower().str.contains(primary, regex=False)
        # Tier 2: INGREDIENTS contain primary token (but name doesn't)
        ing_match  = (~name_match) & pool["ingredients"].str.lower().str.contains(primary, regex=False)

        tier1 = pool[name_match].sort_values("_score", ascending=False)
        tier2 = pool[ing_match].sort_values("_score", ascending=False)

        # Build queue: exact fav first, then tier1, then tier2
        queue: list[str] = []
        exact = tier1[tier1["meal_name"].str.lower() == fav_name.lower()]
        if not exact.empty:
            queue.append(exact.iloc[0]["meal_name"])

        for df_tier in [tier1, tier2]:
            for _, row in df_tier.iterrows():
                if row["meal_name"] not in queue:
                    queue.append(row["meal_name"])

        self._trace.append(
            f"[SELECT] 🎯 Fav-queue (primary='{primary}'): {queue[:goals['num_days']]}"
        )
        return queue

    def _build_ing_queue(self, pool: pd.DataFrame, goals: dict) -> list:
        """
        Build an ordered queue of ingredient-preference meals — one per day.

        Matches against BOTH meal name and ingredients string, so that
        'paneer' finds 'Paneer Tikka', 'Matar Paneer', 'Shahi Paneer', etc.
        Ordered by: #tokens matched DESC → score DESC.
        Deduplicates against fav_queue so the same dish isn't pinned twice.
        """
        if not goals.get("ing_tokens"):
            return []

        ing_tokens = goals["ing_tokens"]
        pool = pool.copy()

        combined_text = pool["meal_name"].str.lower() + " " + pool["ingredients"].str.lower()
        pool["_ing_match_count"] = combined_text.apply(
            lambda s: sum(1 for t in ing_tokens if t in s)
        )
        matched = (
            pool[pool["_ing_match_count"] > 0]
            .sort_values(["_ing_match_count", "_score"], ascending=[False, False])
        )
        queue = list(matched["meal_name"].unique())
        self._trace.append(
            f"[SELECT] 🧂 Ingredient queue (tokens={list(ing_tokens)[:3]}): {queue[:goals['num_days']]}"
        )
        return queue

    def _select_meals(self, pool: pd.DataFrame, goals: dict) -> list[dict]:
        """
        Select meals for the plan using a guaranteed pinned-slot system.

        Pinning rules (one fav + one ingredient meal per day, different slots):
          Day 1: fav → Lunch,  ing → Dinner
          Day 2: fav → Dinner, ing → Lunch   (alternating keeps variety)
          Day 3: fav → Lunch,  ing → Dinner  … etc.
          Breakfast is always chosen freely by the scorer.

        Pinned meals are ALWAYS placed even if they push the total cost up —
        _validate compensates by swapping expensive non-pinned meals down.
        """
        num_days     = goals["num_days"]
        bpm          = goals["budget_per_meal"]
        meals_needed = num_days * len(SLOTS)

        fav_queue = self._build_fav_queue(pool, goals)
        ing_queue = self._build_ing_queue(pool, goals)

        # ── Build per-day pinned slot map ─────────────────────────────────
        pinned: dict        = {}   # (day, slot) → meal_name
        used_in_pinned: set = set()

        fav_idx = 0
        ing_idx = 0

        for day in range(1, num_days + 1):
            # Alternate which heavy slot fav vs ingredient gets
            fav_slot = "Lunch"  if day % 2 == 1 else "Dinner"
            ing_slot = "Dinner" if day % 2 == 1 else "Lunch"

            # Pin next unused fav-similar meal
            while fav_idx < len(fav_queue):
                name = fav_queue[fav_idx]; fav_idx += 1
                if name not in used_in_pinned:
                    pinned[(day, fav_slot)] = name
                    used_in_pinned.add(name)
                    self._trace.append(
                        f"[SELECT] 📌 Day {day} {fav_slot} ← fav-similar '{name}'"
                    )
                    break

            # Pin next unused ingredient-match meal (must be a different meal)
            while ing_idx < len(ing_queue):
                name = ing_queue[ing_idx]; ing_idx += 1
                if name not in used_in_pinned:
                    pinned[(day, ing_slot)] = name
                    used_in_pinned.add(name)
                    self._trace.append(
                        f"[SELECT] 📌 Day {day} {ing_slot} ← ingredient-match '{name}'"
                    )
                    break

        self._trace.append(
            f"[SELECT] Pinned {len(pinned)} slots across {num_days} days"
        )

        # Build candidate pool: top scored meals, then shuffle within score bands
        # so meals with similar scores appear in different order each run.
        top_n      = min(len(pool), max(meals_needed * 5, 50))
        candidates = pool.sort_values("_score", ascending=False).head(top_n).copy()
        # Shuffle within 0.05-width score bands to break ties differently each run
        candidates["_band"] = (candidates["_score"] / 0.05).astype(int)
        candidates = candidates.groupby("_band", group_keys=False).apply(
            lambda g: g.sample(frac=1)
        ).reset_index(drop=True)

        used_names: set       = set()
        used_ingredients: set = set()
        selected: list        = []
        total_cost: float     = 0.0

        for day in range(1, num_days + 1):
            for slot in SLOTS:
                budget_left     = goals["budget"] - total_cost
                remaining_slots = meals_needed - len(selected)
                tight = (budget_left / max(remaining_slots, 1)) < (bpm * 0.5)

                forced  = False
                pin_key = (day, slot)

                if pin_key in pinned:
                    pin_name = pinned[pin_key]
                    pin_row  = pool[pool["meal_name"] == pin_name]
                    if not pin_row.empty and pin_name not in used_names:
                        # Always honour the pin — cost overruns fixed by _validate
                        chosen = pin_row.iloc[0]
                        forced = True
                        self._trace.append(
                            f"[SELECT] ✅ Day {day}/{slot}: PINNED '{pin_name}' "
                            f"₹{int(chosen['cost_inr'])} (budget_left=₹{budget_left:.0f})"
                        )

                if not forced:
                    available = candidates[~candidates["meal_name"].isin(used_names)].copy()
                    if available.empty:
                        available = candidates.copy()
                        self._trace.append(f"[SELECT] Day{day}/{slot}: pool exhausted — allowing reuse")

                    # When budget is tight, heavily favour cheaper meals for free slots
                    if tight:
                        cost_norm = 1 - (available["cost_inr"] / (available["cost_inr"].max() + 1))
                        available = available.copy()
                        available["_score"] = available["_score"] * 0.4 + 0.6 * cost_norm

                    available = available.copy()
                    available["_ing_overlap"] = available["_ing_tokens"].apply(
                        lambda s: len(s & used_ingredients) / (len(s) + 1e-9)
                    )
                    available["_final_score"] = available["_score"] + 0.06 * available["_ing_overlap"]
                    scores  = available["_final_score"].values.astype(float)
                    shifted = scores - scores.max()
                    # Temperature=3: flatter distribution → more meal variety each run
                    weights = np.exp(shifted * 3)
                    weights = weights / weights.sum()
                    idx     = np.random.choice(len(available), p=weights)
                    chosen  = available.iloc[idx]

                used_names.add(chosen["meal_name"])
                used_ingredients.update(chosen["_ing_tokens"])
                total_cost += float(chosen["cost_inr"])

                ing_list  = [i.strip() for i in str(chosen["ingredients"]).split(",") if i.strip()]
                cal_est   = self._lookup_calories(ing_list)
                score_val = float(chosen.get("_score", 0.5))

                is_fav = chosen["meal_name"] in used_in_pinned

                selected.append({
                    "day": day, "slot": slot,
                    "meal": {
                        "meal_name":               chosen["meal_name"],
                        "diet_type":               chosen["diet_type"],
                        "cost_inr":                int(chosen["cost_inr"]),
                        "ingredients":             ing_list,
                        "estimated_calories_kcal": cal_est,
                        "calories_normalized":     round(float(chosen["calories"]), 4),
                        "protein":                 round(float(chosen["protein"]),  4),
                        "fat":                     round(float(chosen["fat"]),      4),
                        "carbs":                   round(float(chosen["carbs"]),    4),
                        "prep_time_normalized":    round(float(chosen["prep_time"]),4),
                        "score":                   round(score_val, 4),
                        "is_healthy":              bool(chosen["is_healthy"]),
                        "is_quick":                bool(chosen["prep_time"] <= 0.40),
                        "is_favorite":             is_fav,
                        "recipe_steps":            str(chosen["recipe_steps"]) if chosen["recipe_steps"] else "",
                    }
                })

        self._trace.append(f"[SELECT] Selected {len(selected)} meals, total cost \u20b9{total_cost:.0f}")
        return selected, total_cost, used_in_pinned

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 5 — VALIDATE + RE-PLAN
    # ═══════════════════════════════════════════════════════════════════════
    def _validate(self, selected, total_cost, goals, pool, pinned_names: set = None):
        """
        Swap expensive NON-PINNED meals to bring total closer to budget.

        HARD RULE: pinned_names (fav / ingredient meals) are NEVER swapped out,
        even if the plan remains over budget after all other swaps.
        It is acceptable to exceed budget in order to honour the user's favourite
        dish and ingredient preferences — the summary will note the overage.
        """
        budget       = goals["budget"]
        pinned_names = pinned_names or set()

        if total_cost <= budget:
            self._trace.append(f"[VALIDATE] ✅ Within budget (₹{total_cost:.0f} ≤ ₹{budget:.0f})")
            return selected, total_cost

        self._trace.append(
            f"[VALIDATE] ⚠ Over budget (₹{total_cost:.0f} > ₹{budget:.0f}) — swapping "
            f"non-pinned meals only (protecting {len(pinned_names)} fav/ingredient meals)"
        )

        # Pass 1: swap most expensive NON-PINNED meals with cheaper alternatives
        swapped_names = set(x["meal"]["meal_name"] for x in selected)
        sorted_sel = sorted(
            selected,
            key=lambda x: (x["meal"]["meal_name"] in pinned_names, -x["meal"]["cost_inr"])
        )

        for entry in sorted_sel:
            if total_cost <= budget:
                break
            if entry["meal"]["meal_name"] in pinned_names:
                continue   # ← NEVER touch pinned meals
            old_cost = entry["meal"]["cost_inr"]
            cheaper = pool[
                (~pool["meal_name"].isin(swapped_names)) &
                (pool["cost_inr"] < old_cost)
            ].sort_values("cost_inr").head(1)

            if cheaper.empty:
                continue

            r        = cheaper.iloc[0]
            savings  = old_cost - r["cost_inr"]
            ing_list = [i.strip() for i in str(r["ingredients"]).split(",") if i.strip()]
            cal_est  = self._lookup_calories(ing_list)

            swapped_names.discard(entry["meal"]["meal_name"])
            swapped_names.add(r["meal_name"])
            entry["meal"].update({
                "meal_name":               r["meal_name"],
                "diet_type":               r["diet_type"],
                "cost_inr":                int(r["cost_inr"]),
                "ingredients":             ing_list,
                "estimated_calories_kcal": cal_est,
                "calories_normalized":     round(float(r["calories"]), 4),
                "protein":                 round(float(r["protein"]),  4),
                "fat":                     round(float(r["fat"]),      4),
                "carbs":                   round(float(r["carbs"]),    4),
                "score":                   round(float(r.get("_score", 0.5)), 4),
                "is_healthy":              bool(r["is_healthy"]),
                "is_favorite":             False,
                "recipe_steps":            str(r["recipe_steps"]) if r["recipe_steps"] else "",
            })
            total_cost -= savings
            self._trace.append(
                f"[REPLAN] Swapped '{entry['meal']['meal_name']}' ← '{r['meal_name']}' saving ₹{savings:.0f}"
            )

        # Pass 2: still over? Replace non-pinned meals with absolute cheapest in pool.
        # Pinned meals remain untouched no matter what.
        if total_cost > budget:
            self._trace.append("[VALIDATE] Pass 2: force cheapest non-pinned meals (pinned meals protected)")
            cheapest_row = pool.sort_values("cost_inr").iloc[0]
            cheapest_ing = [i.strip() for i in str(cheapest_row["ingredients"]).split(",") if i.strip()]
            cheapest_cal = self._lookup_calories(cheapest_ing)

            sorted_sel2 = sorted(
                selected,
                key=lambda x: (x["meal"]["meal_name"] in pinned_names, -x["meal"]["cost_inr"])
            )
            for entry in sorted_sel2:
                if total_cost <= budget:
                    break
                if entry["meal"]["meal_name"] in pinned_names:
                    continue   # ← still never touch pinned meals
                old_cost = entry["meal"]["cost_inr"]
                if int(cheapest_row["cost_inr"]) >= old_cost:
                    continue
                savings = old_cost - int(cheapest_row["cost_inr"])
                entry["meal"].update({
                    "meal_name":               cheapest_row["meal_name"],
                    "diet_type":               cheapest_row["diet_type"],
                    "cost_inr":                int(cheapest_row["cost_inr"]),
                    "ingredients":             cheapest_ing,
                    "estimated_calories_kcal": cheapest_cal,
                    "calories_normalized":     round(float(cheapest_row["calories"]), 4),
                    "protein":                 round(float(cheapest_row["protein"]),  4),
                    "fat":                     round(float(cheapest_row["fat"]),      4),
                    "carbs":                   round(float(cheapest_row["carbs"]),    4),
                    "score":                   round(float(cheapest_row.get("_score", 0.3)), 4),
                    "is_healthy":              bool(cheapest_row["is_healthy"]),
                    "is_favorite":             False,
                    "recipe_steps":            str(cheapest_row["recipe_steps"]) if cheapest_row["recipe_steps"] else "",
                })
                total_cost -= savings
                self._trace.append(f"[REPLAN-P2] Force-cheapest swap saving ₹{savings:.0f}")

        if total_cost > budget:
            over = total_cost - budget
            self._trace.append(
                f"[VALIDATE] ℹ️ Final cost ₹{total_cost:.0f} exceeds budget ₹{budget:.0f} by ₹{over:.0f} "
                f"— fav/ingredient meals kept as requested (cannot swap them out)"
            )
        else:
            self._trace.append(f"[VALIDATE] ✅ Final cost ₹{total_cost:.0f} within budget ₹{budget:.0f}")

        return selected, total_cost

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 6 — REFLECT: build plan structure + summary
    # ═══════════════════════════════════════════════════════════════════════
    def _reflect(self, selected, total_cost, goals):
        num_days = goals["num_days"]

        # Pantry discount: for multi-day plans some ingredients are already
        # at home from Day 1 shopping, so effective spend is lower.
        #   Day 1 → full price   (buying everything fresh)
        #   Day 2 → 10% discount (staples already stocked)
        #   Day 3+ → 20% discount (pantry well-stocked)
        def _pantry_factor(day: int, total_days: int) -> float:
            if total_days <= 1 or day == 1:
                return 1.0
            if day == 2:
                return 0.90
            return 0.80

        # reshape flat list → day-keyed structure
        plan = []
        for day in range(1, num_days + 1):
            day_entries      = [e for e in selected if e["day"] == day]
            day_meals        = {e["slot"]: e["meal"] for e in day_entries}
            raw_day_cost     = sum(e["meal"]["cost_inr"] for e in day_entries)
            factor           = _pantry_factor(day, num_days)
            adj_day_cost     = int(round(raw_day_cost * factor))
            day_cal          = sum(e["meal"]["estimated_calories_kcal"] for e in day_entries)
            discount_pct     = round((1 - factor) * 100)
            plan.append({
                "day":                day,
                "meals":             day_meals,
                "day_cost_inr":      adj_day_cost,
                "raw_day_cost_inr":  int(round(raw_day_cost)),
                "pantry_discount_pct": discount_pct,
                "day_calories_kcal": round(day_cal, 1),
            })

        total_cal         = sum(d["day_calories_kcal"] for d in plan)
        # Budget check uses the REAL (undiscounted) total_cost.
        # Display uses the pantry-adjusted total.
        display_total     = sum(d["day_cost_inr"] for d in plan)
        within_budget     = total_cost <= goals["budget"]
        saved             = goals["budget"] - total_cost
        display_remaining = goals["budget"] - display_total
        unique_meals  = len({e["meal"]["meal_name"] for e in selected})
        d_note        = goals["d_rules"].get("note","") if goals["d_rules"] else ""

        if within_budget:
            budget_line = f"✅ Within budget — ₹{abs(int(round(saved)))} to spare."
        else:
            budget_line = f"⚠️ Over budget by ₹{abs(int(round(saved)))} to fit your favourites."

        ai_summary = (
            f"{budget_line} "
            f"{num_days}-day plan · {unique_meals} unique meals · "
            f"~{int(round(total_cal/num_days))} kcal/day · "
            f"Est. spend ₹{int(round(display_total))}."
            + (f" {d_note}" if d_note else "")
        ).strip()

        self._trace.append("[REFLECT] Plan assembled — returning to client")

        return {
            "plan": plan,
            "grocery_list": self._build_grocery(plan),
            "summary": {
                "total_cost_inr":           int(round(display_total)),
                "raw_total_cost_inr":        int(round(total_cost)),
                "total_calories_kcal":      round(total_cal, 1),
                "avg_daily_cost_inr":       int(round(display_total / num_days)),
                "avg_daily_calories_kcal":  round(total_cal / num_days, 1),
                "budget":                   int(round(goals["budget"])),
                "budget_remaining_inr":     int(round(display_remaining)),
                "within_budget":            within_budget,
                "num_days":                 num_days,
                "diet_type":                goals["diet_type"],
                "disease":                  goals["disease"],
                "disease_note":             d_note,
                "ai_summary":               ai_summary,
                "cook_time":                goals["cook_time"],
                "weight_goal":              goals["weight_goal"],
                "favorite_meal":            goals["favorite_meal"],
                "ingredient_pref":          goals["ingredient_pref"],
                "agent_trace":              self._trace.copy(),
            },
        }

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC — generate_plan: full agent loop
    # ═══════════════════════════════════════════════════════════════════════
    def generate_plan(
        self,
        budget: float,
        diet_type: str,
        num_days: int,
        disease: Optional[str]        = None,
        cook_time: Optional[str]      = None,
        weight_goal: Optional[str]    = None,
        favorite_meal: Optional[str]  = None,
        ingredient_pref: Optional[str]= None,
        seed: Optional[int]           = None,
    ) -> dict:
        self._trace = []
        # Always seed with a fresh random value so every Generate / Re-plan
        # call produces a different selection of dishes and sequence.
        # An explicit seed (e.g. for tests/repro) overrides this.
        effective_seed = seed if seed is not None else random.randint(0, 2**31 - 1)
        random.seed(effective_seed)
        np.random.seed(effective_seed)
        self._trace.append(f"[INIT] run_seed={effective_seed}")

        # ── agent loop ──────────────────────────────────────────────────
        goals    = self._analyze(budget, diet_type, num_days, disease,
                                 cook_time, weight_goal, favorite_meal, ingredient_pref)
        pool     = self._plan_pool(goals)
        pool     = self._score_pool(pool, goals)
        selected, total_cost, pinned_names = self._select_meals(pool, goals)
        selected, total_cost = self._validate(selected, total_cost, goals, pool, pinned_names)
        result   = self._reflect(selected, total_cost, goals)

        return _clean(result)

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC — recipe generation
    # ═══════════════════════════════════════════════════════════════════════
    def get_recipe(self, meal_name: str, ingredients: list[str]) -> dict:
        """Return contextual recipe steps (uses stored steps if available)."""
        row = self.meals_df[
            self.meals_df["meal_name"].str.lower() == meal_name.lower()
        ]
        if not row.empty and str(row.iloc[0]["recipe_steps"]).strip():
            steps_raw = row.iloc[0]["recipe_steps"]
            # split on '. ' or numbered
            steps = _split_steps(steps_raw)
            return {"meal_name": meal_name, "steps": steps, "source": "dataset"}

        # agent-generated contextual recipe
        steps = _generate_recipe(meal_name, ingredients)
        return {"meal_name": meal_name, "steps": steps, "source": "generated"}

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC — similar meal recommendations
    # ═══════════════════════════════════════════════════════════════════════
    def get_similar_meals(self, meal_name: str, top_n: int = 5) -> list[dict]:
        """Jaccard-based ingredient similarity to find related meals."""
        row = self.meals_df[self.meals_df["meal_name"].str.lower() == meal_name.lower()]
        if row.empty:
            return []
        query_tokens = row.iloc[0]["_ing_tokens"]
        df = self.meals_df[self.meals_df["meal_name"].str.lower() != meal_name.lower()].copy()
        df["_sim"] = df["_ing_tokens"].apply(
            lambda s: len(s & query_tokens) / (len(s | query_tokens) + 1e-9)
        )
        top = df.nlargest(top_n, "_sim")[["meal_name","diet_type","cost_inr","_sim"]]
        return top.rename(columns={"_sim": "similarity"}).to_dict("records")

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════
    def _lookup_calories(self, ingredients: list) -> float:
        total = 0.0
        for ing in ingredients:
            m = self.cal_df[
                self.cal_df["FoodItem"].str.lower().str.contains(
                    ing.lower()[:6], na=False, regex=False
                )
            ]
            total += float(m.iloc[0]["cal_value"]) if not m.empty else 80.0
        return round(total, 1)

    def _build_grocery(self, plan: list) -> list:
        """
        Build a clean, deduplicated grocery list.
        - Canonicalises ingredient variants (oil, onion, tomato etc.)
        - Skips always-at-home items (salt, water, pepper)
        - Groups all common spices into a single 'Basic Spices' summary entry
        - Only shows items used in ≥2 meals OR that are the main protein/base of a dish
        - Returns sorted by frequency descending
        """
        freq: dict[str, int] = {}
        spice_freq = 0

        # Core proteins/bases always worth listing even if used once
        ALWAYS_KEEP = {
            "paneer", "chicken", "lamb", "mutton", "fish", "prawn", "prawns",
            "salmon", "tofu", "tempeh", "beef", "pork", "turkey", "tuna",
            "eggs", "egg", "chickpeas", "lentils", "red lentils", "green lentils",
            "moong dal", "toor dal", "chana dal", "black beans", "kidney beans",
            "white beans", "quinoa", "pasta", "basmati rice", "rice",
            "bread", "flatbread", "noodles", "soba noodles", "rice noodles",
        }

        for day in plan:
            for meal in day["meals"].values():
                for ing in meal["ingredients"]:
                    canon = _canonical_ingredient(ing)
                    if canon is None:
                        continue
                    if canon in COMMON_SPICES:
                        spice_freq += 1
                        continue
                    freq[canon] = freq.get(canon, 0) + 1

        # Filter: keep items used ≥2 times, OR that are always-keep proteins/bases
        items = [
            {"ingredient": k, "frequency": v}
            for k, v in freq.items()
            if v >= 2 or k.lower() in ALWAYS_KEEP
        ]
        items = sorted(items, key=lambda x: -x["frequency"])

        # Prepend grouped spices
        if spice_freq:
            items.insert(0, {
                "ingredient": "Basic Spices (cumin, turmeric, coriander, garam masala, chilli)",
                "frequency": spice_freq,
            })

        return items

    def get_dataset_stats(self) -> dict:
        df = self.meals_df
        return {
            "total_meals":   int(len(df)),
            "veg_meals":     int((df["diet_type"] == "Veg").sum()),
            "non_veg_meals": int((df["diet_type"] == "Non-veg").sum()),
            "cost_range":    {"min": int(df["cost_inr"].min()), "max": int(df["cost_inr"].max())},
            "avg_cost":      round(float(df["cost_inr"].mean()), 2),
            "healthy_meals": int(df["is_healthy"].sum()),
            "with_recipes":  int((df["recipe_steps"] != "").sum()),
        }

    def chat(self, message: str, plan_context: Optional[dict] = None) -> str:
        """Rule-based + agent-trace aware chat."""
        msg = message.lower()
        ctx = plan_context or {}

        if any(w in msg for w in ["trace","reasoning","why","how did","explain"]):
            trace = ctx.get("agent_trace", [])
            if trace:
                return "🤖 Agent reasoning:\n" + "\n".join(f"  {t}" for t in trace)
            return "No trace available — generate a plan first."

        if any(w in msg for w in ["budget","cost","spend","price"]):
            if ctx:
                w = "✅" if ctx.get("within_budget") else "⚠️"
                return (f"{w} Total: ₹{ctx.get('total_cost_inr','?')} / ₹{ctx.get('budget','?')}. "
                        f"Remaining: ₹{ctx.get('budget_remaining_inr','?')}.")
            return "Generate a plan first to see cost details."

        if any(w in msg for w in ["calorie","kcal","energy"]):
            if ctx:
                avg = ctx.get("avg_daily_calories_kcal", 0)
                ok  = 1500 <= float(avg) <= 2500
                return (f"Your plan averages {avg} kcal/day — "
                        f"{'within a healthy range ✅' if ok else '⚠️ outside typical 1500–2500 range'}.")
            return "Generate a plan first."

        if any(w in msg for w in ["grocery","ingredient","shopping","buy"]):
            return ("🛒 Grocery list groups similar ingredients (e.g. all oils together). "
                    "The agent minimises unique items by preferring meals that share ingredients.")

        if any(w in msg for w in ["disease","diabetes","hypertension","obesity","heart","cholesterol"]):
            disease = ctx.get("disease")
            if disease and disease.lower() in DISEASE_RULES:
                note  = DISEASE_RULES[disease.lower()]["note"]
                avoid = ", ".join(DISEASE_RULES[disease.lower()]["avoid"][:5])
                return f"For {disease}: {note}\nKey ingredients avoided: {avoid}…"
            return "Select a health condition in the form to enable disease-aware filtering."

        if any(w in msg for w in ["hi","hello","hey","help"]):
            return ("👋 I'm your agentic meal planning assistant! Ask me about:\n"
                    "• budget & cost  • calories  • grocery list\n"
                    "• health conditions  • agent reasoning (type 'explain')\n"
                    "• meal swaps (click Re-plan for a fresh selection)")

        return ("I can help with budget, calories, groceries, health conditions or agent reasoning.\n"
                "Try: 'Am I within budget?', 'Explain your choices', or 'Show calorie info'.")


# ─────────────────────────────────────────────────────────────────────────────
# Recipe helpers
# ─────────────────────────────────────────────────────────────────────────────
def _split_steps(raw: str) -> list[str]:
    """Split a recipe string into clean steps."""
    # try numbered split first
    numbered = re.split(r"\d+\.\s+", raw.strip())
    numbered = [s.strip() for s in numbered if len(s.strip()) > 10]
    if len(numbered) >= 2:
        return numbered
    # sentence split
    sentences = re.split(r"(?<=[.!?])\s+", raw.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def _generate_recipe(meal_name: str, ingredients: list[str]) -> list[str]:
    """
    Contextual rule-based recipe generation.
    Detects cooking method from meal name + ingredients.
    """
    name_l = meal_name.lower()
    ings   = [i.lower() for i in ingredients]
    ing_str= ", ".join(ingredients[:5])

    # detect primary protein/base
    has_chicken  = any("chicken" in i  for i in ings)
    has_fish     = any(w in " ".join(ings) for w in ["salmon","fish","cod","prawn","tuna","sea bass"])
    has_egg      = any("egg" in i      for i in ings)
    has_lentils  = any(w in " ".join(ings) for w in ["lentil","dal","moong","toor","chana"])
    has_rice     = any("rice" in i     for i in ings)
    has_pasta    = any("pasta" in i or "noodle" in i for i in ings)
    has_tofu     = any("tofu" in i     for i in ings)
    is_soup      = any(w in name_l for w in ["soup","broth","stew","chowder","shorba"])
    is_stir_fry  = "stir" in name_l or ("fry" in name_l and "stir" in name_l)
    is_curry     = "curry" in name_l or "masala" in name_l or "korma" in name_l
    is_salad     = "salad" in name_l or "bowl" in name_l
    is_grilled   = "grill" in name_l or "tikka" in name_l or "kebab" in name_l
    is_baked     = "bak" in name_l or "roast" in name_l

    # ── template library ─────────────────────────────────────────────────
    if is_curry:
        return [
            f"Heat oil in a pan over medium heat. Add onion and sauté until golden, then stir in garlic and ginger.",
            f"Add the dry spices and cook for 1 minute until fragrant. Pour in tomatoes (or coconut milk) and simmer 5 minutes.",
            f"Add the main ingredient ({ingredients[0]}) and cook until fully done — about 10–15 minutes on low heat.",
            f"Garnish with fresh coriander. Serve hot with rice or flatbread.",
        ]
    if is_soup:
        return [
            f"Sauté aromatics (onion, garlic) in a large pot over medium heat for 3–4 minutes.",
            f"Add {ing_str} along with enough broth or water to cover. Bring to a boil.",
            f"Reduce heat and simmer for 20–30 minutes until everything is tender and flavours meld.",
            f"Adjust seasoning, ladle into bowls, and serve with crusty bread or a side of your choice.",
        ]
    if is_stir_fry:
        return [
            f"Prepare all ingredients: slice {ingredients[0]} and chop vegetables into bite-sized pieces.",
            f"Heat oil in a wok or large pan on high heat. Add aromatics (garlic, ginger) and stir 30 seconds.",
            f"Add protein first, cook until sealed, then add vegetables. Stir-fry on high for 3–4 minutes.",
            f"Pour in sauce ({', '.join([i for i in ings if any(w in i for w in ['sauce','soy','oyster','fish'])][:2])} or mix of soy + sesame). Toss to coat and serve over rice.",
        ]
    if is_grilled:
        return [
            f"Marinate {ingredients[0]} in a blend of {', '.join(ingredients[1:4])} for at least 30 minutes (overnight for best flavour).",
            f"Preheat grill or grill pan to medium-high. Lightly oil the grates.",
            f"Grill for 4–6 minutes per side, depending on thickness, until nicely charred and cooked through.",
            f"Rest for 2 minutes, then serve with a salad, raita, or dipping sauce of choice.",
        ]
    if is_baked:
        return [
            f"Preheat oven to 200 °C (400 °F). Toss {ing_str} with olive oil and seasoning.",
            f"Spread evenly on a baking tray in a single layer.",
            f"Roast for 20–25 minutes, flipping halfway, until golden and cooked through.",
            f"Finish with fresh herbs or a squeeze of lemon and serve immediately.",
        ]
    if is_salad:
        return [
            f"Prepare the base: rinse and roughly chop greens or grains. Cook any warm components if needed.",
            f"Combine {ing_str} in a large bowl. Season generously.",
            f"Whisk together your dressing (olive oil, lemon/vinegar, mustard) and drizzle over the salad.",
            f"Toss gently, top with any crunchy elements (nuts, croutons), and serve immediately.",
        ]
    if has_pasta:
        return [
            f"Boil salted water and cook pasta until al dente. Reserve ½ cup pasta water before draining.",
            f"Meanwhile, heat olive oil and sauté {', '.join(ingredients[1:3])} for 3–4 minutes.",
            f"Add remaining sauce ingredients; simmer 5 minutes. Toss with drained pasta, adding pasta water to loosen.",
            f"Plate and garnish with parmesan or fresh herbs.",
        ]
    if has_rice and not is_curry:
        return [
            f"Rinse rice until water runs clear. Cook in 1.75× water with a pinch of salt.",
            f"In a separate pan, prepare the accompaniment: sauté {', '.join(ingredients[1:3])} then add spices and remaining ingredients.",
            f"Simmer together for 10 minutes until well combined and fragrant.",
            f"Serve rice topped with the curry/stir-fry mixture, garnished with fresh herbs.",
        ]
    if has_lentils:
        return [
            f"Rinse lentils and soak 10 minutes if using larger varieties. Drain.",
            f"Bring lentils to a boil in 3× water with turmeric. Skim foam and simmer 20 minutes until soft.",
            f"In a separate pan, prepare a tadka: heat oil, add mustard seeds, then {', '.join(ingredients[2:5])}. Cook 2 minutes.",
            f"Pour tadka over lentils, stir, adjust salt and lemon, and serve.",
        ]
    if has_egg:
        return [
            f"Crack eggs into a bowl; season with salt and pepper. Whisk until just combined.",
            f"Heat oil or butter in a non-stick pan over medium heat. Add any aromatics ({', '.join(ingredients[1:3])}) and cook 1 minute.",
            f"Pour in eggs and cook, gently folding, until just set — about 2–3 minutes.",
            f"Remove from heat (eggs continue cooking), plate, and garnish with fresh herbs.",
        ]

    # generic fallback
    return [
        f"Prepare all ingredients: roughly chop {ing_str}.",
        f"Cook the main components over medium heat using your preferred method (sauté, grill, or boil).",
        f"Combine everything and simmer/toss for 5–10 minutes until well combined and seasoned.",
        f"Plate and serve hot, garnished with fresh herbs or a squeeze of citrus.",
    ]