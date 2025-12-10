from typing import Dict, List
from models import Meal


def disease_rules(diseases: List[str]) -> Dict[str, Dict]:
    rules = {"hard": {}, "soft": {}}
    if "diabetes" in diseases:
        rules["hard"]["per_meal_carb_cap_g"] = 60
        rules["soft"]["prefer_low_gi"] = True
        rules["soft"]["min_fiber_g_day"] = 25
    if "hypertension" in diseases:
        rules["hard"]["sodium_day_max_mg"] = 1800
        rules["soft"]["avoid_pickles_papad"] = True
    if "celiac" in diseases:
        rules["hard"].setdefault("exclude_allergens", []).append("gluten")
    return rules


def is_meal_disease_suitable(meal: Meal, rules: Dict[str, Dict]) -> bool:
    try:
        hard = rules.get("hard", {})
        if "per_meal_carb_cap_g" in hard and meal.carbs_g > hard["per_meal_carb_cap_g"]:
            return False
        if "sodium_day_max_mg" in hard and meal.sodium_mg > 700:
            return False
        return True
    except Exception:
        return False
