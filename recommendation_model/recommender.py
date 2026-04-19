"""
recommendation_model/recommender.py
=====================================
Main recommendation engine.

Takes:
  - safe_foods_df    : output from FoodFilteringPipeline
  - recommendation_context : dict from FoodFilteringPipeline
  - goal, activity_level, meal_count : new user inputs

Produces:
  - HealthMetrics (all calculations)
  - 7-day meal plan
  - Health insights & tips
  - Exportable JSON / CSV
"""

import os
import sys
import json
import pandas as pd
from typing import Dict, List
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from recommendation_model.calculator import calculate_all, bmi_advice, HealthMetrics
from recommendation_model.meal_planner import (
    build_weekly_plan, build_daily_plan, check_nutritional_gaps
)
from utils.helpers import output_path, export_json, timestamp_str


GOAL_LABELS = {
    "weight_loss_aggressive": "Aggressive Weight Loss (~0.7 kg/week)",
    "weight_loss":            "Weight Loss (~0.5 kg/week)",
    "weight_loss_mild":       "Mild Weight Loss (~0.25 kg/week)",
    "maintain":               "Maintain Current Weight",
    "weight_gain_mild":       "Mild Weight Gain (~0.25 kg/week)",
    "weight_gain":            "Weight Gain (~0.5 kg/week)",
    "muscle_gain":            "Muscle Gain (Lean Bulk)",
}

ACTIVITY_LABELS = {
    "sedentary":         "Sedentary (desk job, little/no exercise)",
    "lightly_active":    "Lightly Active (light exercise 1-3 days/week)",
    "moderately_active": "Moderately Active (moderate exercise 3-5 days/week)",
    "very_active":       "Very Active (hard exercise 6-7 days/week)",
    "extra_active":      "Extra Active (very hard exercise + physical job)",
}


