from typing import Dict, List
from models import Meal


def disease_rules(diseases: List[str]) -> Dict[str, Dict]:
    rules = {"hard": {}, "soft": {}}

    # -------------------------
    # 1) Diabetes (Type 2)
    # -------------------------
    if "diabetes" in diseases:
        rules["hard"]["per_meal_carb_cap_g"] = 55  # 45–60g/meal common cap
        rules["soft"]["prefer_low_gi"] = True
        rules["soft"]["min_fiber_g_day"] = 25
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["sugar", "sweet", "dessert", "sabudana", "juice", "fried"]
        )

    # -------------------------
    # 2) Hypertension
    # -------------------------
    if "hypertension" in diseases:
        rules["hard"]["sodium_day_max_mg"] = 1800
        rules["soft"]["avoid_pickles_papad"] = True
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["pickle", "papad", "salted", "chaat", "fry"]
        )

    # -------------------------
    # 3) Celiac Disease
    # -------------------------
    if "celiac" in diseases:
        rules["hard"].setdefault("exclude_allergens", []).append("gluten")

    # -------------------------
    # 4) PCOS / PCOD
    # -------------------------
    if "pcos" in diseases:
        rules["soft"]["prefer_low_gi"] = True
        rules["soft"]["higher_protein_ratio"] = True
        rules["soft"]["avoid_keywords"] = rules["soft"].get("avoid_keywords", []) + [
            "sugar",
            "sweet",
            "maida",
            "fried",
        ]

    # -------------------------
    # 5) Hypothyroidism
    # -------------------------
    if "hypothyroidism" in diseases:
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["soy", "soya", "soy milk"]
        )
        rules["soft"]["prefer_mild_processed"] = True

    # -------------------------
    # 6) Fatty Liver (NAFLD)
    # -------------------------
    if "fatty_liver" in diseases:
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["fried", "oil", "butter", "ghee", "cream"]
        )
        rules["soft"]["prefer_low_fat"] = True
        rules["soft"]["prefer_low_sugar"] = True

    # -------------------------
    # 7) Heart Disease / High Cholesterol
    # -------------------------
    if (
        "heart_disease" in diseases
        or "cholesterol" in diseases
        or "dyslipidemia" in diseases
    ):
        rules["soft"]["prefer_unsaturated_fats"] = True
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["fried", "samosa", "bhatura", "cream", "butter", "ghee"]
        )
        rules["hard"]["limit_saturated_fat_g"] = 15  # per day, rough

    # -------------------------
    # 8) CKD (Chronic Kidney Disease)
    # -------------------------
    if "ckd" in diseases:
        rules["hard"]["sodium_day_max_mg"] = 1500
        rules["hard"]["protein_cap_g_per_day"] = 50  # typical stage 3–4 guideline
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["dal", "rajma", "chole", "sambar", "paneer"]
        )

    # -------------------------
    # 9) GERD / Acidity
    # -------------------------
    if "gerd" in diseases or "acidity" in diseases:
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["spicy", "fried", "tomato", "chili", "coffee"]
        )
        rules["soft"]["prefer_low_spice"] = True

    # -------------------------
    # 10) Obesity (general weight mgmt)
    # -------------------------
    if "obesity" in diseases:
        rules["soft"]["prefer_low_kcal_density"] = True
        rules["soft"].setdefault("avoid_keywords", []).extend(
            ["fried", "sweets", "cream", "ghee"]
        )

    return rules


def is_meal_disease_suitable(meal: Meal, rules: Dict[str, Dict]) -> bool:
    try:
        hard = rules.get("hard", {})
        soft = rules.get("soft", {})

        name = meal.name.lower()

        # 1) Carb cap (diabetes)
        if "per_meal_carb_cap_g" in hard and meal.carbs_g > hard["per_meal_carb_cap_g"]:
            return False

        # 2) Sodium guard (HTN / CKD)
        if "sodium_day_max_mg" in hard and meal.sodium_mg > 700:
            return False

        # 3) Saturated fat limit (heart disease)
        if (
            "limit_saturated_fat_g" in hard
            and meal.fat_g > hard["limit_saturated_fat_g"]
        ):
            return False

        # 4) Protein cap (CKD)
        if (
            "protein_cap_g_per_day" in hard and meal.protein_g > 25
        ):  # rough per-meal guard
            return False

        # 5) Keyword-based avoid rules (soft rules)
        for kw in soft.get("avoid_keywords", []):
            if kw in name:
                return False

        return True

    except Exception:
        return False
