"""
recommendation_model/meal_planner.py
======================================
Builds personalised daily and 7-day meal plans from the safe food list.

Logic:
  1. Score every safe food against the user's nutritional targets
  2. Assign foods to meal slots by meal_type compatibility
  3. Calculate portion sizes so each meal hits its calorie target
  4. Validate macros and flag any gaps
  5. Generate variety across 7 days (no two identical days)
"""

import random
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

from recommendation_model.calculator import HealthMetrics

# ── Meal slot → food dataset meal_type mapping ────────────────────────────────
SLOT_TO_MEAL_TYPES = {
    "breakfast":     ["breakfast", "breakfast_snack"],
    "mid_morning":   ["breakfast_snack", "snack"],
    "lunch":         ["lunch_dinner"],
    "afternoon":     ["snack", "breakfast_snack"],
    "evening_snack": ["snack", "breakfast_snack"],
    "dinner":        ["lunch_dinner"],
}

# ── Category preferences per meal slot ───────────────────────────────────────
SLOT_CATEGORY_BOOST = {
    "breakfast": [
        "Breakfast Cereals & Porridge", "South Indian Breakfast",
        "Breads & Flatbreads", "Egg Dishes", "Beverages", "Dairy & Paneer"
    ],
    "mid_morning":   ["Fruits", "Beverages", "Snacks & Street Food", "Dairy & Paneer"],
    "lunch":         [
        "Rice Dishes", "Dals & Legumes", "Vegetable Dishes", "Meat Dishes",
        "Seafood", "Indian Foods", "Breads & Flatbreads"
    ],
    "afternoon":     ["Fruits", "Snacks & Street Food", "Beverages"],
    "evening_snack": ["Snacks & Street Food", "Beverages", "Fruits"],
    "dinner":        [
        "Rice Dishes", "Dals & Legumes", "Vegetable Dishes", "Meat Dishes",
        "Seafood", "Indian Foods", "Breads & Flatbreads", "Soups"
    ],
}

# ── Typical portion sizes (grams) per food category ─────────────────────────
PORTION_SIZES = {
    "Rice Dishes":                   200,
    "Breads & Flatbreads":           100,
    "Dals & Legumes":                150,
    "Vegetable Dishes":              150,
    "Meat Dishes":                   120,
    "Seafood":                       120,
    "Dairy & Paneer":                100,
    "Egg Dishes":                    100,
    "South Indian Breakfast":        150,
    "Breakfast Cereals & Porridge":  150,
    "Snacks & Street Food":           80,
    "Fruits":                        150,
    "Beverages":                     200,
    "Soups":                         200,
    "Sweets & Desserts":              60,
    "Accompaniments":                 50,
    "Indian Foods":                  150,
    "default":                       100,
}

# Max servings per day per food (variety enforcement)
MAX_DAILY_SERVINGS = 2


def _get_portion(food_row: pd.Series) -> float:
    """Return a sensible default portion size in grams for a food."""
    cat = str(food_row.get("category", "")).strip()
    return PORTION_SIZES.get(cat, PORTION_SIZES["default"])


def _food_score(food_row: pd.Series, metrics: HealthMetrics, slot: str) -> float:
    """
    Score a food for a specific meal slot (higher = better fit).
    Combines disease_score, nutritional density, and meal-slot category match.
    """
    score = float(food_row.get("disease_score", 50))

    # Category boost for the slot
    preferred_cats = SLOT_CATEGORY_BOOST.get(slot, [])
    if food_row.get("category") in preferred_cats:
        score += 15

    # Calorie density: prefer foods closer to slot target per portion
    cal_per_100 = float(food_row.get("calories_per_100g", 0))
    portion     = _get_portion(food_row)
    food_kcal   = cal_per_100 * portion / 100
    slot_target = metrics.meal_calories.get(slot, 400)

    # Penalise foods that are too calorie-dense or too light for the slot
    cal_ratio = food_kcal / max(slot_target, 1)
    if 0.25 <= cal_ratio <= 0.6:
        score += 10   # good single-dish calorie contribution
    elif cal_ratio > 1.5:
        score -= 15   # single food overshoots the whole slot

    # Fiber bonus (good for all conditions)
    fiber = float(food_row.get("fiber_g", 0))
    if fiber > 3:
        score += 5

    # Low GI bonus for diabetics
    gi = float(food_row.get("glycemic_index", 0))
    if metrics.__dict__.get("has_diabetes") and 0 < gi <= 40:
        score += 10
    if gi > 70:
        score -= 5

    # Protein bonus for muscle/weight gain
    if metrics.goal in ("muscle_gain", "weight_gain", "weight_gain_mild"):
        score += float(food_row.get("protein_g", 0)) * 0.5

    return round(score, 2)


