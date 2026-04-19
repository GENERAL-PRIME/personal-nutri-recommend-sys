"""
recommendation_model/display.py
Pretty-print recommendation results in the terminal.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tabulate import tabulate
from utils.helpers import (
    cyan, yellow, green, red, bold, magenta,
    print_header, print_section, print_info, print_success
)
from recommendation_model.calculator import HealthMetrics


MEAL_SLOT_LABELS = {
    "breakfast":      "🌅 Breakfast",
    "mid_morning":    "☕ Mid-Morning",
    "lunch":          "🍽  Lunch",
    "afternoon":      "🍊 Afternoon",
    "evening_snack":  "🫖 Evening Snack",
    "dinner":         "🌙 Dinner",
}

BAR_FULL  = "█"
BAR_EMPTY = "░"
BAR_WIDTH = 20


def _progress_bar(actual: float, target: float, width: int = BAR_WIDTH) -> str:
    if target <= 0:
        return ""
    pct   = min(actual / target, 1.5)
    filled = round(pct * width)
    filled = min(filled, width)
    color  = green if pct <= 1.05 else red
    bar    = color(BAR_FULL * filled) + BAR_EMPTY * (width - filled)
    return f"[{bar}] {actual:.0f}/{target:.0f}"


def show_metrics(metrics: HealthMetrics):
    """Display all calculated health metrics."""
    print_section("Health Metrics & Calculations")

    # Body composition
    print(f"\n  {bold('Body Composition')}")
    print(f"    {'BMI':<28}  {cyan(str(metrics.bmi))}  {yellow(f'({metrics.bmi_category})')}")
    print(f"    {'Ideal Body Weight':<28}  {cyan(str(metrics.ibw_kg))} kg")
    print(f"    {'Adjusted Body Weight':<28}  {cyan(str(metrics.abw_kg))} kg")

    # Energy
    print(f"\n  {bold('Energy (kcal/day)')}")
    print(f"    {'BMR (rest)':<28}  {cyan(f'{metrics.bmr:.0f}')}")
    print(f"    {'TDEE (maintenance)':<28}  {cyan(f'{metrics.tdee:.0f}')}")
    print(f"    {'Target Calories':<28}  {bold(green(f'{metrics.target_calories:.0f}'))}")

    # Macros
    print(f"\n  {bold('Daily Macro Targets')}")
    print(f"    {'Protein':<28}  {cyan(f'{metrics.protein_g}g')}  "
          f"({cyan(f'{metrics.protein_kcal:.0f} kcal')})")
    print(f"    {'Carbohydrates':<28}  {cyan(f'{metrics.carbs_g}g')}  "
          f"({cyan(f'{metrics.carbs_kcal:.0f} kcal')})")
    print(f"    {'Fat':<28}  {cyan(f'{metrics.fat_g}g')}  "
          f"({cyan(f'{metrics.fat_kcal:.0f} kcal')})")

    # Micros
    print(f"\n  {bold('Daily Micronutrient Targets')}")
    micros = [
        ("Fibre",      f"{metrics.fiber_g}g"),
        ("Sodium",     f"{metrics.sodium_mg}mg"),
        ("Calcium",    f"{metrics.calcium_mg}mg"),
        ("Iron",       f"{metrics.iron_mg}mg"),
        ("Vitamin C",  f"{metrics.vitamin_c_mg}mg"),
        ("Vitamin D",  f"{metrics.vitamin_d_iu}IU"),
        ("Potassium",  f"{metrics.potassium_mg}mg"),
        ("Water",      f"{metrics.water_ml:.0f}ml ({metrics.water_ml/1000:.1f}L)"),
    ]
    for name, val in micros:
        print(f"    {name:<28}  {cyan(val)}")

    # Meal distribution
    print(f"\n  {bold('Calorie Distribution per Meal')}")
    for slot, kcal in metrics.meal_calories.items():
        label = MEAL_SLOT_LABELS.get(slot, slot)
        print(f"    {label:<32}  {cyan(f'{kcal:.0f} kcal')}")


def show_insights(insights: list):
    print_section("Personalised Health Insights")
    for i, insight in enumerate(insights, 1):
        print(f"\n  {cyan(str(i))}.  {insight}")


def show_tips(tips: list):
    print_section("Actionable Daily Tips")
    for tip in tips:
        print(f"  {green('→')}  {tip}")


def show_day_plan(day_plan: dict, show_detail: bool = True):
    """Display a single day's meal plan."""
    day_name = day_plan.get("day_name", f"Day {day_plan['day']}")
    print(f"\n  {bold(cyan(f'── {day_name} ──'))}")

    for slot, meal in day_plan["meals"].items():
        slot_label  = MEAL_SLOT_LABELS.get(slot, slot)
        target_kcal = meal["target_kcal"]
        actual_kcal = meal["actual_kcal"]

        print(f"\n    {bold(slot_label)}  "
              f"({actual_kcal:.0f} / {target_kcal:.0f} kcal)")

        if show_detail:
            rows = [
                [
                    f["food_name"][:40],
                    f"{f['portion_g']:.0f}g",
                    f"{f['calories']:.0f}",
                    f"{f['protein_g']:.1f}",
                    f"{f['carbs_g']:.1f}",
                    f"{f['fat_g']:.1f}",
                ]
                for f in meal["foods"]
            ]
            print(tabulate(
                rows,
                headers=["Food", "Portion", "kcal", "Prot", "Carbs", "Fat"],
                tablefmt="simple",
                colalign=("left","right","right","right","right","right"),
            ))
            t = meal["totals"]
            print(f"    {'Total:':<12} "
                  f"{t['calories']:.0f} kcal  |  "
                  f"P:{t['protein_g']:.1f}g  "
                  f"C:{t['carbs_g']:.1f}g  "
                  f"F:{t['fat_g']:.1f}g  "
                  f"Fib:{t['fiber_g']:.1f}g")

    # Day totals
    print()
    t = day_plan["totals"]
    tg = day_plan["targets"]
    print(f"  {bold('Day Totals vs Targets:')}")
    fields = [
        ("Calories",   t["calories"],  tg["calories"],  "kcal"),
        ("Protein",    t["protein_g"], tg["protein_g"], "g"),
        ("Carbs",      t["carbs_g"],   tg["carbs_g"],   "g"),
        ("Fat",        t["fat_g"],     tg["fat_g"],     "g"),
        ("Fibre",      t["fiber_g"],   tg["fiber_g"],   "g"),
        ("Sodium",     t["sodium_mg"], tg["sodium_mg"], "mg"),
    ]
    for name, actual, target, unit in fields:
        bar = _progress_bar(actual, target)
        print(f"    {name:<12}  {bar}  {unit}")


