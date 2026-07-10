"""
recommendation_model/calculator.py
====================================
All health and nutrition calculations:
  BMI, BMR (Mifflin-St Jeor), TDEE, IBW, Target Calories,
  Macro targets, Micro targets, Body Fat % (US Navy), 
  Water intake, Meal calorie distribution.
"""

import math
from dataclasses import dataclass, field
from typing import Dict


# ── Activity level multipliers (Harris-Benedict) ─────────────────────────────
ACTIVITY_MULTIPLIERS = {
    "sedentary":        1.2,    # desk job, little/no exercise
    "lightly_active":   1.375,  # light exercise 1-3 days/week
    "moderately_active":1.55,   # moderate exercise 3-5 days/week
    "very_active":      1.725,  # hard exercise 6-7 days/week
    "extra_active":     1.9,    # very hard exercise + physical job
}

# ── Goal calorie adjustments ──────────────────────────────────────────────────
GOAL_ADJUSTMENTS = {
    "weight_loss_aggressive": -750,   # ~0.7 kg/week loss
    "weight_loss":            -500,   # ~0.5 kg/week loss
    "weight_loss_mild":       -250,   # ~0.25 kg/week loss
    "maintain":                  0,
    "weight_gain_mild":        250,   # ~0.25 kg/week gain
    "weight_gain":             500,   # ~0.5 kg/week gain
    "muscle_gain":             300,   # lean bulk
}

# ── Macro ratios per goal ─────────────────────────────────────────────────────
# (protein_pct, carb_pct, fat_pct)
MACRO_RATIOS = {
    "weight_loss_aggressive": (0.35, 0.40, 0.25),
    "weight_loss":            (0.30, 0.40, 0.30),
    "weight_loss_mild":       (0.25, 0.45, 0.30),
    "maintain":               (0.25, 0.50, 0.25),
    "weight_gain_mild":       (0.25, 0.50, 0.25),
    "weight_gain":            (0.25, 0.50, 0.25),
    "muscle_gain":            (0.35, 0.45, 0.20),
}

# Calories per gram
KCAL_PER_G = {"protein": 4.0, "carbs": 4.0, "fat": 9.0}


@dataclass
class HealthMetrics:
    """All calculated health and nutrition metrics for a user."""
    # ── Inputs ────────────────────────────────────────────────────────────────
    age:            float
    weight_kg:      float
    height_cm:      float
    sex:            str     # "male" / "female"
    activity_level: str
    goal:           str

    # ── Body composition ─────────────────────────────────────────────────────
    bmi:            float = 0.0
    bmi_category:   str   = ""
    ibw_kg:         float = 0.0      # Ideal body weight (Devine formula)
    abw_kg:         float = 0.0      # Adjusted body weight

    # ── Energy ───────────────────────────────────────────────────────────────
    bmr:            float = 0.0      # Basal Metabolic Rate (Mifflin-St Jeor)
    tdee:           float = 0.0      # Total Daily Energy Expenditure
    target_calories:float = 0.0      # TDEE ± goal adjustment

    # ── Macros (grams/day) ────────────────────────────────────────────────────
    protein_g:      float = 0.0
    carbs_g:        float = 0.0
    fat_g:          float = 0.0

    # ── Macros (calories/day) ─────────────────────────────────────────────────
    protein_kcal:   float = 0.0
    carbs_kcal:     float = 0.0
    fat_kcal:       float = 0.0

    # ── Micro targets (per day) ───────────────────────────────────────────────
    fiber_g:        float = 0.0
    sodium_mg:      float = 0.0
    calcium_mg:     float = 0.0
    iron_mg:        float = 0.0
    vitamin_c_mg:   float = 0.0
    vitamin_d_iu:   float = 0.0
    potassium_mg:   float = 0.0
    water_ml:       float = 0.0

    # ── Meal distribution (per meal, in kcal) ─────────────────────────────────
    meal_calories:  Dict[str, float] = field(default_factory=dict)

    # ── Flags ─────────────────────────────────────────────────────────────────
    is_underweight: bool = False
    is_overweight:  bool = False
    is_obese:       bool = False


