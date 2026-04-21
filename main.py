"""
main.py  —  AI Personalised NRS
=================================
Entry point. Runs the full pipeline:
  Step 1  →  Collect user profile (new or returning)
  Step 2  →  Food Filtering (allergy → disease → dislike)
  Step 3  →  Recommendation inputs (goal, activity, meals)
  Step 4  →  Diet & Nutrition Recommendation (BMI, BMR, TDEE, 7-day plan)

Usage:
    python main.py
    python main.py --demo
    python main.py --filter-only     # run only the food filter, skip recommendation
"""

import os
import sys
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from models.food_filter_pipeline import FoodFilteringPipeline
from utils.input_collector import collect_user_profile
from utils.display import (
    show_safe_foods_table, show_pipeline_summary, show_allergy_detail,
    show_disease_detail, show_dislike_detail, show_recommendation_context,
    show_severity_warnings,
)
from utils.helpers import (
    print_header, print_section, print_success, print_info,
    print_warning, cyan, bold, green, yellow
)
from utils.user_registry import (
    touch_last_run, save_user_profile
)
from recommendation_model.input_collector import collect_recommendation_inputs
from recommendation_model.recommender    import DietRecommender
from recommendation_model.display import (
    show_metrics, show_insights, show_tips,
    show_day_plan, show_weekly_summary, show_gaps, show_save_confirmation
)


# ── Demo profiles ─────────────────────────────────────────────────────────────
DEMO_PROFILES = [
    {
        "user_id": "DEMO_001", "name": "Rahul Sharma",
        "age": "42", "sex": "Male", "weight_kg": "82", "height_cm": "172",
        "dietary_preference": "vegetarian",
        "allergies": ["gluten", "nuts"],
        "diseases": ["Type 2 Diabetes", "Hypertension"],
        "dislikes": ["Mushrooms", "Bitter Gourd (Karela)"],
    },
    {
        "user_id": "DEMO_002", "name": "Priya Nair",
        "age": "35", "sex": "Female", "weight_kg": "65", "height_cm": "160",
        "dietary_preference": "none",
        "allergies": ["shellfish", "dairy"],
        "diseases": ["Gout", "High Cholesterol", "Obesity"],
        "dislikes": ["Red Meat", "Eggs", "Bitter Foods"],
    },
    {
        "user_id": "DEMO_003", "name": "Ananya Singh",
        "age": "28", "sex": "Female", "weight_kg": "58", "height_cm": "165",
        "dietary_preference": "vegan",
        "allergies": ["soy"],
        "diseases": ["Anemia", "PCOS"],
        "dislikes": ["Bottle Gourd (Lauki)", "Spicy Foods"],
    },
]

DEMO_REC_INPUTS = [
    {"goal": "weight_loss",      "activity_level": "lightly_active",    "meal_count": 4},
    {"goal": "weight_loss",      "activity_level": "moderately_active",  "meal_count": 5},
    {"goal": "maintain",         "activity_level": "lightly_active",    "meal_count": 3},
]