def show_weekly_summary(weekly_plan: list, weekly_avg: dict):
    """One-line summary per day + weekly average."""
    print_section("7-Day Plan Overview")
    rows = []
    for day in weekly_plan:
        t = day["totals"]
        rows.append([
            day.get("day_name", f"Day {day['day']}"),
            f"{t['calories']:.0f}",
            f"{t['protein_g']:.0f}",
            f"{t['carbs_g']:.0f}",
            f"{t['fat_g']:.0f}",
            f"{t['fiber_g']:.0f}",
            f"{t['sodium_mg']:.0f}",
        ])

    rows.append([
        bold("Weekly Avg"),
        bold(f"{weekly_avg['calories']:.0f}"),
        bold(f"{weekly_avg['protein_g']:.0f}"),
        bold(f"{weekly_avg['carbs_g']:.0f}"),
        bold(f"{weekly_avg['fat_g']:.0f}"),
        bold(f"{weekly_avg['fiber_g']:.0f}"),
        bold(f"{weekly_avg['sodium_mg']:.0f}"),
    ])

    print()
    print(tabulate(
        rows,
        headers=["Day", "kcal", "Prot(g)", "Carbs(g)", "Fat(g)", "Fibre(g)", "Na(mg)"],
        tablefmt="rounded_outline",
        colalign=("left","right","right","right","right","right","right"),
    ))


def show_gaps(gaps: list):
    if not gaps:
        print(green("\n  ✔  All macro/micro targets met within tolerance."))
        return
    print_section("Nutritional Gap Analysis")
    for gap in gaps:
        print(f"  {yellow('⚠')}  {gap}")


def show_save_confirmation(saved: dict):
    print_section("Saving Recommendation")
    action = "Updated" if saved["is_update"] else "Created"
    color  = yellow if saved["is_update"] else green
    print(f"  {color(action)}  JSON → {saved['json']}")
    print(f"  {color(action)}  CSV  → {saved['csv']}")