def calculate_all(
    age: float,
    weight_kg: float,
    height_cm: float,
    sex: str,
    activity_level: str,
    goal: str,
    meal_count: int = 3,
    # Disease-driven overrides (from recommendation_context)
    has_diabetes:        bool = False,
    has_hypertension:    bool = False,
    has_kidney_disease:  bool = False,
    has_heart_disease:   bool = False,
    has_pcos:            bool = False,
    has_obesity:         bool = False,
    has_anemia:          bool = False,
    has_osteoporosis:    bool = False,
    is_vegetarian:       bool = False,
    is_vegan:            bool = False,
) -> HealthMetrics:
    """
    Master calculation function. Returns a fully populated HealthMetrics object.
    """

    sex_lower    = sex.strip().lower()
    act_key      = activity_level.strip().lower()
    act_mult     = ACTIVITY_MULTIPLIERS.get(act_key, 1.55)
    goal_key     = goal.strip().lower()
    goal_adj     = GOAL_ADJUSTMENTS.get(goal_key, 0)
    macro_ratio  = MACRO_RATIOS.get(goal_key, (0.25, 0.50, 0.25))

    # ── BMI ───────────────────────────────────────────────────────────────────
    h_m = height_cm / 100.0
    bmi = round(weight_kg / (h_m ** 2), 1)

    if   bmi < 16.0:  bmi_cat = "Severely Underweight"
    elif bmi < 18.5:  bmi_cat = "Underweight"
    elif bmi < 25.0:  bmi_cat = "Normal"
    elif bmi < 30.0:  bmi_cat = "Overweight"
    elif bmi < 35.0:  bmi_cat = "Obese Class I"
    elif bmi < 40.0:  bmi_cat = "Obese Class II"
    else:             bmi_cat = "Obese Class III"

    # ── IBW — Devine formula ──────────────────────────────────────────────────
    height_inches = height_cm / 2.54
    inches_over_5ft = max(0, height_inches - 60)
    if sex_lower in ("male","m"):
        ibw = 50.0 + 2.3 * inches_over_5ft
    else:
        ibw = 45.5 + 2.3 * inches_over_5ft

    # Adjusted Body Weight (used for obese patients in nutrition therapy)
    abw = ibw + 0.4 * (weight_kg - ibw) if weight_kg > ibw * 1.2 else weight_kg

    # ── BMR — Mifflin-St Jeor (most validated for modern populations) ─────────
    if sex_lower in ("male","m"):
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    # ── TDEE ─────────────────────────────────────────────────────────────────
    tdee = bmr * act_mult

    # ── Target calories ───────────────────────────────────────────────────────
    raw_target = tdee + goal_adj

    # Hard floor: never go below 1200 kcal (women) or 1500 kcal (men)
    floor = 1500 if sex_lower in ("male","m") else 1200
    target_cal = max(raw_target, floor)

    # Disease overrides — cap calories
    if has_diabetes or has_obesity:
        target_cal = min(target_cal, 1800)
    if has_kidney_disease:
        target_cal = min(target_cal, 1800)

    # ── Macros ────────────────────────────────────────────────────────────────
    p_pct, c_pct, f_pct = macro_ratio

    # Disease adjustments to macro ratios
    if has_diabetes:
        # Lower carbs, higher protein
        c_pct = max(c_pct - 0.05, 0.35)
        p_pct = min(p_pct + 0.05, 0.35)
    if has_kidney_disease:
        # Lower protein for CKD (0.6–0.8 g/kg)
        protein_g_ckd = round(abw * 0.7, 1)
        p_kcal_ckd    = protein_g_ckd * 4
        p_pct         = p_kcal_ckd / target_cal
        c_pct         = 0.55
        f_pct         = 1 - p_pct - c_pct
    if has_heart_disease:
        f_pct = min(f_pct, 0.25)
        c_pct = max(c_pct, 0.50)

    protein_kcal = target_cal * p_pct
    carbs_kcal   = target_cal * c_pct
    fat_kcal     = target_cal * f_pct

    protein_g = round(protein_kcal / KCAL_PER_G["protein"], 1)
    carbs_g   = round(carbs_kcal   / KCAL_PER_G["carbs"],   1)
    fat_g     = round(fat_kcal     / KCAL_PER_G["fat"],     1)

    # ── Micronutrient targets (DRI / ICMR based) ─────────────────────────────
    fiber_g = 38 if sex_lower in ("male","m") else 25          # ICMR RDA
    if has_diabetes: fiber_g = max(fiber_g, 35)                # higher for DM

    sodium_mg = 2300
    if has_hypertension or has_heart_disease:  sodium_mg = 1500
    if has_kidney_disease:                     sodium_mg = 1000

    calcium_mg = 1000
    if sex_lower not in ("male","m") and age > 50:  calcium_mg = 1200
    if has_osteoporosis:                             calcium_mg = 1500

    iron_mg = 17 if sex_lower in ("male","m") else 21          # ICMR values
    if has_anemia: iron_mg = 30
    if is_vegan:   iron_mg = round(iron_mg * 1.8, 0)           # lower bioavailability

    vitamin_c_mg = 80     # ICMR RDA
    if is_vegan: vitamin_c_mg = 120    # enhances non-heme iron absorption

    vitamin_d_iu = 600
    if age > 70:  vitamin_d_iu = 800

    potassium_mg = 4700
    if has_kidney_disease:  potassium_mg = 2000  # strict limit for CKD

    # Water: 35 ml/kg body weight, adjusted for activity & climate
    water_ml = round(weight_kg * 35 + (act_mult - 1.2) * 500, 0)
    if has_kidney_disease:  water_ml = min(water_ml, 1500)

    # ── Meal calorie distribution ─────────────────────────────────────────────
    meal_cal = _distribute_calories(target_cal, meal_count, goal_key)

    return HealthMetrics(
        age=age, weight_kg=weight_kg, height_cm=height_cm,
        sex=sex, activity_level=activity_level, goal=goal,
        bmi=bmi, bmi_category=bmi_cat,
        ibw_kg=round(ibw, 1), abw_kg=round(abw, 1),
        bmr=round(bmr, 0), tdee=round(tdee, 0),
        target_calories=round(target_cal, 0),
        protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g,
        protein_kcal=round(protein_kcal, 0),
        carbs_kcal=round(carbs_kcal, 0),
        fat_kcal=round(fat_kcal, 0),
        fiber_g=fiber_g, sodium_mg=sodium_mg,
        calcium_mg=calcium_mg, iron_mg=iron_mg,
        vitamin_c_mg=vitamin_c_mg, vitamin_d_iu=vitamin_d_iu,
        potassium_mg=potassium_mg, water_ml=water_ml,
        meal_calories=meal_cal,
        is_underweight = bmi < 18.5,
        is_overweight  = 25 <= bmi < 30,
        is_obese       = bmi >= 30,
    )