def run_full_pipeline(profile: dict, rec_inputs: dict = None, filter_only: bool = False):
    """Run the complete food filter + recommendation pipeline."""

    # ── STEP 2: Food Filtering ────────────────────────────────────────────────
    pipeline = FoodFilteringPipeline()
    print_header(f"Step 2 — Food Filtering  |  {profile.get('name', profile['user_id'])}")
    print_info(f"Allergies  : {', '.join(profile.get('allergies', [])) or 'None'}")
    print_info(f"Diseases   : {', '.join(profile.get('diseases',  [])) or 'None'}")
    print_info(f"Dislikes   : {', '.join(profile.get('dislikes',  [])) or 'None'}")
    print_info(f"Diet pref  : {profile.get('dietary_preference','none') or 'none'}")

    filter_result = pipeline.run(profile)

    show_severity_warnings(filter_result["severity_warnings"])
    show_pipeline_summary(filter_result)
    show_allergy_detail(filter_result["stage_reports"]["allergy"])
    show_disease_detail(filter_result["stage_reports"]["disease"])
    show_dislike_detail(filter_result["stage_reports"]["dislike"])

    print_section(f"Safe Food List  ({len(filter_result['safe_food_list'])} foods)")
    show_safe_foods_table(filter_result["safe_food_list"], max_rows=20)

    show_recommendation_context(filter_result["recommendation_context"])

    # Save filter output
    print_section("Saving Filter Outputs")
    filter_saved = pipeline.save_output(filter_result)
    touch_last_run(result["user_id"] if (result := filter_result) else profile["user_id"])
    save_user_profile(filter_result["user_id"], profile)
    action = "Updated" if filter_saved["is_update"] else "Created"
    color  = yellow if filter_saved["is_update"] else green
    print(f"  {color(action)}  JSON → {filter_saved['json']}")
    print(f"  {color(action)}  CSV  → {filter_saved['csv']}")

    if filter_only:
        print(green(bold("\n  ✅  Food filtering complete.\n")))
        return filter_result

    # ── STEP 3: Recommendation Inputs ────────────────────────────────────────
    if rec_inputs is None:
        print_header("Step 3 — Recommendation Preferences")
        rec_inputs = collect_recommendation_inputs()

    # ── STEP 4: Diet Recommendation ───────────────────────────────────────────
    print_header(f"Step 4 — Diet & Nutrition Plan  |  {profile.get('name','')}")

    recommender    = DietRecommender()
    rec_result     = recommender.run(
        safe_foods_df          = filter_result["safe_food_list"],
        recommendation_context = filter_result["recommendation_context"],
        goal                   = rec_inputs["goal"],
        activity_level         = rec_inputs["activity_level"],
        meal_count             = rec_inputs["meal_count"],
    )

    # Display
    show_metrics(rec_result["metrics"])
    show_insights(rec_result["insights"])
    show_tips(rec_result["tips"])
    show_gaps(rec_result["nutritional_gaps"])
    show_weekly_summary(rec_result["weekly_plan"], rec_result["weekly_avg"])

    # Show Day 1 in full detail
    print_section("Sample Day — Monday (Full Detail)")
    show_day_plan(rec_result["weekly_plan"][0], show_detail=True)

    # Save recommendation output
    rec_saved = recommender.save_output(rec_result)
    show_save_confirmation(rec_saved)

    print()
    print(green(bold("  ✅  Your personalised 7-day diet plan is ready!")))
    print(green(bold("      Open the CSV file for your full week's meal plan.")))
    print()

    return {"filter": filter_result, "recommendation": rec_result}


def pick_demo_profile() -> tuple:
    print_header("Demo Mode  —  Choose a Profile")
    for i, p in enumerate(DEMO_PROFILES, 1):
        diseases = ", ".join(p["diseases"]) or "None"
        print(f"  {cyan(str(i))}.  {bold(p['name']):<22}  Diseases: {diseases}")
    print()
    while True:
        choice = input(cyan("  Select profile [1-3]: ")).strip()
        if choice in ("1","2","3"):
            idx = int(choice) - 1
            return DEMO_PROFILES[idx], DEMO_REC_INPUTS[idx]
        print_warning("Please enter 1, 2, or 3.")


def main():
    parser = argparse.ArgumentParser(description="AI Personalised NRS")
    parser.add_argument("--demo",        action="store_true", help="Run with preset demo profile")
    parser.add_argument("--filter-only", action="store_true", help="Run food filter only, skip recommendation")
    args = parser.parse_args()

    if args.demo:
        profile, rec_inputs = pick_demo_profile()
    else:
        print_header("Step 1 — User Profile")
        profile    = collect_user_profile()
        rec_inputs = None   # will be collected interactively in step 3

    run_full_pipeline(profile, rec_inputs, filter_only=args.filter_only)


if __name__ == "__main__":
    main()
