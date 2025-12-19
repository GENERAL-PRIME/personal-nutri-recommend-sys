from nrs.models import Meal


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def dislikes_gate(meal: Meal, disliked: list[str] | None) -> bool:
    """
    Returns False if any disliked item appears in:
    - ingredients (PRIMARY)
    - dish name (fallback)
    - tags (fallback)
    """
    if not disliked:
        return True

    name = _norm(meal.name)
    ingredients = {_norm(i) for i in meal.ingredients}
    tags = {_norm(t) for t in meal.tags}

    for item in disliked:
        k = _norm(item)
        if not k:
            continue

        if any(k in ing for ing in ingredients):
            return False

        if k in name:
            return False

        if k in tags:
            return False

    return True