def _distribute_calories(total_kcal: float, meal_count: int, goal: str) -> Dict[str, float]:
    """
    Distribute daily calories across meals.
    Meal names and proportions depend on meal_count and goal.
    """
    # Realistic Indian meal distribution: lunch = main meal, breakfast = light
    distributions = {
        3: {"breakfast":0.25,"lunch":0.45,"dinner":0.30},
        4: {"breakfast":0.20,"mid_morning":0.10,"lunch":0.40,"dinner":0.30},
        5: {"breakfast":0.18,"mid_morning":0.10,"lunch":0.37,"evening_snack":0.10,"dinner":0.25},
        6: {"breakfast":0.15,"mid_morning":0.10,"lunch":0.30,"afternoon":0.10,"evening_snack":0.10,"dinner":0.25},
    }
    dist = distributions.get(meal_count, distributions[3])

    return {
        meal: round(total_kcal * pct, 0)
        for meal, pct in dist.items()
    }


def bmi_advice(metrics: HealthMetrics) -> str:
    """Return a short BMI-based health note."""
    if   metrics.bmi < 16.0:
        return "Severely underweight. Medical evaluation strongly recommended."
    elif metrics.bmi < 18.5:
        return ("Underweight. Focus on nutrient-dense calorie surplus. "
                "Consult a dietitian.")
    elif metrics.bmi < 25.0:
        return "Healthy weight range. Maintain with balanced diet and activity."
    elif metrics.bmi < 27.5:
        return ("Slightly overweight. Moderate calorie deficit and increased "
                "activity recommended.")
    elif metrics.bmi < 30.0:
        return ("Overweight. Structured diet and regular exercise advised. "
                "Consider medical guidance.")
    elif metrics.bmi < 35.0:
        return ("Obese Class I. Medical nutrition therapy strongly recommended. "
                "Gradual lifestyle changes.")
    elif metrics.bmi < 40.0:
        return ("Obese Class II. Medical supervision required. "
                "Structured weight management programme.")
    else:
        return ("Obese Class III. Immediate medical and nutritional intervention. "
                "Bariatric evaluation may be needed.")


