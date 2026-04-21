"""
utils/display.py
Pretty-printing helpers for pipeline results.
"""

import pandas as pd
from tabulate import tabulate
from utils.helpers import (
    print_section, print_info, print_warning, print_success,
    cyan, yellow, green, red, bold, magenta
)


def show_safe_foods_table(df: pd.DataFrame, max_rows: int = 25):
    """Print the final safe food list as a formatted table."""
    if df.empty:
        print_warning("No safe foods after filtering.")
        return

    cols = [
        "food_id", "food_name", "category",
        "calories_per_100g", "protein_g", "carbs_g", "fat_g",
        "fiber_g", "sugar_g", "sodium_mg"
    ]
    # Add disease_score column if it exists
    if "disease_score" in df.columns:
        cols.append("disease_score")

    display_df = df[[c for c in cols if c in df.columns]].head(max_rows)

    # Rename for display
    rename_map = {
        "food_id": "ID",
        "food_name": "Food Name",
        "category": "Category",
        "calories_per_100g": "Cal/100g",
        "protein_g": "Protein",
        "carbs_g": "Carbs",
        "fat_g": "Fat",
        "fiber_g": "Fiber",
        "sugar_g": "Sugar",
        "sodium_mg": "Sodium",
        "disease_score": "Score",
    }
    display_df = display_df.rename(columns=rename_map)

    print()
    print(tabulate(
        display_df,
        headers="keys",
        tablefmt="rounded_outline",
        showindex=False,
        floatfmt=".1f"
    ))
    if len(df) > max_rows:
        print(cyan(f"  … and {len(df) - max_rows} more foods (see exported file for full list)"))


def show_pipeline_summary(result: dict):
    """Print a clean summary of what each stage removed."""
    print_section("Pipeline Summary")

    stages = [
        ("Allergy Filter",  result["stage_reports"]["allergy"]),
        ("Disease Filter",  result["stage_reports"]["disease"]),
        ("Dislike Filter",  result["stage_reports"]["dislike"]),
    ]

    for stage_name, report in stages:
        before  = report.get("total_foods_before")
        after   = report.get("total_foods_after")
        removed = report.get("total_removed", 0)

        before_str = str(before) if before is not None else "—"
        after_str  = str(after)  if after  is not None else "—"
        change_str = red(f"  -{removed} removed") if removed > 0 else green("  none removed")

        print(f"    {bold(stage_name):<28}  "
              f"{before_str} foods  →  {after_str} foods  "
              f"({change_str})")

    total_safe = result["recommendation_context"]["total_safe_foods"]
    print()
    print(green(f"  ✔  Final safe food list: {bold(str(total_safe))} foods ready for Recommendation Model"))


def show_allergy_detail(report: dict):
    """Print which specific foods were removed per allergy."""
    removed = report.get("removed_by_allergy", {})
    if not removed:
        return
    print_section("Foods Removed by Allergy")
    for allergy, foods in removed.items():
        print(f"    {yellow(allergy.upper())}: {', '.join(foods[:6])}"
              + (f" … +{len(foods)-6} more" if len(foods) > 6 else ""))


def show_disease_detail(report: dict):
    """Print per-disease removal summary and applied limits."""
    per_disease = report.get("per_disease_report", {})
    if not per_disease:
        return
    print_section("Disease Filtering Details")
    for disease, info in per_disease.items():
        print(f"    {bold(disease)}  —  {red(str(info['removed']))} foods removed")
        limits = info.get("limits_applied", {})
        if limits:
            limit_str = "  |  ".join(f"{k.replace('max_','').replace('min_','')}: {v}" for k, v in limits.items())
            print(f"      Limits: {cyan(limit_str)}")
        notes = info.get("dietary_notes", "")
        if notes:
            print(f"      {magenta('ℹ')} {notes[:90]}{'…' if len(notes) > 90 else ''}")


def show_dislike_detail(report: dict):
    """Print which specific foods were removed per dislike."""
    removed = report.get("removed_by_dislike", {})
    if not removed:
        return
    print_section("Foods Removed by Dislikes / Preferences")
    for dislike, foods in removed.items():
        print(f"    {yellow(dislike)}: {', '.join(foods[:6])}"
              + (f" … +{len(foods)-6} more" if len(foods) > 6 else ""))


def show_recommendation_context(ctx: dict):
    """Print the context dict that will be forwarded to the Recommendation Model."""
    print_section("Context Forwarded to Recommendation Model")

    # ── Disease & dietary flags ──────────────────────────────────────
    flag_keys = [
        "has_diabetes", "has_hypertension", "has_kidney_disease",
        "has_gout", "has_heart_disease", "has_pcos",
        "has_obesity", "has_high_cholesterol", "has_anemia",
        "has_fatty_liver", "is_vegetarian", "is_vegan",
    ]
    for key in flag_keys:
        val = ctx.get(key, False)
        icon = green("✔") if val else "·"
        print(f"    {icon}  {key.replace('_', ' ').title():<32}  {bold(str(val))}")

    # ── Nutrition limits ─────────────────────────────────────────────
    calorie = ctx.get("calorie_limit_kcal") or ctx.get("calorie_limit")
    sodium  = ctx.get("sodium_limit_mg")    or ctx.get("sodium_limit")
    sugar   = ctx.get("sugar_limit_g",      "—")
    protein = ctx.get("protein_target_g",   "—")

    print(f"\n    {'Calorie Limit':<32}  {cyan(str(calorie) if calorie else '—')} kcal/day")
    print(f"    {'Sodium Limit':<32}  {cyan(str(sodium)  if sodium  else '—')} mg/day")
    print(f"    {'Sugar Limit':<32}  {cyan(str(sugar))} g/day")
    print(f"    {'Protein Target':<32}  {cyan(str(protein))} g/day")
    print(f"    {'Total Safe Foods':<32}  {green(str(ctx.get('total_safe_foods', '—')))}")

    # ── Active conditions summary ─────────────────────────────────────
    diseases = ctx.get("active_diseases", [])
    allergies = ctx.get("active_allergies", [])
    if diseases:
        print(f"\n    {'Active Diseases':<32}  {yellow(', '.join(diseases))}")
    if allergies:
        print(f"    {'Active Allergies':<32}  {yellow(', '.join(allergies))}")

    # ── Critical allergy warnings ─────────────────────────────────────
    warnings = ctx.get("critical_allergies", [])
    if warnings:
        print()
        for w in warnings:
            print(f"    {red(w)}")


def show_severity_warnings(warnings: list):
    if not warnings:
        return
    print()
    for w in warnings:
        print(red(f"  ⚠  {w}"))
