"""
main.py  —  Food Filtering Module  |  AI Personalised NRS
===========================================================
Entry point. Run this file from VSCode to:
  1. Collect the user's health profile interactively
  2. Run the 3-stage food filtering pipeline
  3. Display a rich summary in the terminal
  4. Export the safe food list (JSON + CSV) for the
     Nutrition & Diet Recommendation Model

Usage:
    python main.py
    python main.py --demo          # runs a preset demo profile
"""

import os
import sys
import argparse

# ── Ensure project root is on sys.path ───────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from models.food_filter_pipeline import FoodFilteringPipeline
from utils.input_collector import collect_user_profile
from utils.display import (
    show_safe_foods_table,
    show_pipeline_summary,
    show_allergy_detail,
    show_disease_detail,
    show_dislike_detail,
    show_recommendation_context,
    show_severity_warnings,
)
from utils.user_registry import touch_last_run, save_user_profile
from utils.helpers import (
    print_header, print_section, print_success,
    print_info, print_warning, cyan, bold, green, yellow
)


# ── Demo profile (used with --demo flag) ─────────────────────────────────────
DEMO_PROFILES = [
    {
        "user_id":            "DEMO_001",
        "name":               "Rahul Sharma",
        "age":                "42",
        "sex":                "Male",
        "weight_kg":          "82",
        "height_cm":          "172",
        "dietary_preference": "vegetarian",
        "allergies":          ["gluten", "nuts"],
        "diseases":           ["Type 2 Diabetes", "Hypertension"],
        "dislikes":           ["Mushrooms", "Bitter Gourd (Karela)", "Bottle Gourd (Lauki)"],
    },
    {
        "user_id":            "DEMO_002",
        "name":               "Priya Nair",
        "age":                "35",
        "sex":                "Female",
        "weight_kg":          "65",
        "height_cm":          "160",
        "dietary_preference": "none",
        "allergies":          ["shellfish", "dairy"],
        "diseases":           ["Gout", "High Cholesterol", "Obesity"],
        "dislikes":           ["Red Meat", "Eggs", "Bitter Foods"],
    },
    {
        "user_id":            "DEMO_003",
        "name":               "Ananya Singh",
        "age":                "28",
        "sex":                "Female",
        "weight_kg":          "58",
        "height_cm":          "165",
        "dietary_preference": "vegan",
        "allergies":          ["soy"],
        "diseases":           ["Anemia", "PCOS"],
        "dislikes":           ["Bottle Gourd (Lauki)", "Spicy Foods"],
    },
]


def run_pipeline(profile: dict):
    """Run the full pipeline and display results for a given profile."""

    pipeline = FoodFilteringPipeline()

    print_header(f"Running Food Filter  —  {profile.get('name', profile['user_id'])}")
    print_info(f"Allergies  : {', '.join(profile.get('allergies', [])) or 'None'}")
    print_info(f"Diseases   : {', '.join(profile.get('diseases',  [])) or 'None'}")
    print_info(f"Dislikes   : {', '.join(profile.get('dislikes',  [])) or 'None'}")
    print_info(f"Diet pref  : {profile.get('dietary_preference','none') or 'none'}")

    # ── Run ──────────────────────────────────────────────────────────────────
    result = pipeline.run(profile)

    # ── Display ──────────────────────────────────────────────────────────────
    show_severity_warnings(result["severity_warnings"])
    show_pipeline_summary(result)
    show_allergy_detail(result["stage_reports"]["allergy"])
    show_disease_detail(result["stage_reports"]["disease"])
    show_dislike_detail(result["stage_reports"]["dislike"])

    print_section(f"Safe Food List  ({len(result['safe_food_list'])} foods)")
    show_safe_foods_table(result["safe_food_list"], max_rows=30)

    show_recommendation_context(result["recommendation_context"])

    # ── Save outputs ─────────────────────────────────────────────────────────
    print_section("Saving Outputs")
    saved = pipeline.save_output(result)
    touch_last_run(result['user_id'])        # update last_run timestamp
    save_user_profile(result['user_id'], result['input_profile'])  # sync health data

    action = "Updated" if saved["is_update"] else "Created"
    action_color = yellow(action) if saved["is_update"] else green(action)

    print(f"    {action_color}  JSON → {saved['json']}")
    print(f"    {action_color}  CSV  → {saved['csv']}")

    if saved["is_update"]:
        print()
        print(cyan(f"    ℹ  First created : {saved['created_at']}"))
        print(cyan(f"    ℹ  Last updated  : {saved['last_updated']}"))
    else:
        print()
        print(cyan(f"    ℹ  Created at    : {saved['created_at']}"))

    print()
    print(green(bold("  ✅  Food filtering complete. Outputs are ready for the")))
    print(green(bold("      Nutrition & Diet Recommendation Model.")))
    print()

    return result


def pick_demo_profile() -> dict:
    """Let user choose one of the preset demo profiles."""
    print_header("Demo Mode  —  Choose a Profile")
    for i, p in enumerate(DEMO_PROFILES, 1):
        diseases = ", ".join(p["diseases"]) or "None"
        print(f"  {cyan(str(i))}.  {bold(p['name']):<20}  "
              f"Diseases: {diseases}")
    print()
    while True:
        choice = input(cyan("  Select profile [1-3]: ")).strip()
        if choice in ("1","2","3"):
            return DEMO_PROFILES[int(choice) - 1]
        print_warning("Please enter 1, 2, or 3.")


def main():
    parser = argparse.ArgumentParser(description="Food Filtering Module — AI Personalised NRS")
    parser.add_argument("--demo", action="store_true", help="Run with a preset demo profile")
    args = parser.parse_args()

    if args.demo:
        profile = pick_demo_profile()
    else:
        profile = collect_user_profile()

    run_pipeline(profile)


if __name__ == "__main__":
    main()
