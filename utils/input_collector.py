"""
utils/input_collector.py
Interactive CLI for collecting / updating a user health profile.

New user  : auto-ID generated → fill form → register (with full health data)
Returning : enter ID → load saved profile → update with add/remove options

Returning user update options per category (allergies / diseases / dislikes):
  1. Keep existing (no change)
  2. Add to existing list
  3. Remove specific items from existing list
  4. Replace entire list (start fresh)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import (
    print_header, print_section, print_info, print_warning,
    cyan, yellow, green, red, bold, parse_multiline_input, confirm
)
from utils.user_registry import (
    generate_user_id, register_user, user_exists,
    get_user, print_user_card, update_user_meta, save_user_profile
)

SUPPORTED_ALLERGIES = [
    "gluten","wheat","celiac","dairy","milk","lactose",
    "nuts","tree nuts","peanuts","eggs","shellfish",
    "fish","seafood","soy","soya","sesame",
    "sulfites","histamine","fodmap","fructose",
]

SUPPORTED_DISEASES = [
    "Type 2 Diabetes","Type 1 Diabetes","Hypertension",
    "Heart Disease","Kidney Disease","Gout","PCOS",
    "Hypothyroidism","Hyperthyroidism","Anemia",
    "Celiac Disease","IBD","GERD","Fatty Liver Disease",
    "Obesity","Osteoporosis","High Cholesterol",
    "Lactose Intolerance","Cancer","Thyroid Cancer",
]

SUPPORTED_DISLIKES = [
    "Seafood","Red Meat","Eggs","Dairy Products",
    "Mushrooms","Nuts & Seeds","Legumes / Beans",
    "Bitter Gourd (Karela)","Bottle Gourd (Lauki)",
    "Onion & Garlic","Leafy Greens","Spicy Foods",
    "Bitter Foods","Fried Foods","Tofu / Soy Products",
    "Sprouts","Jain Diet","No Beef","No Pork",
    "vegan","vegetarian",
]

DIETARY_PREFERENCES = ["none","vegetarian","vegan","jain","halal"]


# ── Shared display helpers ────────────────────────────────────────────────────

def _print_hint_list(items: list, columns: int = 3):
    col_width = 28
    for i, item in enumerate(items):
        print(f"    {cyan('·')} {item:<{col_width}}", end="")
        if (i + 1) % columns == 0:
            print()
    if len(items) % columns != 0:
        print()


def _print_profile_summary(profile: dict):
    print()
    print(f"    {'User ID':<22}  {bold(green(profile['user_id']))}")
    print(f"    {'Name':<22}  {bold(profile['name'])}")
    print(f"    {'Age / Sex':<22}  {profile.get('age','—')} / {profile.get('sex','—')}")
    print(f"    {'Weight / Height':<22}  {profile.get('weight_kg','—')} kg / {profile.get('height_cm','—')} cm")
    print(f"    {'Dietary Preference':<22}  {bold(profile.get('dietary_preference','none') or 'none')}")
    print(f"    {'Allergies':<22}  {yellow(', '.join(profile.get('allergies',[]) or ['None']))}")
    print(f"    {'Diseases':<22}  {yellow(', '.join(profile.get('diseases', []) or ['None']))}")
    print(f"    {'Dislikes':<22}  {yellow(', '.join(profile.get('dislikes',  []) or ['None']))}")


# ── Core update logic: add / remove / replace / keep ─────────────────────────

def _update_list(label: str, existing: list, hints: list, hint_cols: int = 4) -> list:
    """
    Show a menu for one health category (allergies / diseases / dislikes):
      1 — Keep existing unchanged
      2 — Add new items to existing
      3 — Remove specific items from existing
      4 — Replace entire list with new entries

    Returns the updated list.
    """
    existing_display = ', '.join(existing) if existing else 'None'

    print()
    print(cyan(f"  Current {label}: ") + yellow(existing_display))
    print()
    print(f"    {cyan('1')}  Keep as-is")
    print(f"    {cyan('2')}  Add  new {label.lower()} to existing list")
    print(f"    {cyan('3')}  Remove specific {label.lower()} from existing list")
    print(f"    {cyan('4')}  Replace entire list (start fresh)")
    print()

    while True:
        choice = input(cyan(f"  Choose [1-4]: ")).strip()
        if choice in ("1","2","3","4"):
            break
        print_warning("Enter 1, 2, 3 or 4.")

    # ── 1: Keep ──────────────────────────────────────────────────────────────
    if choice == "1":
        print_info(f"{label} unchanged: {existing_display}")
        return existing

    # ── 2: Add ───────────────────────────────────────────────────────────────
    if choice == "2":
        print(cyan(f"\n  Supported {label.lower()}:"))
        _print_hint_list(hints, columns=hint_cols)
        new_items = parse_multiline_input(
            f"Enter {label.lower()} to ADD (one per line or comma-separated):"
        )
        # Merge, preserving order, no duplicates (case-insensitive dedup)
        existing_lower = {x.lower() for x in existing}
        added = []
        for item in new_items:
            if item.lower() not in existing_lower:
                existing.append(item)
                existing_lower.add(item.lower())
                added.append(item)
        if added:
            print_info(f"Added: {', '.join(added)}")
        else:
            print_info("No new items added (all already in list).")
        print_info(f"Updated {label}: {', '.join(existing) or 'None'}")
        return existing

    # ── 3: Remove ─────────────────────────────────────────────────────────────
    if choice == "3":
        if not existing:
            print_info(f"No {label.lower()} to remove.")
            return existing

        # Show numbered list
        print(cyan(f"\n  Current {label}:"))
        for i, item in enumerate(existing, 1):
            print(f"    {cyan(str(i))}.  {item}")
        print()
        print(cyan("  Enter the NUMBERS of items to remove (e.g. 1, 3)"))
        print(cyan("  OR type the exact names — one per line.\n"))

        raw = parse_multiline_input(f"Items to REMOVE from {label.lower()}:")

        to_remove_idx = set()   # 1-based indices
        to_remove_names = set() # exact or partial names

        for r in raw:
            r = r.strip()
            if r.isdigit():
                idx = int(r)
                if 1 <= idx <= len(existing):
                    to_remove_idx.add(idx)
            else:
                to_remove_names.add(r.lower())

        removed = []
        kept = []
        for i, item in enumerate(existing, 1):
            if i in to_remove_idx or item.lower() in to_remove_names:
                removed.append(item)
            else:
                kept.append(item)

        if removed:
            print_info(f"Removed: {', '.join(removed)}")
        else:
            print_warning("No matching items found to remove. List unchanged.")
        print_info(f"Updated {label}: {', '.join(kept) or 'None'}")
        return kept

    # ── 4: Replace ────────────────────────────────────────────────────────────
    if choice == "4":
        print(cyan(f"\n  Supported {label.lower()}:"))
        _print_hint_list(hints, columns=hint_cols)
        if confirm(f"Clear all existing {label.lower()} and enter fresh list?"):
            new_items = parse_multiline_input(
                f"Enter new {label.lower()} (one per line or comma-separated):"
            )
            print_info(f"Replaced {label}: {', '.join(new_items) or 'None'}")
            return new_items
        else:
            print_info(f"{label} unchanged.")
            return existing

    return existing   # fallback


# ── Health info collection (new user — all fresh) ─────────────────────────────

def _collect_health_info_fresh(profile: dict) -> dict:
    """Collect health fields from scratch (used for new users)."""

    print_section("Dietary Preference")
    print(cyan("  Options: ") + ", ".join(DIETARY_PREFERENCES))
    pref = input(cyan("  Your dietary preference: ")).strip().lower()
    profile["dietary_preference"] = pref if pref in DIETARY_PREFERENCES else "none"

    print_section("Allergies")
    print(cyan("  Supported allergy types:"))
    _print_hint_list(SUPPORTED_ALLERGIES, columns=4)
    print()
    if confirm("Do you have any food allergies?"):
        allergies = parse_multiline_input("Enter allergies (one per line or comma-separated):")
        profile["allergies"] = allergies
        if allergies:
            print_info(f"Recorded: {', '.join(allergies)}")
    else:
        profile["allergies"] = []
        print_info("No allergies recorded.")

    print_section("Medical Conditions / Diseases")
    print(cyan("  Supported conditions:"))
    _print_hint_list(SUPPORTED_DISEASES, columns=3)
    print()
    if confirm("Do you have any diagnosed medical conditions?"):
        diseases = parse_multiline_input("Enter conditions (one per line or comma-separated):")
        profile["diseases"] = diseases
        if diseases:
            print_info(f"Recorded: {', '.join(diseases)}")
    else:
        profile["diseases"] = []
        print_info("No medical conditions recorded.")

    print_section("Food Dislikes / Preferences")
    print(cyan("  Common options:"))
    _print_hint_list(SUPPORTED_DISLIKES, columns=3)
    print()
    if confirm("Do you have any food dislikes or avoidances?"):
        dislikes = parse_multiline_input("Enter dislikes (one per line or comma-separated):")
        profile["dislikes"] = dislikes
        if dislikes:
            print_info(f"Recorded: {', '.join(dislikes)}")
    else:
        profile["dislikes"] = []
        print_info("No dislikes recorded.")

    return profile


# ── Health info update (returning user — add / remove / replace / keep) ───────

def _update_health_info(profile: dict) -> dict:
    """
    For returning users: show current values and offer
    keep / add / remove / replace per category.
    """

    # Dietary preference
    print_section("Dietary Preference")
    print(cyan("  Options: ") + ", ".join(DIETARY_PREFERENCES))
    existing_pref = profile.get("dietary_preference", "none") or "none"
    print(cyan(f"  Current: ") + yellow(existing_pref))
    pref = input(cyan(f"  New preference (Enter to keep [{existing_pref}]): ")).strip().lower()
    if not pref:
        pref = existing_pref
    profile["dietary_preference"] = pref if pref in DIETARY_PREFERENCES else existing_pref

    # Allergies
    print_section("Allergies")
    profile["allergies"] = _update_list(
        "Allergies", profile.get("allergies", []),
        SUPPORTED_ALLERGIES, hint_cols=4
    )

    # Diseases
    print_section("Medical Conditions / Diseases")
    profile["diseases"] = _update_list(
        "Diseases", profile.get("diseases", []),
        SUPPORTED_DISEASES, hint_cols=3
    )

    # Dislikes
    print_section("Food Dislikes / Preferences")
    profile["dislikes"] = _update_list(
        "Dislikes", profile.get("dislikes", []),
        SUPPORTED_DISLIKES, hint_cols=3
    )

    return profile


# ── New user flow ─────────────────────────────────────────────────────────────

def _new_user_flow() -> dict:
    print_section("New User Registration")

    user_id = generate_user_id()
    print(f"\n    {cyan('Your unique User ID:  ')}{bold(green(user_id))}")
    print(cyan("    ⚠  Save this ID — you will need it to update your profile later.\n"))

    name      = input(cyan("  Enter your Name         : ")).strip() or "User"
    age       = input(cyan("  Enter Age               : ")).strip()
    sex       = input(cyan("  Enter Sex (M/F/Other)   : ")).strip()
    weight_kg = input(cyan("  Enter Weight (kg)       : ")).strip()
    height_cm = input(cyan("  Enter Height (cm)       : ")).strip()

    profile = {
        "user_id":   user_id,
        "name":      name,
        "age":       age,
        "sex":       sex,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
    }

    profile = _collect_health_info_fresh(profile)

    # Register with FULL health data stored in registry
    register_user(
        user_id, name, age, sex,
        weight_kg          = weight_kg,
        height_cm          = height_cm,
        dietary_preference = profile.get("dietary_preference", "none"),
        allergies          = profile.get("allergies", []),
        diseases           = profile.get("diseases",  []),
        dislikes           = profile.get("dislikes",  []),
    )
    return profile


# ── Returning user flow ───────────────────────────────────────────────────────

def _returning_user_flow() -> dict | None:
    print_section("Returning User — Enter Your User ID")
    print(cyan("  Your ID looks like:  NRS0001\n"))

    while True:
        entered_id = input(cyan("  Enter your User ID: ")).strip().upper()

        if not entered_id:
            print_warning("No ID entered.")
            if not confirm("Try again?"):
                return None
            continue

        if not user_exists(entered_id):
            print()
            print(red(f"  ✘  User ID '{entered_id}' not found."))
            print(cyan("     Check your ID and try again, or register as a New User."))
            print()
            if not confirm("Try a different ID?"):
                return None
            continue

        record = get_user(entered_id)
        print(green(f"\n  ✔  Welcome back, {bold(record['name'])}!"))
        print_user_card(record)
        break

    # Build profile from stored registry data (includes health info)
    profile = {
        "user_id":            record["user_id"],
        "name":               record.get("name", ""),
        "age":                record.get("age", ""),
        "sex":                record.get("sex", ""),
        "weight_kg":          record.get("weight_kg", ""),
        "height_cm":          record.get("height_cm", ""),
        "dietary_preference": record.get("dietary_preference", "none"),
        "allergies":          list(record.get("allergies", [])),
        "diseases":           list(record.get("diseases",  [])),
        "dislikes":           list(record.get("dislikes",  [])),
    }

    # Update basic info
    print_section("Update Basic Information  (press Enter to keep existing)")
    new_name = input(cyan(f"  Name         [{record['name']}]: ")).strip()
    new_age  = input(cyan(f"  Age          [{record.get('age','—')}]: ")).strip()
    new_sex  = input(cyan(f"  Sex          [{record.get('sex','—')}]: ")).strip()
    new_wt   = input(cyan(f"  Weight (kg)  [{record.get('weight_kg','—')}]: ")).strip()
    new_ht   = input(cyan(f"  Height (cm)  [{record.get('height_cm','—')}]: ")).strip()

    if new_name: profile["name"]      = new_name
    if new_age:  profile["age"]       = new_age
    if new_sex:  profile["sex"]       = new_sex
    if new_wt:   profile["weight_kg"] = new_wt
    if new_ht:   profile["height_cm"] = new_ht

    # Update health info with add/remove/replace/keep options
    profile = _update_health_info(profile)
    return profile


# ── Main entry point ──────────────────────────────────────────────────────────

def collect_user_profile() -> dict:
    print_header("AI Personalised NRS  —  Food Filtering Module")
    print(cyan("  This module collects your health profile and filters safe foods."))
    print(cyan("  Results are forwarded to the Nutrition & Diet Recommendation Model.\n"))

    print(cyan("  ┌──────────────────────────────────────────┐"))
    print(cyan("  │  1.  New User      (register & get ID)   │"))
    print(cyan("  │  2.  Returning User (update preferences) │"))
    print(cyan("  └──────────────────────────────────────────┘"))
    print()

    while True:
        choice = input(cyan("  Select [1/2]: ")).strip()
        if choice in ("1","2"):
            break
        print_warning("Please enter 1 or 2.")

    profile = None

    if choice == "1":
        profile = _new_user_flow()
    else:
        profile = _returning_user_flow()
        if profile is None:
            print_warning("Could not find existing account.")
            if confirm("Register as a new user instead?"):
                profile = _new_user_flow()
            else:
                sys.exit(0)

    print_section("Profile Summary  —  Please Confirm")
    _print_profile_summary(profile)
    print()

    if not confirm("Confirm and run the food filter?"):
        print_warning("Aborted by user.")
        sys.exit(0)

    return profile
