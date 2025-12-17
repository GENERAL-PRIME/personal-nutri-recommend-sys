from typing import Dict
from nrs.models import Meal


def score_meal(meal: Meal, rules: Dict[str, Dict]) -> float:
    prefer_low_gi = rules.get("soft", {}).get("prefer_low_gi", False)
    score = 0.0

    score += meal.protein_g * 0.40
    score += meal.fiber_g * 0.20
    score -= meal.sodium_mg * 0.001
    score -= meal.cost_score * 0.05
    score -= meal.prep_time_min * 0.02
    score += (25 - min(meal.gi, 80)) * (0.15 if prefer_low_gi else 0.05)

    return score
