"""
recommendation_model/meal_planner.py
=========================================
REALISTIC INDIAN THALI MEAL PLANNER

Model type: Rule-based combinatorial assignment with weighted food scoring.

Key improvements:
  1. COMBO-BASED meals: each meal is a realistic combination
     e.g. "2 Roti + Dal Tadka + Aloo Gobhi + Raita"
     NOT individual foods picked at random.

  2. COUNT-BASED serving for countable foods:
     "2 pieces Roti (35g each)" instead of "70g Roti"

  3. Bilingual display: every food shown in English + Hindi

  4. Realistic Indian meal patterns:
     Breakfast: Roti/Paratha/Poha/Idli + Dal/Sabzi + Chai
     Lunch:     Rice/Roti + Dal + Sabzi + Raita/Salad
     Dinner:    Roti + Dal/Sabzi (lighter)
     Snacks:    Chai + Biscuit/Fruit/Namkeen
"""

import random
import pandas as pd
from typing import Dict, List, Optional, Tuple
from recommendation_model.calculator import HealthMetrics


# ── Realistic Indian meal templates ──────────────────────────────────────────
# Each template defines COMPONENT ROLES for a complete meal.
# Count means how many of that role to pick.
# Calorie weight = fraction of meal target this component gets.

THALI_TEMPLATES = {
    "breakfast": [
        {"role": "staple",    "count": 1, "base_portion": 200, "cal_pct": 0.45, "label": "मुख्य / Main"},
        {"role": "protein",   "count": 1, "base_portion": 120, "cal_pct": 0.30, "label": "साथ / Side"},
        {"role": "beverage",  "count": 1, "base_portion": 200, "cal_pct": 0.15, "label": "पेय / Drink"},
        {"role": "fruit",     "count": 1, "base_portion": 100, "cal_pct": 0.10, "label": "फल / Fruit"},
    ],
    "mid_morning": [
        {"role": "fruit",     "count": 1, "base_portion": 150, "cal_pct": 0.50, "label": "फल / Fruit"},
        {"role": "beverage",  "count": 1, "base_portion": 150, "cal_pct": 0.30, "label": "पेय / Drink"},
        {"role": "snack",     "count": 1, "base_portion":  60, "cal_pct": 0.20, "label": "नाश्ता / Snack"},
    ],
    "lunch": [
        {"role": "staple",        "count": 1, "base_portion": 200, "cal_pct": 0.35, "label": "मुख्य / Staple"},
        {"role": "protein",       "count": 1, "base_portion": 150, "cal_pct": 0.30, "label": "दाल/प्रोटीन / Dal"},
        {"role": "vegetable",     "count": 1, "base_portion": 120, "cal_pct": 0.20, "label": "सब्जी / Sabzi"},
        {"role": "accompaniment", "count": 1, "base_portion":  80, "cal_pct": 0.10, "label": "साइड / Side"},
        {"role": "beverage",      "count": 1, "base_portion": 150, "cal_pct": 0.05, "label": "पेय / Drink"},
    ],
    "afternoon": [
        {"role": "snack",    "count": 1, "base_portion": 80,  "cal_pct": 0.55, "label": "नाश्ता / Snack"},
        {"role": "beverage", "count": 1, "base_portion": 150, "cal_pct": 0.45, "label": "पेय / Drink"},
    ],
    "evening_snack": [
        {"role": "snack",    "count": 1, "base_portion": 80,  "cal_pct": 0.55, "label": "नाश्ता / Snack"},
        {"role": "beverage", "count": 1, "base_portion": 150, "cal_pct": 0.45, "label": "पेय / Drink"},
    ],
    "dinner": [
        {"role": "staple",        "count": 1, "base_portion": 160, "cal_pct": 0.35, "label": "मुख्य / Staple"},
        {"role": "protein",       "count": 1, "base_portion": 120, "cal_pct": 0.30, "label": "दाल / Dal"},
        {"role": "vegetable",     "count": 1, "base_portion": 100, "cal_pct": 0.25, "label": "सब्जी / Sabzi"},
        {"role": "accompaniment", "count": 1, "base_portion":  60, "cal_pct": 0.10, "label": "साइड / Side"},
    ],
}

