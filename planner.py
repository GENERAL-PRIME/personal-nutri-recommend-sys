from typing import Dict, List, Tuple
from models import Meal
from allergies import build_allergen_ontology, is_meal_allergy_safe
from diseases import is_meal_disease_suitable


def _diet_gate(meal: Meal, requested: str) -> bool:
    if requested == "jain":
        return meal.diet_type == "jain" or "jain_safe" in meal.tags
    if requested == "veg":
        return meal.veg_type == "veg"
    if requested == "eggetarian":
        return meal.diet_type in ("veg", "eggetarian")
    if requested == "nonveg":
        return True
    return True


def _score_meal(meal: Meal, rules: Dict[str, Dict]) -> float:
    prefer_low_gi = rules.get("soft", {}).get("prefer_low_gi", False)
    score = 0.0
    score += meal.protein_g * 0.5
    score += (25 - min(meal.gi, 75)) * (0.2 if prefer_low_gi else 0.05)
    score += meal.fiber_g * 0.3
    score -= (meal.sodium_mg / 100.0) * 0.2
    score -= (meal.cost_score - 1) * 0.1
    score -= (meal.prep_time_min / 10.0) * 0.1
    return score


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def _dislikes_gate(meal: Meal, disliked: list[str] | None) -> bool:
    if not disliked:
        return True
    name = _norm(meal.name)
    tagset = {_norm(t) for t in meal.tags}
    for item in disliked:
        k = _norm(item)
        # block if keyword appears in meal name or exact tag match
        if k and (k in name or k in tagset):
            return False
    return True


def select_meals_for_day(
    meals: List[Meal],
    rules: Dict[str, Dict],
    allergies: List[str],
    diet_type: str,
    meal_frequency: int,
    disliked_foods: list[str] | None = None,
) -> List[Meal]:

    ontology = build_allergen_ontology()
    candidates = [
        m
        for m in meals
        if _diet_gate(m, diet_type)
        and _dislikes_gate(m, disliked_foods)
        and is_meal_allergy_safe(m, allergies, ontology)
        and is_meal_disease_suitable(m, rules)
    ]

    by_course: Dict[str, List[Meal]] = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snack": [],
    }
    for m in candidates:
        by_course[m.course].append(m)
    for c in by_course:
        by_course[c].sort(key=lambda x: _score_meal(x, rules), reverse=True)

    course_order = ["breakfast", "lunch", "dinner", "snack", "snack"]
    plan: List[Meal] = []
    for c in course_order[: max(3, min(5, meal_frequency))]:
        if by_course[c]:
            plan.append(by_course[c][0])
    return plan


def adjust_portions_to_targets(
    day_meals: List[Meal], targets: Dict[str, float]
) -> Tuple[List[Dict], Dict[str, float]]:
    total_kcal = sum(m.kcal for m in day_meals)
    scale = max(0.7, min(1.3, targets["kcal"] / total_kcal)) if total_kcal else 1.0
    adjusted = []
    for m in day_meals:
        adjusted.append(
            {
                "name": m.name,
                "course": m.course,
                "portion_note": f"{scale:.1f}× portion",
                "kcal": round(m.kcal * scale),
                "carbs_g": round(m.carbs_g * scale, 1),
                "protein_g": round(m.protein_g * scale, 1),
                "fat_g": round(m.fat_g * scale, 1),
                "fiber_g": round(m.fiber_g * scale, 1),
                "sodium_mg": round(m.sodium_mg * scale),
                "gi": m.gi,
            }
        )
    summary = {
        "kcal": sum(a["kcal"] for a in adjusted),
        "carbs_g": round(sum(a["carbs_g"] for a in adjusted), 1),
        "protein_g": round(sum(a["protein_g"] for a in adjusted), 1),
        "fat_g": round(sum(a["fat_g"] for a in adjusted), 1),
        "fiber_g": round(sum(a["fiber_g"] for a in adjusted), 1),
        "sodium_mg": sum(a["sodium_mg"] for a in adjusted),
    }
    return adjusted, summary