# ═══════════════════════════════════════════════════════════════════════
# REALISTIC WEEK DURATION ENGINE
# ═══════════════════════════════════════════════════════════════════════

import datetime as _dt

def calculate_plan_duration(metrics: HealthMetrics,
                             has_diabetes: bool = False,
                             has_hypertension: bool = False,
                             has_kidney_disease: bool = False) -> dict:
    """
    Calculate personalised plan duration based on real clinical parameters.
    
    Logic:
    - Weekly weight change rate = calorie deficit/surplus ÷ 7700 kcal/kg
    - Weeks to reach target = (weight gap to IBW) ÷ weekly_change
    - Capped between 4 and 20 weeks
    - Medical conditions add mandatory minimum
    
    Returns full dict with weeks, milestones, countdown support.
    """
    goal      = (metrics.goal or "maintain").lower()
    bmi       = metrics.bmi
    weight    = metrics.weight_kg
    ibw       = metrics.ibw_kg
    tdee      = metrics.tdee
    target    = metrics.target_calories
    sex       = metrics.sex.lower()

    # ── Step 1: Real weekly weight change from calorie math ───────────────
    daily_delta       = target - tdee           # negative = deficit
    weekly_kcal_delta = daily_delta * 7
    # 1 kg fat = 7700 kcal (Wishnofsky rule)
    weekly_kg_change  = weekly_kcal_delta / 7700.0   # neg=loss, pos=gain

    # ── Step 2: Calculate weeks needed to reach a meaningful target ───────
    if goal in ("weight_loss_aggressive", "weight_loss", "weight_loss_mild"):
        # Target: get to healthy BMI upper bound (BMI 23 for South Asians)
        target_weight  = 23.0 * ((metrics.height_cm / 100) ** 2)
        weight_to_lose = max(weight - target_weight, 0)
        if abs(weekly_kg_change) < 0.05:
            weeks = 8   # plateau — still benefit from 8 weeks
        else:
            weeks = math.ceil(weight_to_lose / abs(weekly_kg_change))

    elif goal in ("weight_gain", "weight_gain_mild", "muscle_gain"):
        # Target: get to healthy BMI lower bound (BMI 18.5)
        target_weight  = 18.5 * ((metrics.height_cm / 100) ** 2)
        weight_to_gain = max(target_weight - weight, 0)
        if abs(weekly_kg_change) < 0.05:
            weeks = 8
        else:
            weeks = math.ceil(weight_to_gain / abs(weekly_kg_change))
        # Muscle gain needs minimum 10 weeks to see meaningful change
        if goal == "muscle_gain":
            weeks = max(weeks, 10)

    else:  # maintain
        weeks = 4   # maintenance review cycle

    # ── Step 3: Apply medical and practical bounds ─────────────────────────
    # Medical conditions → minimum weeks of consistency required
    medical_min = 0
    if has_diabetes:          medical_min = max(medical_min, 10)
    if has_hypertension:      medical_min = max(medical_min, 8)
    if has_kidney_disease:    medical_min = max(medical_min, 12)

    weeks = max(weeks, medical_min)

    # BMI-based minimum: very underweight/obese need more time
    if bmi < 16.0 or bmi >= 35.0:  weeks = max(weeks, 16)
    elif bmi < 17.5 or bmi >= 30.0: weeks = max(weeks, 12)
    elif bmi < 18.5 or bmi >= 27.5: weeks = max(weeks, 8)

    # Practical cap: re-assess every 20 weeks max
    weeks = min(weeks, 20)

    # ── Step 4: Build plan_start date and countdown ────────────────────────
    today          = _dt.date.today()
    plan_start_str = today.isoformat()
    plan_end_date  = today + _dt.timedelta(weeks=weeks)
    plan_end_str   = plan_end_date.isoformat()

    expected_total_change = round(weekly_kg_change * weeks, 1)
    expected_end_weight   = round(weight + expected_total_change, 1)
    days_remaining        = (plan_end_date - today).days

    # ── Step 5: Personalised milestones ───────────────────────────────────
    milestones = _build_milestones(goal, weeks, weekly_kg_change, metrics)

    # ── Step 6: Urgency ────────────────────────────────────────────────────
    if bmi >= 35 or bmi < 16 or has_kidney_disease:
        urgency = "high"
    elif bmi >= 30 or bmi < 18.5 or has_diabetes or has_hypertension:
        urgency = "moderate"
    else:
        urgency = "routine"

    # ── Step 7: Reassessment guidance ─────────────────────────────────────
    direction = "lose" if weekly_kg_change < 0 else ("gain" if weekly_kg_change > 0 else "maintain")
    abs_change = abs(round(weekly_kg_change, 2))

    if direction == "lose":
        reassess_note = (
            f"After {weeks} weeks you should have lost approximately "
            f"{abs(expected_total_change):.1f} kg. "
            "Come back with your new weight and measurements to get an updated plan. "
            "If weight loss stalls for 2+ consecutive weeks, take a 1-week diet break at maintenance."
        )
    elif direction == "gain":
        reassess_note = (
            f"After {weeks} weeks you should have gained approximately "
            f"{abs(expected_total_change):.1f} kg. "
            "Return with updated measurements to recalculate your new targets."
        )
    else:
        reassess_note = (
            "Reassess your plan every 4 weeks. "
            "If your weight shifts by more than 1.5 kg, adjust calories accordingly."
        )

    return {
        "weeks_recommended":       weeks,
        "plan_start":              plan_start_str,
        "plan_end":                plan_end_str,
        "days_remaining":          days_remaining,
        "weekly_weight_change_kg": round(weekly_kg_change, 3),
        "expected_change_kg":      expected_total_change,
        "expected_end_weight_kg":  expected_end_weight,
        "milestones":              milestones,
        "reassess_note":           reassess_note,
        "urgency":                 urgency,
        "direction":               direction,
    }


