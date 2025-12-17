import csv
from typing import List
from nrs.models import Meal


def load_meals_from_csv(path: str) -> List[Meal]:
    meals: List[Meal] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            tags_list = [
                t.strip().lower() for t in (r.get("tags") or "").split(",") if t.strip()
            ]
            meals.append(
                Meal(
                    id=r["id"].strip(),
                    name=r["name"].strip(),
                    course=r["course"].strip().lower(),
                    portion_desc=r["portion_desc"].strip(),
                    kcal=int(float(r["kcal"])),
                    carbs_g=float(r["carbs_g"]),
                    protein_g=float(r["protein_g"]),
                    fat_g=float(r["fat_g"]),
                    fiber_g=float(r["fiber_g"]),
                    sodium_mg=int(float(r["sodium_mg"])),
                    gi=int(float(r["gi"])),
                    cost_score=int(float(r["cost_score"])),
                    prep_time_min=int(float(r["prep_time_min"])),
                    diet_type=r["diet_type"].strip().lower(),
                    veg_type=r["veg_type"].strip().lower(),
                    tags=tags_list,
                )
            )
    return meals
