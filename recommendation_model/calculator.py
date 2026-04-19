"""
recommendation_model/calculator.py
====================================
All health and nutrition calculations:
  BMI, BMR (Mifflin-St Jeor), TDEE, IBW, Target Calories,
  Macro targets, Micro targets, Body Fat % (US Navy), 
  Water intake, Meal calorie distribution.
"""

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
    distributions = {
        3: {
            "breakfast": 0.30,
            "lunch":     0.40,
            "dinner":    0.30,
        },
        4: {
            "breakfast":      0.25,
            "mid_morning":    0.15,
            "lunch":          0.35,
            "dinner":         0.25,
        },
        5: {
            "breakfast":      0.20,
            "mid_morning":    0.15,
            "lunch":          0.30,
            "evening_snack":  0.15,
            "dinner":         0.20,
        },
        6: {
            "breakfast":      0.20,
            "mid_morning":    0.10,
            "lunch":          0.25,
            "afternoon":      0.10,
            "evening_snack":  0.15,
            "dinner":         0.20,
        },
    }

    dist = distributions.get(meal_count, distributions[3])

    # For weight loss / diabetes: bigger breakfast, lighter dinner
    if "weight_loss" in goal or goal == "maintain":
        if meal_count >= 3:
            # Shift 5% from dinner to breakfast
            if "breakfast" in dist and "dinner" in dist:
                dist = dict(dist)
                dist["breakfast"] = round(dist["breakfast"] + 0.05, 2)
                dist["dinner"]    = round(dist["dinner"]    - 0.05, 2)

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
