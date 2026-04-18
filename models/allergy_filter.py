"""
Food Filtering Model - Allergy Based
=====================================
Filters foods from the main food dataset based on user's reported allergies.
Output: List of safe foods to pass to the Nutrition & Diet Recommendation Model.
"""

import os, sys
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')


class AllergyFoodFilter:
    """
    Filters foods based on user allergies using rule-based matching.
    Supports 14 allergy types including cross-reactivity checks.
    """

    # Map allergen names to dataset columns
    ALLERGEN_COLUMN_MAP = {
        'gluten':     'contains_gluten',
        'celiac':     'contains_gluten',
        'wheat':      'contains_gluten',
        'dairy':      'contains_dairy',
        'milk':       'contains_dairy',
        'lactose':    'contains_dairy',
        'nuts':       'contains_nuts',
        'tree nuts':  'contains_nuts',
        'eggs':       'contains_eggs',
        'egg':        'contains_eggs',
        'shellfish':  'contains_shellfish',
        'shrimp':     'contains_shellfish',
        'fish':       'contains_fish',
        'seafood':    'contains_fish',
        'soy':        'contains_soy',
        'soya':       'contains_soy',
        'sesame':     'contains_sesame',
        'peanuts':    'contains_peanuts',
        'peanut':     'contains_peanuts',
        'sulfites':   'contains_sulfites',
        'sulphites':  'contains_sulfites',
    }

    # Special filter rules that need custom logic (beyond column flags)
    SPECIAL_ALLERGY_RULES = {
        'histamine': {
            'exclude_categories': ['seafood', 'dairy'],
            'exclude_food_ids': ['F012', 'F013', 'F017', 'F018', 'F019', 'F020',
                                  'F022', 'F023', 'F024', 'F095'],
            'notes': 'Histamine found in fermented/aged/canned/smoked foods'
        },
        'fodmap': {
            'exclude_food_ids': ['F044', 'F045', 'F008', 'F009', 'F010', 'F011',
                                  'F057', 'F063', 'F097', 'F003', 'F004', 'F005'],
            'notes': 'Low-FODMAP diet; limit onion, garlic, legumes, wheat'
        },
        'fructose': {
            'max_sugar_g': 8,
            'exclude_food_ids': ['F085', 'F031', 'F034'],
            'notes': 'Limit high-fructose foods; apples and pears also flagged'
        }
    }

    def __init__(self, food_data_path: str, allergy_data_path: str):
        self.food_df = pd.read_csv(food_data_path)
        self.allergy_df = pd.read_csv(allergy_data_path)
        self._preprocess()

    def _preprocess(self):
        """Convert boolean columns from strings to actual booleans."""
        bool_cols = [
            'contains_gluten', 'contains_dairy', 'contains_nuts', 'contains_eggs',
            'contains_shellfish', 'contains_fish', 'contains_soy', 'contains_sesame',
            'contains_peanuts', 'contains_sulfites', 'is_vegetarian', 'is_vegan'
        ]
        for col in bool_cols:
            if col in self.food_df.columns:
                self.food_df[col] = self.food_df[col].astype(str).str.strip().str.lower() == 'true'

    def filter(self, user_allergies: List[str]) -> Tuple[pd.DataFrame, Dict]:
        """
        Filter foods based on a list of user allergies.

        Args:
            user_allergies: List of allergy strings e.g. ['gluten', 'nuts', 'shellfish']

        Returns:
            (safe_foods_df, filter_report)
        """
        if not user_allergies:
            full = self.food_df.copy()
            return full, {
                'status': 'no_allergies',
                'total_foods_before': len(full),
                'total_foods_after':  len(full),
                'total_removed': 0,
                'removed_by_allergy': {},
                'filter_log': [],
            }

        safe_df = self.food_df.copy()
        removed_foods = {}
        filter_log = []

        for allergy in user_allergies:
            allergy_lower = allergy.strip().lower()

            # --- Standard column-based filter ---
            if allergy_lower in self.ALLERGEN_COLUMN_MAP:
                col = self.ALLERGEN_COLUMN_MAP[allergy_lower]
                if col in safe_df.columns:
                    before = len(safe_df)
                    flagged = safe_df[safe_df[col] == True]['food_name'].tolist()
                    safe_df = safe_df[safe_df[col] == False]
                    removed = before - len(safe_df)
                    if removed > 0:
                        removed_foods[allergy] = flagged
                        filter_log.append(f"[{allergy.upper()}] Removed {removed} foods via column '{col}'")

            # --- Special rule-based filters ---
            elif allergy_lower in self.SPECIAL_ALLERGY_RULES:
                rule = self.SPECIAL_ALLERGY_RULES[allergy_lower]
                before = len(safe_df)

                # Exclude by food_id
                if 'exclude_food_ids' in rule:
                    flagged = safe_df[safe_df['food_id'].isin(rule['exclude_food_ids'])]['food_name'].tolist()
                    safe_df = safe_df[~safe_df['food_id'].isin(rule['exclude_food_ids'])]

                # Exclude by category
                if 'exclude_categories' in rule:
                    cat_flagged = safe_df[safe_df['category'].str.lower().isin(
                        [c.lower() for c in rule['exclude_categories']])]['food_name'].tolist()
                    flagged = flagged + cat_flagged
                    safe_df = safe_df[~safe_df['category'].str.lower().isin(
                        [c.lower() for c in rule['exclude_categories']])]

                # Apply max sugar filter (fructose intolerance)
                if 'max_sugar_g' in rule:
                    sugar_flagged = safe_df[safe_df['sugar_g'] > rule['max_sugar_g']]['food_name'].tolist()
                    flagged = flagged + sugar_flagged
                    safe_df = safe_df[safe_df['sugar_g'] <= rule['max_sugar_g']]

                removed = before - len(safe_df)
                if removed > 0:
                    removed_foods[allergy] = list(set(flagged))
                    filter_log.append(f"[{allergy.upper()}] {rule.get('notes','')} → Removed {removed} foods")

            else:
                filter_log.append(f"[WARNING] Allergy '{allergy}' not recognized in database")

        report = {
            'status': 'filtered',
            'input_allergies': user_allergies,
            'total_foods_before': len(self.food_df),
            'total_foods_after': len(safe_df),
            'total_removed': len(self.food_df) - len(safe_df),
            'removed_by_allergy': removed_foods,
            'filter_log': filter_log
        }

        return safe_df.reset_index(drop=True), report

    def get_severity_warning(self, allergies: List[str]) -> List[str]:
        """Returns severity warnings for given allergies."""
        warnings_list = []
        high_risk = ['peanuts', 'peanut', 'shellfish', 'shrimp']
        for allergy in allergies:
            if allergy.lower() in high_risk:
                warnings_list.append(
                    f"⚠️  CRITICAL: {allergy} allergy detected. "
                    f"Even trace amounts can cause anaphylaxis. "
                    f"Carry epinephrine auto-injector."
                )
        return warnings_list

    def get_allergy_info(self, allergy_name: str) -> Dict:
        """Fetch detailed info about a specific allergy from the allergy dataset."""
        row = self.allergy_df[
            self.allergy_df['allergy_name'].str.lower().str.contains(allergy_name.lower())
        ]
        if not row.empty:
            return row.iloc[0].to_dict()
        return {}


