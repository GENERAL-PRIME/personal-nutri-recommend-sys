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
        "peanut": ["peanut", "groundnut", "chikki", "peanut chutney"],
        "tree_nut": ["cashew", "kaju", "almond", "badam", "pista", "pistachio"],
        "egg": ["egg", "omelette", "anda", "bhurji"],
        "soy": ["soy", "soya", "tofu", "soy milk"],
        "fish": ["fish", "prawn", "shrimp", "crab"],
        "sesame": ["sesame", "til"],
    }


def normalize_allergies(
    user_allergies: List[str], ontology: Dict[str, List[str]]
) -> List[str]:
    """
    Convert raw allergy keywords into canonical allergy categories.
    e.g. 'wheat' → 'gluten', 'paneer' → 'dairy'
    """
    normalized = set()

    for raw in user_allergies:
        raw = raw.lower().strip()

        # If already canonical
        if raw in ontology:
            normalized.add(raw)
            continue

        # Match keyword to group
        for canonical, keywords in ontology.items():
            if raw in keywords:
                normalized.add(canonical)

    return list(normalized)


def is_meal_allergy_safe(
    meal: Meal,
    allergies: List[str],
    ontology: Dict[str, List[str]],
) -> bool:
    try:
        canonical_allergies = normalize_allergies(allergies, ontology)

        name = meal.name.lower()
        tagset = set(meal.tags)

        for a in canonical_allergies:
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

            if a in ("fish", "shellfish"):
                if any(k in name for k in keywords):
                    return False

            if any(k in name for k in keywords):
                return False
            if any(a in t for t in tagset):
                return False

        return True

    except Exception:
        return False
