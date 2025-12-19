from dataclasses import dataclass
from typing import List, Literal


@dataclass
class Meal:
    id: str
    name: str
    course: Literal["breakfast", "lunch", "dinner", "snack"]
    portion_desc: str
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float
    sodium_mg: int
    gi: int
    cost_score: int
    prep_time_min: int
    diet_type: Literal["veg", "eggetarian", "nonveg", "jain"]
    veg_type: Literal["veg", "nonveg"]
    tags: List[str]
    ingredients: List[str]
