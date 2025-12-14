import random
from typing import Dict, List, Tuple
from models import Meal
from allergies import build_allergen_ontology, is_meal_allergy_safe
from diseases import is_meal_disease_suitable


# -----------------------------
# Diet Filter
# -----------------------------
def _diet_gate(meal: Meal, requested: str) -> bool:
    requested = requested.lower()

    if requested == "jain":
        return meal.diet_type == "jain" or "jain_safe" in meal.tags

    if requested == "veg":
        return meal.veg_type == "veg"

    if requested == "eggetarian":
        return meal.diet_type in ("veg", "eggetarian")  # no meat/fish

    if requested == "nonveg":
        return True

    return True


# -----------------------------
# Disliked foods filter
# -----------------------------
def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def _dislikes_gate(meal: Meal, disliked: list[str] | None) -> bool:
    if not disliked:
        return True
    name = _norm(meal.name)
    tagset = {_norm(t) for t in meal.tags}

    for item in disliked:
        k = _norm(item)
        if k and (k in name or k in tagset):
            return False

    return True


# -----------------------------
# Meal scoring
# -----------------------------
def _score_meal(meal: Meal, rules: Dict[str, Dict]) -> float:
    prefer_low_gi = rules.get("soft", {}).get("prefer_low_gi", False)
    score = 0.0

    score += meal.protein_g * 0.40
    score += meal.fiber_g * 0.20
    score -= meal.sodium_mg * 0.001
    score -= meal.cost_score * 0.05
    score -= meal.prep_time_min * 0.02

    score += (25 - min(meal.gi, 80)) * (0.15 if prefer_low_gi else 0.05)

    return score


# -----------------------------
# Main Meal Selector
# -----------------------------
def select_meals_for_day(
    meals: List[Meal],
    rules: Dict[str, Dict],
    allergies: List[str],
    diet_type: str,
    meal_frequency: int,
    disliked_foods: list[str] | None = None,
) -> List[Meal]:

    ontology = build_allergen_ontology()

    # 1. Filter candidates
    candidates = [
        m
        for m in meals
        if _diet_gate(m, diet_type)
        and _dislikes_gate(m, disliked_foods)
        and is_meal_allergy_safe(m, allergies, ontology)
        and is_meal_disease_suitable(m, rules)
    ]

    if not candidates:
        return []

    # 2. Bucket by course + attach scores
    buckets: Dict[str, List[Tuple[Meal, float]]] = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snack": [],
    }

    for m in candidates:
        buckets[m.course].append((m, _score_meal(m, rules)))

    for c in buckets:
        buckets[c].sort(key=lambda x: x[1], reverse=True)

    used_ids = set()

    # ---- PICKER FUNCTIONS ----
    def pick_best_unique(course: str):
        """Pick unique meal from course (top 3 shuffled for variety)."""
        items = buckets[course]
        if items:
            top_k = items[: min(3, len(items))]
            random.shuffle(top_k)
            for m, _ in top_k:
                if m.id not in used_ids:
                    used_ids.add(m.id)
                    return m
        return None

    def pick_any_unique():
        """Fallback: best remaining meal across all courses."""
        all_items = [
            (m, sc)
            for lst in buckets.values()
            for (m, sc) in lst
            if m.id not in used_ids
        ]
        if not all_items:
            return None
        all_items.sort(key=lambda x: x[1], reverse=True)
        best = all_items[0][0]
        used_ids.add(best.id)
        return best

    # -----------------------------
    # STRICT FINAL PLAN STRUCTURE
    # -----------------------------
    plan = []

    # 1 breakfast
    bf = pick_best_unique("breakfast")
    if not bf:
        bf = pick_any_unique()
        if bf:
            bf.course = "breakfast"
    if bf:
        plan.append(bf)

    # 1 lunch
    ln = pick_best_unique("lunch")
    if not ln:
        ln = pick_any_unique()
        if ln:
            ln.course = "lunch"
    if ln:
        plan.append(ln)

    # 1 dinner
    dn = pick_best_unique("dinner")
    if not dn:
        dn = pick_any_unique()
        if dn:
            dn.course = "dinner"
    if dn:
        plan.append(dn)

    # Remaining meals = snacks only
    remaining_snacks = max(0, min(2, meal_frequency - 3))
    for _ in range(remaining_snacks):
        sn = pick_best_unique("snack")
        if not sn:
            sn = pick_any_unique()
        if sn:
            sn.course = "snack"
            plan.append(sn)

    return plan


# -----------------------------
# Portion Adjuster
# -----------------------------
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
                "portion_note": m.portion_desc,  # original portion only
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
        "kcal": sum(m["kcal"] for m in adjusted),
        "carbs_g": round(sum(m["carbs_g"] for m in adjusted), 1),
        "protein_g": round(sum(m["protein_g"] for m in adjusted), 1),
        "fat_g": round(sum(m["fat_g"] for m in adjusted), 1),
        "fiber_g": round(sum(m["fiber_g"] for m in adjusted), 1),
        "sodium_mg": sum(m["sodium_mg"] for m in adjusted),
    }

    return adjusted, summary
