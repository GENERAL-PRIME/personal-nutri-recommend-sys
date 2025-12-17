from nrs.models import Meal


def diet_gate(meal: Meal, requested: str) -> bool:
    requested = requested.lower()

    if requested == "jain":
        return meal.diet_type == "jain" or "jain_safe" in meal.tags

    if requested == "veg":
        return meal.veg_type == "veg"

    if requested == "eggetarian":
        return meal.diet_type in ("veg", "eggetarian")

    if requested == "nonveg":
        return True

    return True
