from typing import Dict, List, Tuple
from nrs.models import Meal


def adjust_portions_to_targets(
    day_meals: List[Meal], targets: Dict[str, float]
) -> Tuple[List[Dict], Dict[str, float]]:

    total_kcal = sum(m.kcal for m in day_meals)
    scale = max(0.7, min(1.3, targets["kcal"] / total_kcal)) if total_kcal else 1.0

    adjusted = [
        {
            "name": m.name,
            "course": m.course,
            "portion_note": m.portion_desc,
            "kcal": round(m.kcal * scale),
            "carbs_g": round(m.carbs_g * scale, 1),
            "protein_g": round(m.protein_g * scale, 1),
            "fat_g": round(m.fat_g * scale, 1),
            "fiber_g": round(m.fiber_g * scale, 1),
            "sodium_mg": round(m.sodium_mg * scale),
            "gi": m.gi,
        }
        for m in day_meals
    ]

    summary = {
        "kcal": sum(m["kcal"] for m in adjusted),
        "carbs_g": round(sum(m["carbs_g"] for m in adjusted), 1),
        "protein_g": round(sum(m["protein_g"] for m in adjusted), 1),
        "fat_g": round(sum(m["fat_g"] for m in adjusted), 1),
        "fiber_g": round(sum(m["fiber_g"] for m in adjusted), 1),
        "sodium_mg": sum(m["sodium_mg"] for m in adjusted),
    }

    return adjusted, summary
