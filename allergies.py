from typing import Dict, List
from models import Meal


def build_allergen_ontology() -> Dict[str, List[str]]:
    return {
        "gluten": [
            "wheat",
            "atta",
            "maida",
            "sooji",
            "semolina",
            "sev",
            "seviyaan",
            "bhatura",
            "naan",
            "bread",
            "paratha",
            "roti",
            "dalia",
            "upma",
        ],
        "dairy": [
            "milk",
            "paneer",
            "ghee",
            "butter",
            "cream",
            "khoya",
            "khoa",
            "curd",
            "lassi",
            "buttermilk",
            "kadhi",
        ],
        "peanut": ["peanut", "groundnut", "chikki", "peanut chutney", "nut"],
        "tree_nut": ["cashew", "kaju", "almond", "badam", "pista", "pistachio"],
        "egg": ["egg", "omelette", "anda", "bhurji"],
        "soy": ["soy", "soya", "tofu", "soy milk"],
        "fish": ["fish", "prawn", "shrimp", "crab"],
        "sesame": ["sesame", "til"],
    }


def is_meal_allergy_safe(
    meal: Meal, allergies: List[str], ontology: Dict[str, List[str]]
) -> bool:
    try:
        name = meal.name.lower()
        tagset = set(meal.tags)
        for allergy in allergies:
            a = allergy.lower().strip()
            keywords = ontology.get(a, [])

            if a == "gluten":
                if "gf" in tagset:
                    continue
                if any(k in name for k in keywords):
                    return False
                continue

            if a == "egg":
                if meal.diet_type == "eggetarian" or any(k in name for k in keywords):
                    return False

            elif a in ("fish", "shellfish"):
                if any(k in name for k in keywords):
                    return False

            else:
                if any(k in name for k in keywords) or any(a in t for t in tagset):
                    return False
        return True
    except Exception:
        return False