ROLE_FALLBACKS = {
    "fruit":         ["snack", "other"],
    "vegetable":     ["protein", "other"],
    "accompaniment": ["vegetable", "snack"],
    "beverage":      ["snack"],
    "staple":        ["protein", "other"],
    "protein":       ["vegetable", "staple"],
    "snack":         ["fruit", "other"],
}

ZONE_CUISINES = {
    "north":   ["North Indian","Kashmiri","Awadhi","Punjabi","Rajasthani","UP",
                "Haryanvi","Himachali","Kumaoni","Garhwali","Sindhi"],
    "south":   ["South Indian","Kerala","Tamil Nadu","Karnataka","Andhra",
                "Chettinad","Hyderabadi","Telangana"],
    "east":    ["Bengali","Odia","Bihari","Assamese","Northeast Indian",
                "Naga","Mizo","Tripuri","Sikkimese","Arunachali","Manipuri",
                "Khasi","Nepali/Sikkimese"],
    "west":    ["Maharashtrian","Gujarati","Goan","Konkan"],
    "central": ["Madhya Pradesh","Chhattisgarhi","Jharkhand","Jain"],
}


# ── Serving size calculation ──────────────────────────────────────────────────

def _calc_serving(row: pd.Series, target_kcal: float) -> Tuple[float, float, str, str]:
    """
    Returns (portion_g, serving_kcal, display_qty, serving_label)
    display_qty: e.g. "2 pieces", "1 katori", "150g"
    """
    unit         = str(row.get("serving_unit", "gram"))
    piece_weight = float(row.get("piece_weight_g", 100))
    cal100       = float(row.get("calories_per_100g", 100))
    if cal100 <= 0:
        cal100 = 50

    UNIT_LABELS = {
        "piece": "नग/पीस",
        "bowl":  "कटोरी",
        "glass": "गिलास",
        "cup":   "कप",
        "katori":"कटोरी",
        "plate": "प्लेट",
        "gram":  "ग्राम",
        "tablespoon": "चम्मच",
    }

    if unit == "gram":
        # Use base_portion passed in (already set by caller)
        portion_g = max(50, min(target_kcal * 100 / cal100, 400))
        portion_g = round(portion_g / 10) * 10  # round to 10g
        portion_g = round(portion_g / 5) * 5  # round to 5g for cleanliness
        qty_str   = f"{portion_g:.0f}g"
        label_str = f"{portion_g:.0f}g"
    else:
        # Calculate how many pieces/bowls fit the calorie target
        kcal_per_unit = cal100 * piece_weight / 100
        if kcal_per_unit <= 0:
            kcal_per_unit = 50
        n_units = max(1, round(target_kcal / kcal_per_unit))

        # Cap sensibly
        caps = {"piece": 4, "bowl": 2, "glass": 2, "cup": 2, "katori": 2, "plate": 1}
        n_units = min(n_units, caps.get(unit, 3))
        n_units = max(1, n_units)

        portion_g = piece_weight * n_units
        hindi_unit = UNIT_LABELS.get(unit, unit)
        qty_str   = f"{n_units} {unit}{'s' if n_units > 1 and unit in ('piece','bowl','glass','cup') else ''}"
        label_str = f"{n_units} {hindi_unit} ({portion_g:.0f}g)"

    serving_kcal = cal100 * portion_g / 100
    return portion_g, serving_kcal, qty_str, label_str


# ── Food scoring ──────────────────────────────────────────────────────────────

def _score_food(row, slot, metrics, used_yesterday):
    score  = float(row.get("disease_score", 50))
    gi     = float(row.get("glycemic_index", 0))
    fiber  = float(row.get("fiber_g", 0))
    prot   = float(row.get("protein_g", 0))
    sodium = float(row.get("sodium_mg", 0))
    cal    = float(row.get("calories_per_100g", 100))

    if fiber >= 3: score += 8
    if fiber >= 6: score += 5
    if 0 < gi <= 40:  score += 10
    elif gi > 70:     score -= 8
    if sodium > 400:  score -= 10
    if sodium > 800:  score -= 20
    if slot in ("mid_morning", "afternoon", "evening_snack") and cal > 400:
        score -= 15
    if metrics.goal in ("weight_loss", "weight_loss_aggressive", "muscle_gain"):
        score += prot * 0.8
    if metrics.goal in ("weight_gain", "weight_gain_mild", "muscle_gain") and cal > 150:
        score += 5
    if row["food_id"] in used_yesterday:
        score -= 15

    return max(round(score, 2), 1)