def recalculate_weeks_remaining(plan_start_iso: str, weeks_recommended: int) -> dict:
    """
    Given the original plan start date and recommended weeks,
    compute real-time countdown for the frontend.
    """
    try:
        start = _dt.date.fromisoformat(plan_start_iso)
    except Exception:
        start = _dt.date.today()
    end            = start + _dt.timedelta(weeks=weeks_recommended)
    today          = _dt.date.today()
    days_elapsed   = (today - start).days
    days_total     = weeks_recommended * 7
    days_remaining = max((end - today).days, 0)
    weeks_elapsed  = days_elapsed // 7
    weeks_remaining= max(weeks_recommended - weeks_elapsed, 0)
    pct_complete   = min(round((days_elapsed / max(days_total, 1)) * 100, 1), 100)
    is_complete    = today >= end

    return {
        "days_elapsed":    days_elapsed,
        "days_remaining":  days_remaining,
        "weeks_elapsed":   weeks_elapsed,
        "weeks_remaining": weeks_remaining,
        "pct_complete":    pct_complete,
        "is_complete":     is_complete,
        "plan_end":        end.isoformat(),
    }


def _build_milestones(goal: str, total_weeks: int,
                      wt_change: float, metrics: HealthMetrics) -> list:
    """Build week-by-week personalised milestones with evidence-based tips."""
    abs_wt  = abs(wt_change)
    is_loss = wt_change < 0
    is_gain = wt_change > 0

    # Checkpoints: 1, then every 2 weeks, then final
    checkpoints = sorted(set(
        [1, 2] +
        list(range(4, total_weeks, 2)) +
        [total_weeks]
    ))

    TIPS_LOSS = [
        "Week 1 is about building habits, not perfection. Focus on meal timing.",
        "Add a 20-min walk daily — burns ~80 kcal and reduces insulin resistance.",
        "Drink 2 glasses of water 30 min before each main meal to reduce portion size.",
        "Check your iron and B12 — deficiency causes fatigue that kills motivation.",
        "Swap white rice for hand-pounded or parboiled rice — lower GI, same taste.",
        "Sleep 7–8 hours. Poor sleep raises ghrelin (hunger hormone) by ~24%.",
        "Halfway there! Take waist measurement — often reduces before scale moves.",
        "Reduce refined carbs gradually — maida → atta → multigrain.",
        "If plateau hits: cut 100 kcal from dinner, not breakfast or lunch.",
        "Final week — photograph your meals. Visual logging increases awareness.",
    ]
    TIPS_GAIN = [
        "Eat within 30 min of waking — skipping breakfast slows anabolic signalling.",
        "Add a calorie-dense pre-bed snack: warm milk + banana or peanut butter toast.",
        "Spread protein evenly — 20–30g per meal for optimal muscle protein synthesis.",
        "Track your intake honestly — most people underestimate by 200–400 kcal/day.",
        "Add healthy fats: ghee on rotis, a handful of mixed nuts mid-morning.",
        "Resistance training 3× per week converts your calorie surplus into muscle.",
        "Sleep is anabolic — 80% of GH is secreted during deep sleep.",
        "Measure arm circumference — muscle gains show there before the scale.",
        "If no weight change in 2 weeks, add 150–200 kcal to your dinner.",
        "Final week — compare strength benchmarks (push-ups, squats) to week 1.",
    ]
    TIPS_MAINTAIN = [
        "Weigh yourself once weekly, same time (morning, fasted).",
        "Focus on food quality now — aim for 5 different vegetable colours each day.",
        "Try a new regional healthy recipe each week to prevent diet fatigue.",
        "Portion creep is the biggest maintenance risk — measure servings monthly.",
        "Seasonal produce is cheaper, fresher, and better for gut microbiome diversity.",
    ]

    pool = TIPS_LOSS if is_loss else TIPS_GAIN if is_gain else TIPS_MAINTAIN
    milestones = []

    for i, week in enumerate(checkpoints):
        cum_change = round(abs_wt * week, 1)
        wt_label   = f"{cum_change} kg {'lost' if is_loss else 'gained'}"

        if goal == "maintain":
            label = f"Week {week} — Weight check & plan review"
        else:
            label = f"Week {week} — ~{wt_label} from start"

        tip = pool[min(i, len(pool) - 1)]
        milestones.append({"week": week, "label": label, "tip": tip})

    return milestones
