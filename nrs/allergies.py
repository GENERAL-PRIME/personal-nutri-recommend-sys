from typing import Dict, List
from nrs.models import Meal


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
            "bread",
            "naan",
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
        "peanut": ["peanut", "groundnut", "chikki"],
        "tree_nut": ["cashew", "kaju", "almond", "badam", "pista"],
        "egg": ["egg", "omelette", "anda", "bhurji"],
        "soy": ["soy", "soya", "tofu", "soy milk"],
        "fish": ["fish", "prawn", "shrimp", "crab"],
        "sesame": ["sesame", "til"],
        "chicken": ["chicken", "murgh", "broiler"],
        "mutton": ["mutton", "goat", "lamb", "bakra"],
        "beef": ["beef", "buff", "buffalo"],
        "pork": ["pork", "bacon", "ham"],
        "meat": [
            "chicken",
            "murgh",
            "broiler",
            "mutton",
            "goat",
            "lamb",
            "bakra",
            "beef",
            "buff",
            "buffalo",
            "pork",
            "bacon",
            "ham",
        ],
    }


def normalize_allergies(
    user_allergies: List[str],
    ontology: Dict[str, List[str]],
) -> List[str]:
    """
    Maps raw inputs to canonical allergens.
    e.g. wheat → gluten, paneer → dairy, chicken → chicken/meat
    """
    normalized = set()

    for raw in user_allergies:
        raw = raw.lower().strip()

        # direct canonical match
        if raw in ontology:
            normalized.add(raw)
            continue

        # ingredient keyword match
        for canonical, keywords in ontology.items():
            if raw in keywords:
                normalized.add(canonical)

    return list(normalized)


# -------------------------------------------------
# Allergy safety check (ingredient-first)
# -------------------------------------------------
def is_meal_allergy_safe(
    meal: Meal,
    allergies: List[str],
    ontology: Dict[str, List[str]],
) -> bool:
    try:
        canonical_allergies = normalize_allergies(allergies, ontology)

        ingredients = [i.lower() for i in meal.ingredients]
        name = meal.name.lower()
        tags = set(t.lower() for t in meal.tags)

        for allergen in canonical_allergies:
            keywords = ontology.get(allergen, [])

            if allergen == "gluten":
                if "gf" in tags:
                    continue
                if any(k in ing for ing in ingredients for k in keywords):
                    return False
                continue

            # -------------------------
            # Ingredient-based check
            # -------------------------
            if any(k in ing for ing in ingredients for k in keywords):
                return False

            if any(k in name for k in keywords):
                return False
            if allergen in tags:
                return False

        return True

    except Exception:
        return False