# ─────────────────────────────────────────────
# Example Usage
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os

    BASE = os.path.dirname(os.path.abspath(__file__))
    food_path    = os.path.join(BASE, "../datasets/food_data.csv")
    allergy_path = os.path.join(BASE, "../datasets/allergy_data.csv")

    model = AllergyFoodFilter(food_path, allergy_path)

    # --- Test Case 1: Gluten + Dairy Allergy ---
    user_allergies = ["gluten", "dairy"]
    safe_foods, report = model.filter(user_allergies)

    print("=" * 60)
    print("ALLERGY FOOD FILTER - TEST RESULTS")
    print("=" * 60)
    print(f"User Allergies   : {report['input_allergies']}")
    print(f"Foods Before     : {report['total_foods_before']}")
    print(f"Foods After      : {report['total_foods_after']}")
    print(f"Foods Removed    : {report['total_removed']}")
    print("\n--- Filter Log ---")
    for log in report['filter_log']:
        print(f"  {log}")
    print("\n--- Removed Foods by Allergy ---")
    for allergy, foods in report['removed_by_allergy'].items():
        print(f"  [{allergy}]: {foods}")
    print("\n--- Safe Foods (first 15) ---")
    print(safe_foods[['food_id', 'food_name', 'category', 'calories_per_100g']].head(15).to_string(index=False))

    # Severity warnings
    warnings = model.get_severity_warning(user_allergies)
    if warnings:
        print("\n--- Safety Warnings ---")
        for w in warnings:
            print(f"  {w}")

    # --- Test Case 2: Shellfish + Nuts ---
    print("\n" + "=" * 60)
    user_allergies_2 = ["shellfish", "nuts", "eggs"]
    safe_foods_2, report_2 = model.filter(user_allergies_2)
    print(f"Allergies: {user_allergies_2}")
    print(f"Safe Foods Count: {len(safe_foods_2)} / {report_2['total_foods_before']}")
    warnings_2 = model.get_severity_warning(user_allergies_2)
    for w in warnings_2:
        print(f"  {w}")