def _pick_foods_for_slot(
    safe_df: pd.DataFrame,
    slot: str,
    target_kcal: float,
    metrics: HealthMetrics,
    used_today: Dict[str, int],
    rng: random.Random,
    n_items: int = 3,
) -> List[Dict]:
    """
    Select n_items foods for a meal slot, respecting calorie target
    and variety constraints.
    Returns list of {food, portion_g, food_kcal, ...}.
    """
    # Filter by compatible meal types
    compatible_types = SLOT_TO_MEAL_TYPES.get(slot, ["lunch_dinner"])
    mask = safe_df["meal_type"].apply(
        lambda mt: any(ct in str(mt) for ct in compatible_types)
    )
    candidates = safe_df[mask].copy()

    if candidates.empty:
        candidates = safe_df.copy()  # fallback: any food

    # Exclude foods used too many times today
    candidates = candidates[
        ~candidates["food_id"].isin(
            [fid for fid, cnt in used_today.items() if cnt >= MAX_DAILY_SERVINGS]
        )
    ]

    if candidates.empty:
        candidates = safe_df.copy()

    # Score all candidates
    candidates = candidates.copy()
    candidates["_score"] = candidates.apply(
        lambda r: _food_score(r, metrics, slot), axis=1
    )
    candidates = candidates.sort_values("_score", ascending=False)

    # Take top N * 3 candidates and sample with probability weighting
    pool_size = min(len(candidates), n_items * 5)
    pool      = candidates.head(pool_size)

    # Weighted random selection (score as weight)
    weights   = pool["_score"].clip(lower=1).values
    weights   = weights / weights.sum()

    try:
        chosen_indices = rng.choices(
            range(len(pool)), weights=weights.tolist(), k=min(n_items, len(pool))
        )
        chosen_indices = list(dict.fromkeys(chosen_indices))  # deduplicate, preserve order
    except Exception:
        chosen_indices = list(range(min(n_items, len(pool))))

    items = []
    remaining_kcal = target_kcal

    for idx in chosen_indices:
        row = pool.iloc[idx]
        portion_g = _get_portion(row)

        cal_per_100 = float(row.get("calories_per_100g", 100))
        food_kcal   = cal_per_100 * portion_g / 100

        # Adjust portion to consume ~half the remaining budget (leaves room for next items)
        if cal_per_100 > 0 and remaining_kcal > 0:
            ideal_portion = (remaining_kcal * 0.5 * 100) / cal_per_100
            # Clip to ±50% of default portion
            min_p = portion_g * 0.5
            max_p = portion_g * 1.5
            portion_g = round(max(min_p, min(ideal_portion, max_p)), 0)
            food_kcal = round(cal_per_100 * portion_g / 100, 1)

        remaining_kcal -= food_kcal

        items.append({
            "food_id":        row["food_id"],
            "food_name":      row["food_name"],
            "category":       row["category"],
            "cuisine_type":   row.get("cuisine_type", ""),
            "portion_g":      portion_g,
            "calories":       food_kcal,
            "protein_g":      round(float(row.get("protein_g", 0))  * portion_g / 100, 1),
            "carbs_g":        round(float(row.get("carbs_g",   0))  * portion_g / 100, 1),
            "fat_g":          round(float(row.get("fat_g",     0))  * portion_g / 100, 1),
            "fiber_g":        round(float(row.get("fiber_g",   0))  * portion_g / 100, 1),
            "sodium_mg":      round(float(row.get("sodium_mg", 0))  * portion_g / 100, 1),
            "disease_score":  float(row.get("disease_score", 50)),
        })

        # Track usage
        fid = row["food_id"]
        used_today[fid] = used_today.get(fid, 0) + 1

    return items


