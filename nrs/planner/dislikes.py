from nrs.models import Meal


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def dislikes_gate(meal: Meal, disliked: list[str] | None) -> bool:
    if not disliked:
        return True

    name = _norm(meal.name)
    tagset = {_norm(t) for t in meal.tags}

    for item in disliked:
        k = _norm(item)
        if k and (k in name or k in tagset):
            return False

    return True
