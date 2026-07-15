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
    build_weekly_plan,
    build_daily_plan,
    check_nutritional_gaps,
)
from recommendation_model.feedback import compute_adaptive_temperature
from utils.helpers import output_path, export_json, timestamp_str

GOAL_LABELS = {
    "weight_loss_aggressive": "Aggressive Weight Loss (~0.7 kg/week)",
    "weight_loss": "Weight Loss (~0.5 kg/week)",
    "weight_loss_mild": "Mild Weight Loss (~0.25 kg/week)",
    "maintain": "Maintain Current Weight",
    "weight_gain_mild": "Mild Weight Gain (~0.25 kg/week)",
    "weight_gain": "Weight Gain (~0.5 kg/week)",
    "muscle_gain": "Muscle Gain (Lean Bulk)",
}

ACTIVITY_LABELS = {
    "sedentary": "Sedentary (desk job, little/no exercise)",
    "lightly_active": "Lightly Active (light exercise 1-3 days/week)",
    "moderately_active": "Moderately Active (moderate exercise 3-5 days/week)",
    "very_active": "Very Active (hard exercise 6-7 days/week)",
    "extra_active": "Extra Active (very hard exercise + physical job)",
}


class DietRecommender:

    def __init__(self):
        pass

    def run(
        self,
        safe_foods_df: pd.DataFrame,
        recommendation_context: Dict,
        goal: str,
        activity_level: str,
        meal_count: int = 3,
        region_zone: str = "any",
        seed: int = 42,
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
            age = float(ctx.get("age", 30))
        except (ValueError, TypeError):
            age = 30.0
        try:
            weight_kg = float(ctx.get("weight_kg", 70))
        except (ValueError, TypeError):
            weight_kg = 70.0
        try:
            height_cm = float(ctx.get("height_cm", 170))
        except (ValueError, TypeError):
            height_cm = 170.0

        sex = str(ctx.get("sex", "male")).strip().lower()
        user_id = ctx.get("user_id", "anonymous")
        name = ctx.get("name", "User")

        # ── Run calculations ───────────────────────────────────────────────────
        metrics = calculate_all(
            age=age,
            weight_kg=weight_kg,
            height_cm=height_cm,
            sex=sex,
            activity_level=activity_level,
            goal=goal,
            meal_count=meal_count,
            has_diabetes=bool(ctx.get("has_diabetes", False)),
            has_hypertension=bool(ctx.get("has_hypertension", False)),
            has_kidney_disease=bool(ctx.get("has_kidney_disease", False)),
            has_heart_disease=bool(ctx.get("has_heart_disease", False)),
            has_pcos=bool(ctx.get("has_pcos", False)),
            has_obesity=bool(ctx.get("has_obesity", False)),
            has_anemia=bool(ctx.get("has_anemia", False)),
            is_vegetarian=bool(ctx.get("is_vegetarian", False)),
            is_vegan=bool(ctx.get("is_vegan", False)),
        )

        # ── Build 7-day meal plan ──────────────────────────────────────────────
        from recommendation_model.meal_planner import filter_by_region

        regional_df = filter_by_region(safe_foods_df, region_zone)
        festive_mode = ctx.get("festive_mode", None)
        diet_pref = ctx.get("dietary_preference", "none") or "none"
        # Seed based on user_id + today's date → different plan each day, reproducible per day
        _seed_str = f"{user_id}{datetime.now().strftime('%Y-%m-%d')}"
        import hashlib as _hl

        _seed = int(_hl.md5(_seed_str.encode()).hexdigest(), 16) % (2**31)
        # Adaptive temperature: falls back to 12.0 automatically if there's
        # no MongoDB handle, no user_id, or fewer than 5 past ratings.
        try:
            from utils import db as mdb

            adaptive_temp = compute_adaptive_temperature(user_id, mdb.db)
        except Exception:
            adaptive_temp = 12.0

        weekly_plan = build_weekly_plan(
            regional_df,
            metrics,
            seed=_seed,
            preferred_region=region_zone,
            festive_mode=festive_mode,
            diet_pref=diet_pref,
            temperature=adaptive_temp,
        )

        # ── Nutritional gap analysis ───────────────────────────────────────────
        day1_gaps = check_nutritional_gaps(weekly_plan[0], metrics)
        overall_gaps = self._avg_gaps(weekly_plan, metrics)

        # ── Health insights ────────────────────────────────────────────────────
        insights = self._generate_insights(metrics, ctx)
        tips = self._generate_tips(metrics, ctx, goal)

        # ── Weekly nutrition summary ───────────────────────────────────────────
        weekly_avg = self._weekly_average(weekly_plan)

        return {
            "user_id": user_id,
            "name": name,
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "region_zone": region_zone,
            "goal_label": GOAL_LABELS.get(goal, goal),
            "activity_level": activity_level,
            "activity_label": ACTIVITY_LABELS.get(activity_level, activity_level),
            "meal_count": meal_count,
            # All health calculations
            "metrics": metrics,
            # 7-day plan
            "weekly_plan": weekly_plan,
            # Analysis
            "weekly_avg": weekly_avg,
            "nutritional_gaps": overall_gaps,
            "day1_gaps": day1_gaps,
            "insights": insights,
            "tips": tips,
            # Input context (for reference)
            "recommendation_context": ctx,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _avg_gaps(self, weekly_plan: List[Dict], metrics: HealthMetrics) -> List[str]:
        """Check average daily gaps across the week."""
        avg_plan = {
            "totals": {
                "calories": sum(d["totals"]["calories"] for d in weekly_plan) / 7,
                "protein_g": sum(d["totals"]["protein_g"] for d in weekly_plan) / 7,
                "carbs_g": sum(d["totals"]["carbs_g"] for d in weekly_plan) / 7,
                "fat_g": sum(d["totals"]["fat_g"] for d in weekly_plan) / 7,
                "fiber_g": sum(d["totals"]["fiber_g"] for d in weekly_plan) / 7,
                "sodium_mg": sum(d["totals"]["sodium_mg"] for d in weekly_plan) / 7,
            },
            "targets": weekly_plan[0]["targets"],
        }
        return check_nutritional_gaps(avg_plan, metrics)

    def _weekly_average(self, weekly_plan: List[Dict]) -> Dict:
        """Compute average daily totals across 7 days."""
        keys = ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg"]
        return {k: round(sum(d["totals"][k] for d in weekly_plan) / 7, 1) for k in keys}

    def _generate_insights(self, metrics: HealthMetrics, ctx: Dict) -> List[str]:
        """Generate rich, personalised health insights from all available metrics."""
        ins = []
        w = metrics.weight_kg
        h = metrics.height_cm / 100
        bmi = metrics.bmi
        ibw = metrics.ibw_kg
        sex = metrics.sex.lower()

        # ── 1. BMI with clinical context ─────────────────────────────────────
        wt_gap = round(w - ibw, 1)
        gap_str = (
            f" That is {abs(wt_gap)} kg {'above' if wt_gap > 0 else 'below'} "
            f"your ideal weight of {ibw} kg."
            if abs(wt_gap) > 1
            else " You are very close to your ideal weight — great work!"
        )
        ins.append(
            f"📊 BMI: {bmi} ({metrics.bmi_category}).{gap_str} " + bmi_advice(metrics)
        )

        # ── 2. Energy balance explained simply ───────────────────────────────
        deficit = round(metrics.target_calories - metrics.tdee, 0)
        deficit_str = (
            f"a deficit of {abs(deficit):.0f} kcal/day (≈ {abs(deficit)/7700*7:.2f} kg/week loss)"
            if deficit < -50
            else (
                f"a surplus of {deficit:.0f} kcal/day (≈ {deficit/7700*7:.2f} kg/week gain)"
                if deficit > 50
                else "maintenance — matching your energy expenditure exactly"
            )
        )
        ins.append(
            f"🔥 Energy Balance: BMR {metrics.bmr:.0f} kcal (at rest) → "
            f"TDEE {metrics.tdee:.0f} kcal (with activity) → "
            f"Target {metrics.target_calories:.0f} kcal/day ({deficit_str})."
        )

        # ── 3. Macro breakdown with real-food equivalents ────────────────────
        ins.append(
            f"🥗 Daily Macros: Protein {metrics.protein_g}g "
            f"(≈ {round(metrics.protein_g/25)} cups cooked dal or "
            f"{round(metrics.protein_g/20)} eggs) | "
            f"Carbs {metrics.carbs_g}g "
            f"(≈ {round(metrics.carbs_g/30)} medium rotis or "
            f"{round(metrics.carbs_g/28)} cups cooked rice) | "
            f"Fat {metrics.fat_g}g "
            f"(≈ {round(metrics.fat_g/5)} tsp ghee/oil equivalent)."
        )

        # ── 4. Protein adequacy check ─────────────────────────────────────────
        prot_per_kg = round(metrics.protein_g / w, 2)
        prot_verdict = (
            "✅ Excellent — supports muscle repair and satiety."
            if prot_per_kg >= 1.6
            else (
                "✅ Adequate for general health."
                if prot_per_kg >= 1.0
                else "⚠ Slightly low — aim to include a protein source at every meal."
            )
        )
        ins.append(
            f"💪 Protein adequacy: {metrics.protein_g}g/day = "
            f"{prot_per_kg}g per kg body weight. {prot_verdict}"
        )

        # ── 5. Hydration target ───────────────────────────────────────────────
        ins.append(
            f"💧 Hydration target: {metrics.water_ml:.0f} ml/day "
            f"({metrics.water_ml/1000:.1f} L). "
            f"Practical split: {round(metrics.water_ml/250)} glasses of 250 ml. "
            "Increase by 200–300 ml for every 30 min of exercise."
        )

        # ── 6. Micronutrient focus ─────────────────────────────────────────────
        micros = []
        if ctx.get("has_anemia") or (sex not in ("male", "m") and metrics.iron_mg > 18):
            micros.append(f"iron {metrics.iron_mg:.0f} mg (pair with vitamin C foods)")
        if metrics.calcium_mg > 1000:
            micros.append(
                f"calcium {metrics.calcium_mg:.0f} mg (curd, ragi, til seeds)"
            )
        if ctx.get("is_vegan") or ctx.get("is_vegetarian"):
            micros.append("vitamin B12 (supplement recommended for vegans)")
        if micros:
            ins.append(f"🦴 Key micronutrients to monitor: {', '.join(micros)}.")

        # ── 7. Fibre target ───────────────────────────────────────────────────
        ins.append(
            f"🌾 Fibre target: {metrics.fiber_g}g/day. "
            "Best sources: sabzi at every meal, whole dal, fruits with skin, oats, jowar/bajra. "
            "Adequate fibre feeds gut bacteria, reduces cholesterol, and blunts blood sugar spikes."
        )

        # ── 8. Disease-specific — detailed and actionable ────────────────────
        if ctx.get("has_diabetes"):
            ins.append(
                "🩺 Diabetes Management: Your carb target is intentionally lowered. "
                f"Keep each meal under {round(metrics.carbs_g/3)}g carbs. "
                "Choose low-GI staples: oats, barley, whole dals, hand-pounded rice. "
                "Avoid fruit juices — eat whole fruit instead. "
                "Post-meal walks of even 10 min significantly reduce glucose spikes."
            )
        if ctx.get("has_hypertension"):
            ins.append(
                f"🩺 Blood Pressure: Sodium is capped at {metrics.sodium_mg} mg/day "
                f"(≈ {round(metrics.sodium_mg/2300)} tsp salt). "
                "Increase potassium-rich foods: banana, tomato, spinach, coconut water. "
                "The DASH diet pattern — which this plan follows — lowers BP by 8–14 mmHg on average."
            )
        if ctx.get("has_kidney_disease"):
            ins.append(
                f"🩺 Kidney Disease: Protein restricted to protect GFR. "
                f"Potassium ≤ {metrics.potassium_mg} mg/day — avoid: banana, orange, tomato in excess. "
                f"Phosphorus: avoid processed/packaged foods. "
                f"Fluid: {metrics.water_ml:.0f} ml/day strictly. "
                "Follow up with nephrologist before any dietary change."
            )
        if ctx.get("has_pcos"):
            ins.append(
                "🩺 PCOS: Insulin resistance is the core driver. "
                "Low-GI, high-fibre, anti-inflammatory foods are most effective. "
                "Include: flaxseed, fenugreek, turmeric, cruciferous vegetables. "
                "Avoid: refined carbs, sweetened dairy, processed snacks."
            )
        if ctx.get("has_gout"):
            ins.append(
                "🩺 Gout: Avoid high-purine foods — organ meats, shellfish, dried pulses in excess. "
                "Stay well hydrated (helps uric acid excretion). "
                "Limit fructose (packaged juices, soda). Cherry extract has emerging evidence."
            )
        if ctx.get("has_heart_disease"):
            ins.append(
                "🩺 Heart Disease: Saturated fat is capped. "
                "Prioritise omega-3 sources: flaxseed, walnuts, fatty fish (if not vegetarian). "
                "Include: oats, barley, amla, garlic, olive oil. "
                "Avoid: vanaspati, trans fats, high-sodium pickles."
            )
        if ctx.get("has_thyroid"):
            ins.append(
                "🩺 Thyroid: Avoid raw cruciferous vegetables in large amounts (goitrogens). "
                "Ensure adequate iodine and selenium. "
                "Take thyroid medication 30–60 min before breakfast for optimal absorption."
            )
        if ctx.get("is_vegan"):
            ins.append(
                "🌱 Vegan diet: Critical nutrients to supplement: B12 (essential), "
                "Vitamin D3 (algae-based), omega-3 DHA/EPA (algae oil), zinc, iodine. "
                "Pair iron-rich foods (dark greens, seeds) with vitamin C at every meal."
            )

        return ins

    def _generate_tips(self, metrics: HealthMetrics, ctx: Dict, goal: str) -> List[str]:
        """Generate specific, science-backed, actionable daily tips."""
        tips = []
        sex = metrics.sex.lower()
        w = metrics.weight_kg

        # ── Goal-specific tips ────────────────────────────────────────────────
        if "weight_loss" in goal:
            tips += [
                "🍽 Eat in this order: salad/raw veg → dal/protein → rotis/rice. "
                "This sequence lowers post-meal glucose by up to 30%.",
                "⏱ Eat slowly — satiety signals take 15–20 min. Put your fork/spoon "
                "down between bites and aim for 20-min mealtimes.",
                "🥤 Drink 400 ml water 20–30 min before lunch and dinner. "
                "Studies show this reduces meal size by 13% on average.",
                "🥚 Front-load protein at breakfast — it reduces evening snack cravings "
                "by up to 25% compared to carb-heavy breakfasts.",
                "🚫 Cut liquid calories first: 1 glass sweetened chai = 80–120 kcal. "
                "Switch to plain chai, black coffee, or nimbu pani (no sugar).",
                "📱 Take a photo of every meal for 2 weeks — visual food logs "
                "increase dietary awareness better than calorie counting apps.",
            ]
        elif goal == "muscle_gain":
            tips += [
                f"💪 Hit {metrics.protein_g:.0f}g protein daily — that is your most "
                f"important number. Spread across {metrics.meal_calories.__len__()} meals.",
                "⏰ Consume 20–40g protein within 2 hours post-workout for optimal "
                "muscle protein synthesis (the 'anabolic window').",
                "🌙 Casein before bed: 1 cup curd or 200 ml milk before sleep provides "
                "slow-release protein for overnight muscle repair.",
                "💤 Sleep 8 hours minimum. GH secretion peaks in deep sleep — "
                "inadequate sleep reduces muscle gain by up to 60%.",
                "📈 Progressive overload: increase weight or reps every 1–2 weeks. "
                "Diet alone cannot build muscle without progressive stimulus.",
            ]
        elif goal in ("weight_gain", "weight_gain_mild"):
            tips += [
                "📅 Never skip a meal — consistency of calorie intake matters more "
                "than any single high-calorie meal.",
                "🥜 Add calorie-dense whole foods to every meal: "
                "ghee on dal, nuts in curd, peanut butter on toast.",
                "🌙 High-calorie bedtime snack: warm milk + 2 dates + handful of nuts "
                "= ~300 kcal with protein and healthy fats.",
                f"📊 You need {metrics.target_calories:.0f} kcal/day. "
                "Most people who struggle to gain weight are unintentionally eating 300–500 kcal less.",
            ]
        else:  # maintain
            tips += [
                "⚖ Weigh yourself once a week, same morning, same time — fasted. "
                "Daily fluctuations of 1–2 kg from water are normal and misleading.",
                "📅 Practice 80/20 eating: follow your plan 80% of the time. "
                "One meal off-track will not reverse progress.",
                "🔄 Rotate your protein sources weekly — variety feeds different gut bacteria "
                "and prevents micronutrient gaps.",
            ]

        # ── Medical condition tips ────────────────────────────────────────────
        if ctx.get("has_diabetes"):
            tips += [
                "🩸 Walk for 10 min after every main meal — this single habit reduces "
                "post-meal glucose by 12–22% (proven in Indian T2D studies).",
                "🕐 Eat at consistent times daily — meal timing affects insulin sensitivity. "
                "Irregular mealtimes worsen glycaemic control.",
            ]
        if ctx.get("has_hypertension"):
            tips += [
                "🧂 Taste food before adding salt — most Indian cooking has enough. "
                f"Your daily limit is {metrics.sodium_mg} mg (≈ {round(metrics.sodium_mg/400)} pinches).",
            ]
        if ctx.get("has_anemia"):
            tips.append(
                f"🫀 Consume {metrics.iron_mg:.0f} mg iron/day. "
                "Have amla, tomato, or lemon with iron-rich meals (vitamin C triples absorption). "
                "Avoid tea/coffee for 1 hour around meals."
            )
        if ctx.get("has_pcos"):
            tips.append(
                "🌿 Add 1 tsp fenugreek seeds (soaked overnight) to morning water — "
                "reduces fasting blood sugar and improves insulin sensitivity in PCOS."
            )

        # ── Universal evidence-based tips ─────────────────────────────────────
        tips += [
            f"🌾 Fibre goal: {metrics.fiber_g}g/day. Practical guide: "
            "1 katori dal = 6g, 1 medium apple = 4g, 1 cup cooked sabzi = 3–5g. "
            "Spread across all meals.",
            f"💧 Hydration: {metrics.water_ml/1000:.1f}L/day. "
            "Urine colour check: pale straw = hydrated, dark yellow = drink more.",
            "🥦 Eat at least 3 different vegetable colours daily — "
            "each colour indicates different protective phytonutrients.",
            "🛒 Read nutrition labels: reject products with more than 5g added sugar "
            "or 'hydrogenated oil' / 'vanaspati' in the first 3 ingredients.",
            "🍱 Meal prep Sunday: cook dals, cut vegetables, portion grains. "
            "Prepared food reduces impulsive eating by 60%.",
            "📵 No screens while eating — distracted eating increases meal size by 10–25%. "
            "Mindful eating improves satiety and reduces bingeing.",
        ]

        # ── Diet-type specific ────────────────────────────────────────────────
        if ctx.get("is_vegan") or ctx.get("is_vegetarian"):
            tips.append(
                "🌱 Complete protein formula: dal + grain at the same meal "
                "(rajma-rice, dal-roti, chhole-bhature) provides all essential amino acids."
            )
        if sex not in ("male", "m"):
            tips.append(
                "🌸 Hormonal health: Include 1–2 tbsp flaxseed powder daily (phytoestrogens). "
                "Adequate iron and calcium are critical — both are commonly deficient in Indian women."
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

        uid = result["user_id"]
        json_file = output_path(f"{uid}_diet_plan.json")
        csv_file = output_path(f"{uid}_diet_plan.csv")
        is_update = _os.path.exists(json_file)

        # ── Build flat CSV: one row per meal per day ──────────────────────────
        rows = []
        for day in result["weekly_plan"]:
            day_name = day.get("day_name", f"Day {day['day']}")
            for slot, meal_data in day["meals"].items():
                for food in meal_data["foods"]:
                    rows.append(
                        {
                            "day": day_name,
                            "meal_slot": slot,
                            "food_name": food["food_name"],
                            "category": food["category"],
                            "portion_g": food["portion_g"],
                            "calories": food["calories"],
                            "protein_g": food["protein_g"],
                            "carbs_g": food["carbs_g"],
                            "fat_g": food["fat_g"],
                            "fiber_g": food["fiber_g"],
                            "sodium_mg": food["sodium_mg"],
                        }
                    )

        csv_df = pd.DataFrame(rows)
        csv_df.to_csv(csv_file, index=False)

        # ── Build JSON ────────────────────────────────────────────────────────
        metrics = result["metrics"]
        json_payload = {
            "user_id": result["user_id"],
            "name": result["name"],
            "timestamp": result["timestamp"],
            "goal": result["goal_label"],
            "activity": result["activity_label"],
            "meal_count": result["meal_count"],
            "metrics": {
                "bmi": metrics.bmi,
                "bmi_category": metrics.bmi_category,
                "bmr_kcal": metrics.bmr,
                "tdee_kcal": metrics.tdee,
                "target_kcal": metrics.target_calories,
                "ibw_kg": metrics.ibw_kg,
                "protein_g": metrics.protein_g,
                "carbs_g": metrics.carbs_g,
                "fat_g": metrics.fat_g,
                "fiber_g": metrics.fiber_g,
                "sodium_mg": metrics.sodium_mg,
                "water_ml": metrics.water_ml,
                "calcium_mg": metrics.calcium_mg,
                "iron_mg": metrics.iron_mg,
                "vitamin_c_mg": metrics.vitamin_c_mg,
                "vitamin_d_iu": metrics.vitamin_d_iu,
                "potassium_mg": metrics.potassium_mg,
            },
            "weekly_plan": result["weekly_plan"],
            "weekly_avg": result["weekly_avg"],
            "nutritional_gaps": result["nutritional_gaps"],
            "insights": result["insights"],
            "tips": result["tips"],
        }
        export_json(json_payload, json_file)

        return {
            "json": json_file,
            "csv": csv_file,
            "is_update": is_update,
        }