def _pick_role(safe_df, role, slot, metrics, used_today, used_yesterday, rng):
    roles_to_try = [role] + ROLE_FALLBACKS.get(role, [])
    exhausted    = {fid for fid, cnt in used_today.items() if cnt >= 1}

    for try_role in roles_to_try:
        candidates = safe_df[
            (safe_df["meal_role"] == try_role) &
            (~safe_df["food_id"].isin(exhausted))
        ].copy()

        if candidates.empty:
            candidates = safe_df[safe_df["meal_role"] == try_role].copy()
        if candidates.empty:
            continue

        candidates["_score"] = candidates.apply(
            lambda r: _score_food(r, slot, metrics, used_yesterday), axis=1
        )
        pool    = candidates.nlargest(min(20, len(candidates)), "_score")
        weights = pool["_score"].values
        weights = weights / weights.sum()

        try:
            idx    = rng.choices(range(len(pool)), weights=weights.tolist(), k=1)[0]
            chosen = pool.iloc[idx]
            used_today[chosen["food_id"]] = used_today.get(chosen["food_id"], 0) + 1
            return chosen
        except Exception:
            if not pool.empty:
                return pool.iloc[0]

    return None


# ── Build one food item dict ──────────────────────────────────────────────────

def _build_item(row, target_slot_kcal, slot_def):
    """Create a complete food item dict with bilingual name and serving info."""
    # Allocate calories proportionally
    cal_for_this = target_slot_kcal * slot_def["cal_pct"]
    portion_g, food_kcal, qty_str, label_str = _calc_serving(row, cal_for_this)

    factor       = portion_g / 100.0
    raw_hindi    = row.get("food_name_hindi", "")
    hindi        = "" if (not raw_hindi or str(raw_hindi).strip().lower() in ("nan","none","")) else str(raw_hindi).strip()
    bilingual    = f"{row['food_name']} / {hindi}" if hindi else row['food_name']

    return {
        "food_id":        row["food_id"],
        "food_name":      row["food_name"],
        "food_name_hindi": hindi,
        "food_name_bilingual": bilingual,
        "category":       row.get("category", ""),
        "cuisine_type":   row.get("cuisine_type", ""),
        "meal_role":      row.get("meal_role", "other"),
        "slot_label":     slot_def["label"],
        # Serving display
        "serving_unit":   str(row.get("serving_unit", "gram")),
        "piece_weight_g": float(row.get("piece_weight_g", 100)),
        "qty_display":    qty_str,        # e.g. "2 pieces", "1 katori", "150g"
        "qty_label":      label_str,      # e.g. "2 नग/पीस (70g)"
        "portion_g":      round(portion_g, 0),
        # Nutrition (scaled to portion)
        "calories":       round(food_kcal, 1),
        "protein_g":      round(float(row.get("protein_g",   0)) * factor, 1),
        "carbs_g":        round(float(row.get("carbs_g",     0)) * factor, 1),
        "fat_g":          round(float(row.get("fat_g",       0)) * factor, 1),
        "fiber_g":        round(float(row.get("fiber_g",     0)) * factor, 1),
        "sodium_mg":      round(float(row.get("sodium_mg",   0)) * factor, 1),
        "disease_score":  float(row.get("disease_score", 50)),
    }


# ── Build daily plan ──────────────────────────────────────────────────────────

