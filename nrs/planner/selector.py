import random
from typing import Dict, List, Tuple
from nrs.models import Meal
from nrs.allergies import build_allergen_ontology, is_meal_allergy_safe
from nrs.diseases import is_meal_disease_suitable

from nrs.planner.diet import diet_gate
from nrs.planner.dislikes import dislikes_gate
from nrs.planner.scoring import score_meal


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
        if diet_gate(m, diet_type)
        and dislikes_gate(m, disliked_foods)
        and is_meal_allergy_safe(m, allergies, ontology)
        and is_meal_disease_suitable(m, rules)
    ]

    if not candidates:
        return []

    buckets: Dict[str, List[Tuple[Meal, float]]] = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snack": [],
    }

    for m in candidates:
        buckets[m.course].append((m, score_meal(m, rules)))

    for c in buckets:
        buckets[c].sort(key=lambda x: x[1], reverse=True)

    used_ids = set()

    def pick_best(course: str):
        for m, _ in buckets[course][:3]:
            if m.id not in used_ids:
                used_ids.add(m.id)
                return m
        return None

    def pick_any():
        all_items = [
            (m, sc)
            for lst in buckets.values()
            for (m, sc) in lst
            if m.id not in used_ids
        ]
        if not all_items:
            return None
        all_items.sort(key=lambda x: x[1], reverse=True)
        m = all_items[0][0]
        used_ids.add(m.id)
        return m

    plan = []

    for course in ("breakfast", "lunch", "dinner"):
        meal = pick_best(course) or pick_any()
        if meal:
            meal.course = course
            plan.append(meal)

    for _ in range(max(0, min(2, meal_frequency - 3))):
        snack = pick_best("snack") or pick_any()
        if snack:
            snack.course = "snack"
            plan.append(snack)

    return plan
