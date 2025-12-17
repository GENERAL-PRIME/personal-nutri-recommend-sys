from typing import Dict


def compute_targets(
    age: int, sex: str, height_cm: float, weight_kg: float, activity: str, goal: str
) -> Dict[str, float]:
    s = 5 if sex.lower().startswith("m") else -161
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + s
    act = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very active": 1.9,
    }.get(activity, 1.55)
    tdee = bmr * act
    delta = {"loss": -500, "maintain": 0, "gain": +350}.get(goal, 0)
    kcal = max(1200, tdee + delta)
    protein_g = max(
        0.9 * weight_kg, 1.2 * weight_kg if goal == "loss" else 1.0 * weight_kg
    )
    fat_kcal = 0.25 * kcal
    fat_g = fat_kcal / 9
    carbs_g = (kcal - (protein_g * 4 + fat_g * 9)) / 4
    return {
        "kcal": round(kcal),
        "protein_g": round(protein_g),
        "fat_g": round(fat_g),
        "carbs_g": round(carbs_g),
    }