def build_daily_plan(safe_df, metrics, day_num, used_yesterday=None, seed=42):
    rng            = random.Random(seed + day_num * 997)
    used_today     = {}
    used_yesterday = used_yesterday or set()
    meals          = {}
    day_totals     = {k: 0 for k in ["calories","protein_g","carbs_g","fat_g","fiber_g","sodium_mg"]}

    for slot, target_kcal in metrics.meal_calories.items():
        template = THALI_TEMPLATES.get(slot, THALI_TEMPLATES["lunch"])
        items    = []

        for slot_def in template:
            chosen = _pick_role(
                safe_df, slot_def["role"], slot, metrics,
                used_today, used_yesterday, rng
            )
            if chosen is not None:
                items.append(_build_item(chosen, target_kcal, slot_def))

        # Compute totals
        slot_totals = {
            k: round(sum(i[k] for i in items), 1)
            for k in ["calories","protein_g","carbs_g","fat_g","fiber_g","sodium_mg"]
        }

        # Build human-readable meal description
        meal_desc = _build_meal_description(items, slot)

        meals[slot] = {
            "slot_label":   slot.replace("_", " ").title(),
            "target_kcal":  round(target_kcal, 0),
            "actual_kcal":  slot_totals["calories"],
            "meal_description": meal_desc,        # ← NEW: e.g. "2 Roti + Dal Tadka + Aloo Gobhi"
            "foods":        items,
            "totals":       slot_totals,
        }
        for k in day_totals:
            day_totals[k] += slot_totals.get(k, 0)

    return {
        "day":     day_num,
        "meals":   meals,
        "totals":  {k: round(v, 1) for k, v in day_totals.items()},
        "targets": {
            "calories":  metrics.target_calories,
            "protein_g": metrics.protein_g,
            "carbs_g":   metrics.carbs_g,
            "fat_g":     metrics.fat_g,
            "fiber_g":   metrics.fiber_g,
            "sodium_mg": metrics.sodium_mg,
        },
    }


def _build_meal_description(items, slot):
    """
    Build a short natural-language description of the meal.
    e.g. "2 Roti + Dal Tadka (1 katori) + Aloo Gobhi + Chai"
    """
    parts = []
    for item in items:
        name  = item["food_name"]
        qty   = item["qty_display"]
        hindi = item["food_name_hindi"]

        # Short display: use qty if non-gram
        if item["serving_unit"] != "gram":
            parts.append(f"{qty} {name}")
        else:
            parts.append(f"{name} ({qty})")

    return " + ".join(parts)


# ── Build weekly plan ─────────────────────────────────────────────────────────

def build_weekly_plan(safe_df, metrics, seed=42):
    DAY_NAMES      = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    weekly         = []
    used_yesterday = set()

    for i, day_name in enumerate(DAY_NAMES):
        plan = build_daily_plan(
            safe_df, metrics,
            day_num=i + 1,
            used_yesterday=used_yesterday,
            seed=seed
        )
        plan["day_name"] = day_name
        used_yesterday   = {
            f["food_id"]
            for m in plan["meals"].values()
            for f in m["foods"]
        }
        weekly.append(plan)
    return weekly


# ── Nutritional gap check ─────────────────────────────────────────────────────

def check_nutritional_gaps(daily_plan, metrics):
    t, tg = daily_plan["totals"], daily_plan["targets"]
    checks = [
        ("Calories",  "calories",  tg["calories"],  60,  "kcal"),
        ("Protein",   "protein_g", tg["protein_g"], 10,  "g"),
        ("Carbs",     "carbs_g",   tg["carbs_g"],   15,  "g"),
        ("Fat",       "fat_g",     tg["fat_g"],      8,  "g"),
        ("Fiber",     "fiber_g",   tg["fiber_g"],    5,  "g"),
        ("Sodium",    "sodium_mg", tg["sodium_mg"], 300, "mg"),
    ]
    warnings = []
    for name, key, target, tol, unit in checks:
        if target <= 0: continue
        actual = t.get(key, 0)
        diff   = actual - target
        if abs(diff) > tol:
            direction = "above" if diff > 0 else "below"
            warnings.append(
                f"{name}: {actual:.0f}{unit} "
                f"({direction} target {target:.0f}{unit} by {abs(diff):.0f}{unit})"
            )
    return warnings


# ── Region filter ─────────────────────────────────────────────────────────────

def filter_by_region(safe_df, region_zone):
    if not region_zone or region_zone in ("any", ""):
        return safe_df

    zone_key  = region_zone.lower().strip()
    cuisines  = ZONE_CUISINES.get(zone_key, [])
    if not cuisines:
        return safe_df

    df = safe_df.copy()
    zone_mask    = (df.get("region_zone", pd.Series(dtype=str)) == zone_key)
    cuisine_mask = df["cuisine_type"].isin(cuisines)
    regional     = zone_mask | cuisine_mask

    df.loc[regional, "disease_score"] = (
        df.loc[regional, "disease_score"] + 40
    ).clip(upper=100)

    generic = df["cuisine_type"].isin(
        ["Indian","Continental","Western","Asian","Italian","Chinese"]
    ) & ~regional
    df.loc[generic, "disease_score"] = (
        df.loc[generic, "disease_score"] - 10
    ).clip(lower=1)

    return df
