"""
recommendation_model/input_collector.py
Collects the recommendation-specific inputs from the user:
  goal, activity level, meal count.
These are asked AFTER the food filtering step completes.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import (
    print_header, print_section, print_info, print_warning,
    cyan, yellow, green, bold, confirm
)

GOALS = {
    "1": ("weight_loss_aggressive", "Aggressive Weight Loss  (~0.7 kg/week deficit)"),
    "2": ("weight_loss",            "Weight Loss             (~0.5 kg/week deficit)"),
    "3": ("weight_loss_mild",       "Mild Weight Loss        (~0.25 kg/week deficit)"),
    "4": ("maintain",               "Maintain Current Weight (no calorie change)"),
    "5": ("weight_gain_mild",       "Mild Weight Gain        (~0.25 kg/week surplus)"),
    "6": ("weight_gain",            "Weight Gain             (~0.5 kg/week surplus)"),
    "7": ("muscle_gain",            "Muscle Gain             (lean bulk, +300 kcal)"),
}

ACTIVITY_LEVELS = {
    "1": ("sedentary",          "Sedentary          (desk job, no exercise)"),
    "2": ("lightly_active",     "Lightly Active     (light exercise 1-3 days/week)"),
    "3": ("moderately_active",  "Moderately Active  (exercise 3-5 days/week)"),
    "4": ("very_active",        "Very Active        (hard exercise 6-7 days/week)"),
    "5": ("extra_active",       "Extra Active       (athlete / physical job)"),
}

MEAL_COUNTS = {
    "3": (3, "3 meals/day  (Breakfast · Lunch · Dinner)"),
    "4": (4, "4 meals/day  (+ Mid-Morning snack)"),
    "5": (5, "5 meals/day  (+ Mid-Morning + Evening snack)"),
    "6": (6, "6 meals/day  (+ Mid-Morning + Afternoon + Evening snack)"),
}


def _menu(title: str, options: dict) -> str:
    """Generic numbered menu. Returns the selected key value."""
    print(f"\n  {bold(title)}")
    for num, (_, label) in options.items():
        print(f"    {cyan(num)}.  {label}")
    print()
    while True:
        choice = input(cyan(f"  Select [{'/'.join(options.keys())}]: ")).strip()
        if choice in options:
            return options[choice][0]
        print_warning(f"Please enter one of: {', '.join(options.keys())}")


def collect_recommendation_inputs() -> dict:
    """
    Interactive prompt for recommendation-specific inputs.
    Returns dict with goal, activity_level, meal_count.
    """
    print_section("Diet & Nutrition Recommendation Setup")
    print(cyan("  Answer 3 quick questions to personalise your diet plan.\n"))

    goal           = _menu("What is your primary goal?", GOALS)
    activity_level = _menu("What is your activity level?", ACTIVITY_LEVELS)
    meal_count_str = _menu("How many meals do you prefer per day?", MEAL_COUNTS)
    meal_count     = int(meal_count_str) if isinstance(meal_count_str, str) else meal_count_str

    # Confirm
    goal_label = next((v[1] for v in GOALS.values() if v[0] == goal), goal)
    act_label  = next((v[1] for v in ACTIVITY_LEVELS.values() if v[0] == activity_level), activity_level)
    meal_label = next((v[1] for v in MEAL_COUNTS.values() if v[0] == meal_count), str(meal_count))

    print()
    print(f"    {'Goal':<22}  {bold(goal_label)}")
    print(f"    {'Activity Level':<22}  {bold(act_label)}")
    print(f"    {'Meal Preference':<22}  {bold(meal_label)}")

    return {
        "goal":           goal,
        "activity_level": activity_level,
        "meal_count":     meal_count,
    }