def build_daily_plan(
    safe_df:  pd.DataFrame,
    metrics:  HealthMetrics,
    day_num:  int,
    seed:     int = 42,
) -> Dict:
    """
    Build a full day's meal plan.
    day_num used to vary the seed for day-to-day variety.
    """
    rng = random.Random(seed + day_num * 1000)
    used_today: Dict[str, int] = {}
    meals   = {}
    totals  = {"calories": 0, "protein_g": 0, "carbs_g": 0,
                "fat_g": 0, "fiber_g": 0, "sodium_mg": 0}

    # Pre-filter: remove excessively high-sodium foods when user has sodium limit
    sodium_limit = metrics.sodium_mg  # daily target from metrics
    n_slots = len(metrics.meal_calories) or 3
    per_meal_sodium_cap = (sodium_limit / n_slots) * 2.5  # generous per-meal cap
    # Only cap if sodium limit is a meaningful restriction (< 2000)
    if sodium_limit < 2000:
        safe_df = safe_df[safe_df['sodium_mg'] <= min(per_meal_sodium_cap, 800)]

    slot_order = list(metrics.meal_calories.keys())

    for slot in slot_order:
        target_kcal = metrics.meal_calories[slot]

        # Number of foods per slot varies by slot type and meal count
        if slot in ("mid_morning", "afternoon", "evening_snack"):
            n_foods = 2
        elif slot in ("breakfast",):
            n_foods = 3
        else:
            n_foods = 4   # lunch and dinner get more variety

        items = _pick_foods_for_slot(
            safe_df, slot, target_kcal, metrics, used_today, rng, n_foods
        )

        slot_cal     = sum(i["calories"]  for i in items)
        slot_protein = sum(i["protein_g"] for i in items)
        slot_carbs   = sum(i["carbs_g"]   for i in items)
        slot_fat     = sum(i["fat_g"]     for i in items)
        slot_fiber   = sum(i["fiber_g"]   for i in items)
        slot_sodium  = sum(i["sodium_mg"] for i in items)

        meals[slot] = {
            "target_kcal": target_kcal,
            "actual_kcal": round(slot_cal, 1),
            "foods":       items,
            "totals": {
                "calories":  round(slot_cal,     1),
                "protein_g": round(slot_protein, 1),
                "carbs_g":   round(slot_carbs,   1),
                "fat_g":     round(slot_fat,     1),
                "fiber_g":   round(slot_fiber,   1),
                "sodium_mg": round(slot_sodium,  1),
            }
        }

        totals["calories"]  += slot_cal
        totals["protein_g"] += slot_protein
        totals["carbs_g"]   += slot_carbs
        totals["fat_g"]     += slot_fat
        totals["fiber_g"]   += slot_fiber
        totals["sodium_mg"] += slot_sodium

    return {
        "day":    day_num,
        "meals":  meals,
        "totals": {k: round(v, 1) for k, v in totals.items()},
        "targets": {
            "calories":  metrics.target_calories,
            "protein_g": metrics.protein_g,
            "carbs_g":   metrics.carbs_g,
            "fat_g":     metrics.fat_g,
            "fiber_g":   metrics.fiber_g,
            "sodium_mg": metrics.sodium_mg,
        },
    }


def build_weekly_plan(
    safe_df:  pd.DataFrame,
    metrics:  HealthMetrics,
    seed:     int = 42,
) -> List[Dict]:
    """Build 7 unique daily plans."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"]
    weekly = []
    for i, day_name in enumerate(days):
        plan = build_daily_plan(safe_df, metrics, day_num=i + 1, seed=seed)
        plan["day_name"] = day_name
        weekly.append(plan)
    return weekly


def check_nutritional_gaps(daily_plan: Dict, metrics: HealthMetrics) -> List[str]:
    """
    Compare actual vs target macros/micros and return warning strings
    for any significant gaps (>20% off target).
    """
    warnings = []
    t = daily_plan["totals"]
    tg = daily_plan["targets"]

    checks = [
        ("Calories",  t["calories"],  tg["calories"],  50,   "kcal"),
        ("Protein",   t["protein_g"], tg["protein_g"], 5,    "g"),
        ("Carbs",     t["carbs_g"],   tg["carbs_g"],   10,   "g"),
        ("Fat",       t["fat_g"],     tg["fat_g"],     5,    "g"),
        ("Fiber",     t["fiber_g"],   tg["fiber_g"],   3,    "g"),
        ("Sodium",    t["sodium_mg"], tg["sodium_mg"], 200,  "mg"),
    ]

    for name, actual, target, tolerance, unit in checks:
        if target <= 0:
            continue
        diff = actual - target
        if abs(diff) > tolerance:
            direction = "above" if diff > 0 else "below"
            warnings.append(
                f"{name}: {actual:.0f}{unit} ({direction} target {target:.0f}{unit} by {abs(diff):.0f}{unit})"
            )

    return warnings