class DietRecommender:

    def __init__(self):
        pass

    def run(
        self,
        safe_foods_df:          pd.DataFrame,
        recommendation_context: Dict,
        goal:                   str,
        activity_level:         str,
        meal_count:             int = 3,
        seed:                   int = 42,
    ) -> Dict:
        """
        Main entry point.

        Parameters
        ----------
        safe_foods_df          : filtered food list from FoodFilteringPipeline
        recommendation_context : context dict from FoodFilteringPipeline
        goal                   : user goal key (e.g. "weight_loss")
        activity_level         : activity key (e.g. "moderately_active")
        meal_count             : 3, 4, 5, or 6 meals per day
        seed                   : random seed for reproducibility

        Returns
        -------
        Full recommendation dict including metrics, meal plan, insights, tips
        """
        ctx = recommendation_context

        # ── Parse user bio ─────────────────────────────────────────────────────
        try:
            age        = float(ctx.get("age", 30))
        except (ValueError, TypeError):
            age        = 30.0
        try:
            weight_kg  = float(ctx.get("weight_kg", 70))
        except (ValueError, TypeError):
            weight_kg  = 70.0
        try:
            height_cm  = float(ctx.get("height_cm", 170))
        except (ValueError, TypeError):
            height_cm  = 170.0

        sex            = str(ctx.get("sex", "male")).strip().lower()
        user_id        = ctx.get("user_id", "anonymous")
        name           = ctx.get("name", "User")

        # ── Run calculations ───────────────────────────────────────────────────
        metrics = calculate_all(
            age            = age,
            weight_kg      = weight_kg,
            height_cm      = height_cm,
            sex            = sex,
            activity_level = activity_level,
            goal           = goal,
            meal_count     = meal_count,
            has_diabetes       = bool(ctx.get("has_diabetes", False)),
            has_hypertension   = bool(ctx.get("has_hypertension", False)),
            has_kidney_disease = bool(ctx.get("has_kidney_disease", False)),
            has_heart_disease  = bool(ctx.get("has_heart_disease", False)),
            has_pcos           = bool(ctx.get("has_pcos", False)),
            has_obesity        = bool(ctx.get("has_obesity", False)),
            has_anemia         = bool(ctx.get("has_anemia", False)),
            is_vegetarian      = bool(ctx.get("is_vegetarian", False)),
            is_vegan           = bool(ctx.get("is_vegan", False)),
        )

        # ── Build 7-day meal plan ──────────────────────────────────────────────
        weekly_plan = build_weekly_plan(safe_foods_df, metrics, seed=seed)

        # ── Nutritional gap analysis ───────────────────────────────────────────
        day1_gaps    = check_nutritional_gaps(weekly_plan[0], metrics)
        overall_gaps = self._avg_gaps(weekly_plan, metrics)

        # ── Health insights ────────────────────────────────────────────────────
        insights = self._generate_insights(metrics, ctx)
        tips     = self._generate_tips(metrics, ctx, goal)

        # ── Weekly nutrition summary ───────────────────────────────────────────
        weekly_avg = self._weekly_average(weekly_plan)

        return {
            "user_id":          user_id,
            "name":             name,
            "timestamp":        datetime.now().isoformat(),
            "goal":             goal,
            "goal_label":       GOAL_LABELS.get(goal, goal),
            "activity_level":   activity_level,
            "activity_label":   ACTIVITY_LABELS.get(activity_level, activity_level),
            "meal_count":       meal_count,

            # All health calculations
            "metrics":          metrics,

            # 7-day plan
            "weekly_plan":      weekly_plan,

            # Analysis
            "weekly_avg":       weekly_avg,
            "nutritional_gaps": overall_gaps,
            "day1_gaps":        day1_gaps,
            "insights":         insights,
            "tips":             tips,

            # Input context (for reference)
            "recommendation_context": ctx,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _avg_gaps(self, weekly_plan: List[Dict], metrics: HealthMetrics) -> List[str]:
        """Check average daily gaps across the week."""
        avg_plan = {
            "totals": {
                "calories":  sum(d["totals"]["calories"]  for d in weekly_plan) / 7,
                "protein_g": sum(d["totals"]["protein_g"] for d in weekly_plan) / 7,
                "carbs_g":   sum(d["totals"]["carbs_g"]   for d in weekly_plan) / 7,
                "fat_g":     sum(d["totals"]["fat_g"]     for d in weekly_plan) / 7,
                "fiber_g":   sum(d["totals"]["fiber_g"]   for d in weekly_plan) / 7,
                "sodium_mg": sum(d["totals"]["sodium_mg"] for d in weekly_plan) / 7,
            },
            "targets": weekly_plan[0]["targets"],
        }
        return check_nutritional_gaps(avg_plan, metrics)

    def _weekly_average(self, weekly_plan: List[Dict]) -> Dict:
        """Compute average daily totals across 7 days."""
        keys = ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg"]
        return {
            k: round(sum(d["totals"][k] for d in weekly_plan) / 7, 1)
            for k in keys
        }

    def _generate_insights(self, metrics: HealthMetrics, ctx: Dict) -> List[str]:
        """Generate personalised health insights based on metrics."""
        insights = []

        # BMI insight
        insights.append(
            f"BMI: {metrics.bmi} ({metrics.bmi_category}). "
            + bmi_advice(metrics)
        )

        # Calorie context
        insights.append(
            f"Your Basal Metabolic Rate is {metrics.bmr:.0f} kcal/day — "
            f"calories your body burns at complete rest."
        )
        insights.append(
            f"Your TDEE is {metrics.tdee:.0f} kcal/day — "
            f"total daily burn at your activity level "
            f"({ACTIVITY_LABELS.get(metrics.activity_level,'')})."
        )
        insights.append(
            f"Your personalised calorie target is {metrics.target_calories:.0f} kcal/day "
            f"to {GOAL_LABELS.get(metrics.goal, metrics.goal).lower()}."
        )

        # Macro insight
        insights.append(
            f"Daily macro targets — Protein: {metrics.protein_g}g | "
            f"Carbs: {metrics.carbs_g}g | Fat: {metrics.fat_g}g."
        )

        # IBW
        insights.append(
            f"Ideal body weight (Devine formula): {metrics.ibw_kg} kg. "
            f"Your current weight is {metrics.weight_kg} kg."
        )

        # Water
        insights.append(
            f"Recommended daily water intake: {metrics.water_ml:.0f} ml "
            f"({metrics.water_ml/1000:.1f} litres)."
        )

        # Disease-specific
        if ctx.get("has_diabetes"):
            insights.append(
                "Diabetes: Prioritise low-GI foods (GI ≤ 55). "
                "Eat small frequent meals. Avoid refined carbs and sugary drinks."
            )
        if ctx.get("has_hypertension"):
            insights.append(
                f"Hypertension: Sodium target {metrics.sodium_mg} mg/day. "
                "Follow DASH principles — increase fruits, vegetables, and whole grains."
            )
        if ctx.get("has_kidney_disease"):
            insights.append(
                "Kidney Disease: Protein is restricted to protect kidney function. "
                f"Potassium limit: {metrics.potassium_mg} mg/day. "
                f"Water limit: {metrics.water_ml:.0f} ml/day. "
                "Strict medical supervision required."
            )
        if ctx.get("has_pcos"):
            insights.append(
                "PCOS: Low-GI anti-inflammatory diet is most beneficial. "
                "Limit processed foods, dairy (some benefit), and refined carbs."
            )
        if ctx.get("has_anemia"):
            insights.append(
                f"Anaemia: Iron target {metrics.iron_mg} mg/day. "
                "Pair iron-rich foods with vitamin C to boost absorption. "
                "Avoid tea/coffee within 1 hour of meals."
            )
        if ctx.get("has_gout"):
            insights.append(
                "Gout: Avoid organ meats, shellfish, and high-purine foods. "
                "Stay well hydrated. Limit alcohol and fructose."
            )
        if ctx.get("is_vegan"):
            insights.append(
                "Vegan diet: Monitor B12, iron, zinc, calcium, and omega-3 carefully. "
                "Consider supplements for B12 and Vitamin D."
            )

        return insights

    def _generate_tips(
        self, metrics: HealthMetrics, ctx: Dict, goal: str
    ) -> List[str]:
        """Generate actionable daily tips."""
        tips = []

        if "weight_loss" in goal:
            tips += [
                "Eat slowly — it takes 20 minutes for satiety signals to reach your brain.",
                "Use smaller plates to naturally reduce portion sizes.",
                "Drink a glass of water before each meal to reduce hunger.",
                "Prioritise protein at every meal — it keeps you fuller for longer.",
                "Avoid liquid calories (juice, soda, sweetened chai).",
            ]
        elif goal == "muscle_gain":
            tips += [
                "Eat protein within 30-60 minutes after strength training.",
                "Spread protein intake evenly across all meals for optimal synthesis.",
                "Don't skip meals — muscle gain requires consistent calorie surplus.",
                "Prioritise sleep — 80% of growth hormone is released during deep sleep.",
            ]
        elif goal == "weight_gain" or goal == "weight_gain_mild":
            tips += [
                "Add calorie-dense whole foods: nuts, avocado, whole grains, paneer.",
                "Eat every 3-4 hours and include a high-calorie pre-bedtime snack.",
                "Don't drink water right before meals — it can suppress appetite.",
            ]
        else:  # maintain
            tips += [
                "Consistency is key — stick to your meal timings daily.",
                "Log your food once a week to stay aware of portion creep.",
            ]

        # Universal tips
        tips += [
            f"Aim for {metrics.fiber_g}g fibre/day — include vegetables, dals, and whole grains.",
            f"Target {metrics.water_ml/1000:.1f} litres of water daily, more if exercising.",
            "Include a source of colour at every meal — red/orange/green vegetables.",
            "Limit ultra-processed foods — they are high in sodium, sugar, and unhealthy fats.",
            "Plan meals in advance to avoid last-minute poor food choices.",
        ]

        if ctx.get("is_vegetarian") or ctx.get("is_vegan"):
            tips.append(
                "Combine plant proteins at each meal "
                "(e.g. dal + rice, chapati + rajma) for a complete amino acid profile."
            )

        return tips

    # ── Export ────────────────────────────────────────────────────────────────

    def save_output(self, result: Dict) -> Dict:
        """
        Save recommendation output.
        Same update-vs-create logic as FoodFilteringPipeline:
        - Same user_id → overwrite existing files
        - New user_id  → create new files
        """
        import os as _os

        uid       = result["user_id"]
        json_file = output_path(f"{uid}_diet_plan.json")
        csv_file  = output_path(f"{uid}_diet_plan.csv")
        is_update = _os.path.exists(json_file)

        # ── Build flat CSV: one row per meal per day ──────────────────────────
        rows = []
        for day in result["weekly_plan"]:
            day_name = day.get("day_name", f"Day {day['day']}")
            for slot, meal_data in day["meals"].items():
                for food in meal_data["foods"]:
                    rows.append({
                        "day":         day_name,
                        "meal_slot":   slot,
                        "food_name":   food["food_name"],
                        "category":    food["category"],
                        "portion_g":   food["portion_g"],
                        "calories":    food["calories"],
                        "protein_g":   food["protein_g"],
                        "carbs_g":     food["carbs_g"],
                        "fat_g":       food["fat_g"],
                        "fiber_g":     food["fiber_g"],
                        "sodium_mg":   food["sodium_mg"],
                    })

        csv_df = pd.DataFrame(rows)
        csv_df.to_csv(csv_file, index=False)

        # ── Build JSON ────────────────────────────────────────────────────────
        metrics = result["metrics"]
        json_payload = {
            "user_id":       result["user_id"],
            "name":          result["name"],
            "timestamp":     result["timestamp"],
            "goal":          result["goal_label"],
            "activity":      result["activity_label"],
            "meal_count":    result["meal_count"],
            "metrics": {
                "bmi":             metrics.bmi,
                "bmi_category":    metrics.bmi_category,
                "bmr_kcal":        metrics.bmr,
                "tdee_kcal":       metrics.tdee,
                "target_kcal":     metrics.target_calories,
                "ibw_kg":          metrics.ibw_kg,
                "protein_g":       metrics.protein_g,
                "carbs_g":         metrics.carbs_g,
                "fat_g":           metrics.fat_g,
                "fiber_g":         metrics.fiber_g,
                "sodium_mg":       metrics.sodium_mg,
                "water_ml":        metrics.water_ml,
                "calcium_mg":      metrics.calcium_mg,
                "iron_mg":         metrics.iron_mg,
                "vitamin_c_mg":    metrics.vitamin_c_mg,
                "vitamin_d_iu":    metrics.vitamin_d_iu,
                "potassium_mg":    metrics.potassium_mg,
            },
            "weekly_plan":       result["weekly_plan"],
            "weekly_avg":        result["weekly_avg"],
            "nutritional_gaps":  result["nutritional_gaps"],
            "insights":          result["insights"],
            "tips":              result["tips"],
        }
        export_json(json_payload, json_file)

        return {
            "json":      json_file,
            "csv":       csv_file,
            "is_update": is_update,
        }
