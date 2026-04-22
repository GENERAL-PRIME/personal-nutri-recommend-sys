"""
Food Filtering Model - Disease Based
=====================================
Filters foods based on user's diagnosed medical conditions.
Applies nutritional thresholds and disease-specific food exclusion rules.
Output: List of safe, disease-appropriate foods for the Recommendation Model.
"""

import os, sys
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class DiseaseFoodFilter:
    """
    Filters foods based on user-reported diseases/conditions.
    Combines hard exclusion (unsafe foods) + soft scoring (preferred foods).
    Supports 20 disease conditions including diabetes, hypertension, CKD, gout, etc.
    """

    # Nutritional limit keys mapped to dataset columns
    NUTRITION_COLUMNS = {
        'max_sodium_mg':        'sodium_mg',
        'max_sugar_g':          'sugar_g',
        'max_fat_g':            'fat_g',
        'max_calories':         'calories_per_100g',
        'min_fiber_g':          'fiber_g',
        'max_cholesterol_mg':   'cholesterol_mg',
        'max_saturated_fat_g':  'saturated_fat_g',
        'max_glycemic_index':   'glycemic_index',
        'max_purine_mg':        'purine_mg',
        'max_potassium_mg':     'potassium_mg',
        'max_phosphorus_mg':    'phosphorus_mg',
    }

    def __init__(self, food_data_path=None, disease_data_path=None,
                 food_df=None, disease_df=None):
        """Accept either file paths OR pre-loaded DataFrames (from MongoDB)."""
        if food_df is not None and disease_df is not None:
            self.food_df    = food_df.copy()
            self.disease_df = disease_df.copy()
        elif food_data_path and disease_data_path:
            self.food_df    = pd.read_csv(food_data_path)
            self.disease_df = pd.read_csv(disease_data_path)
        else:
            raise ValueError("Provide either DataFrames or file paths to DiseaseFoodFilter")
        self._preprocess_food_df()
        self._preprocess_disease_df()

    def _preprocess_food_df(self):
        """Ensure correct data types for food dataset."""
        bool_cols = [
            'contains_gluten', 'contains_dairy', 'contains_nuts', 'contains_eggs',
            'contains_shellfish', 'contains_fish', 'contains_soy', 'contains_sesame',
            'contains_peanuts', 'contains_sulfites', 'is_vegetarian', 'is_vegan'
        ]
        for col in bool_cols:
            if col in self.food_df.columns:
                self.food_df[col] = self.food_df[col].astype(str).str.lower() == 'true'

        numeric_cols = [
            'calories_per_100g', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g',
            'sugar_g', 'sodium_mg', 'cholesterol_mg', 'saturated_fat_g',
            'glycemic_index', 'purine_mg', 'oxalate_mg', 'potassium_mg',
            'calcium_mg', 'iron_mg'
        ]
        for col in numeric_cols:
            if col in self.food_df.columns:
                self.food_df[col] = pd.to_numeric(self.food_df[col], errors='coerce').fillna(0)

    def _preprocess_disease_df(self):
        """Parse disease dataset limit columns to numeric."""
        limit_cols = [
            'max_sodium_mg', 'max_sugar_g', 'max_fat_g', 'max_calories',
            'min_fiber_g', 'max_cholesterol_mg', 'max_saturated_fat_g',
            'max_glycemic_index', 'max_purine_mg', 'max_potassium_mg', 'max_phosphorus_mg'
        ]
        for col in limit_cols:
            if col in self.disease_df.columns:
                self.disease_df[col] = pd.to_numeric(self.disease_df[col], errors='coerce').fillna(9999)

    def _get_disease_rules(self, disease_name: str) -> Optional[pd.Series]:
        """Fuzzy-match disease name in dataset."""
        exact = self.disease_df[
            self.disease_df['disease_name'].str.lower() == disease_name.lower()
        ]
        if not exact.empty:
            return exact.iloc[0]

        fuzzy = self.disease_df[
            self.disease_df['disease_name'].str.lower().str.contains(disease_name.lower())
        ]
        if not fuzzy.empty:
            return fuzzy.iloc[0]

        # Try disease_id
        by_id = self.disease_df[
            self.disease_df['disease_id'].str.lower() == disease_name.lower()
        ]
        if not by_id.empty:
            return by_id.iloc[0]

        return None

    def _apply_nutritional_limits(
        self, df: pd.DataFrame, disease_rules: pd.Series
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Remove foods exceeding nutritional thresholds for a disease."""
        log = []
        filtered_df = df.copy()

        for limit_key, food_col in self.NUTRITION_COLUMNS.items():
            if food_col not in filtered_df.columns:
                continue

            limit_val = float(disease_rules.get(limit_key, 9999))
            if limit_val == 0 or limit_val == 9999:
                continue

            # min_fiber_g is a lower bound (keep foods WITH enough fiber — we don't exclude low-fiber,
            # but flag as less preferred; actual enforcement is at recommendation level)
            if limit_key == 'min_fiber_g':
                continue  # Handled in scoring, not hard filtering

            before = len(filtered_df)
            filtered_df = filtered_df[filtered_df[food_col] <= limit_val]
            removed = before - len(filtered_df)
            if removed > 0:
                log.append(
                    f"  Limit [{limit_key}={limit_val}] on '{food_col}' → removed {removed} foods"
                )

        return filtered_df, log

    def _apply_food_exclusions(
        self, df: pd.DataFrame, disease_rules: pd.Series
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Remove specific food_ids flagged as unsafe for the disease."""
        log = []
        avoid_str = str(disease_rules.get('avoid_food_ids', '')).strip()
        if not avoid_str or avoid_str == 'nan':
            return df, log

        avoid_ids = [x.strip() for x in avoid_str.split(',') if x.strip()]
        if not avoid_ids:
            return df, log

        flagged_names = df[df['food_id'].isin(avoid_ids)]['food_name'].tolist()
        filtered_df = df[~df['food_id'].isin(avoid_ids)]
        removed = len(df) - len(filtered_df)
        if removed > 0:
            log.append(f"  Excluded {removed} disease-specific unsafe foods: {flagged_names}")

        return filtered_df, log

    def _score_foods(
        self, df: pd.DataFrame, disease_rules: pd.Series
    ) -> pd.DataFrame:
        """
        Add a disease_suitability_score (0–100) to each food.
        Higher = more appropriate for this disease.
        """
        scored_df = df.copy()
        scored_df['disease_score'] = 50  # baseline

        # Preferred foods get +20
        prefer_str = str(disease_rules.get('prefer_food_ids', '')).strip()
        if prefer_str and prefer_str != 'nan':
            prefer_ids = [x.strip() for x in prefer_str.split(',') if x.strip()]
            scored_df.loc[scored_df['food_id'].isin(prefer_ids), 'disease_score'] += 20

        # Fiber bonus (fiber is almost universally beneficial)
        min_fiber = float(disease_rules.get('min_fiber_g', 0))
        if min_fiber > 0 and 'fiber_g' in scored_df.columns:
            scored_df.loc[scored_df['fiber_g'] >= min_fiber, 'disease_score'] += 10

        # Low calorie bonus for obesity/diabetes
        max_cal = float(disease_rules.get('max_calories', 9999))
        if max_cal < 2000 and 'calories_per_100g' in scored_df.columns:
            scored_df.loc[scored_df['calories_per_100g'] < 100, 'disease_score'] += 5

        # Low GI bonus for diabetes
        max_gi = float(disease_rules.get('max_glycemic_index', 9999))
        if max_gi < 9999 and 'glycemic_index' in scored_df.columns:
            scored_df.loc[scored_df['glycemic_index'] <= 40, 'disease_score'] += 10
            scored_df.loc[scored_df['glycemic_index'] == 0, 'disease_score'] -= 5  # unknown GI

        # Clip scores to 0–100
        scored_df['disease_score'] = scored_df['disease_score'].clip(0, 100)

        return scored_df

    def filter(
        self,
        user_diseases: List[str],
        input_foods_df: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Filter (and score) foods based on user diseases.

        Args:
            user_diseases: List of disease names e.g. ['Type 2 Diabetes', 'Hypertension']
            input_foods_df: Optional pre-filtered DataFrame (from allergy filter stage).
                            Uses full food_df if None.

        Returns:
            (filtered_scored_df, report)
        """
        base_df = input_foods_df.copy() if input_foods_df is not None else self.food_df.copy()

        if not user_diseases:
            return base_df, {
                'status': 'no_diseases',
                'total_foods_before': len(base_df),
                'total_foods_after':  len(base_df),
                'total_removed': 0,
                'per_disease_report': {},
                'filter_log': [],
            }

        safe_df = base_df.copy()
        all_logs = []
        disease_reports = {}
        not_found = []

        for disease in user_diseases:
            rules = self._get_disease_rules(disease)
            if rules is None:
                not_found.append(disease)
                all_logs.append(f"[WARNING] Disease '{disease}' not found in database")
                continue

            disease_name = rules['disease_name']
            before = len(safe_df)
            all_logs.append(f"\n[{disease_name.upper()}]")

            # Step 1: Hard nutritional limits
            safe_df, nutr_log = self._apply_nutritional_limits(safe_df, rules)
            all_logs.extend(nutr_log)

            # Step 2: Specific food exclusions
            safe_df, excl_log = self._apply_food_exclusions(safe_df, rules)
            all_logs.extend(excl_log)

            removed = before - len(safe_df)
            disease_reports[disease_name] = {
                'removed': removed,
                'dietary_notes': rules.get('notes', ''),
                'limits_applied': {
                    k: float(rules.get(k, 9999))
                    for k in self.NUTRITION_COLUMNS.keys()
                    if float(rules.get(k, 9999)) not in [0, 9999]
                }
            }

        # Step 3: Scoring (based on the first/primary disease)
        primary_rules = self._get_disease_rules(user_diseases[0])
        if primary_rules is not None:
            safe_df = self._score_foods(safe_df, primary_rules)
            safe_df = safe_df.sort_values('disease_score', ascending=False)

        report = {
            'status': 'filtered',
            'input_diseases': user_diseases,
            'diseases_not_found': not_found,
            'total_foods_before': len(base_df),
            'total_foods_after': len(safe_df),
            'total_removed': len(base_df) - len(safe_df),
            'per_disease_report': disease_reports,
            'filter_log': all_logs
        }

        return safe_df.reset_index(drop=True), report

    def get_dietary_guidelines(self, disease_name: str) -> str:
        """Return dietary notes for a specific disease."""
        rules = self._get_disease_rules(disease_name)
        if rules is not None:
            return rules.get('notes', 'No guidelines found.')
        return f"Disease '{disease_name}' not found in database."

    def list_supported_diseases(self) -> List[str]:
        """Return all disease names in the database."""
        return self.disease_df['disease_name'].tolist()


# ─────────────────────────────────────────────
# Example Usage
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import os

    BASE = os.path.dirname(os.path.abspath(__file__))
    food_path    = os.path.join(BASE, "../datasets/food_data.csv")
    disease_path = os.path.join(BASE, "../datasets/disease_diet_data.csv")

    model = DiseaseFoodFilter(food_path, disease_path)

    print("=" * 60)
    print("DISEASE FOOD FILTER - TEST RESULTS")
    print("=" * 60)

    # Test Case 1: Diabetic + Hypertension patient
    user_diseases = ["Type 2 Diabetes", "Hypertension"]
    safe_foods, report = model.filter(user_diseases)

    print(f"Diseases         : {report['input_diseases']}")
    print(f"Foods Before     : {report['total_foods_before']}")
    print(f"Foods After      : {report['total_foods_after']}")
    print(f"Foods Removed    : {report['total_removed']}")
    print("\n--- Per Disease Summary ---")
    for d, dr in report['per_disease_report'].items():
        print(f"  [{d}]: removed={dr['removed']}")
        print(f"    Limits: {dr['limits_applied']}")
        print(f"    Notes: {dr['dietary_notes'][:80]}...")
    print("\n--- Top Recommended Foods ---")
    cols = ['food_id', 'food_name', 'category', 'calories_per_100g',
            'sugar_g', 'sodium_mg', 'glycemic_index', 'disease_score']
    print(safe_foods[cols].head(15).to_string(index=False))

    # Test Case 2: CKD patient
    print("\n" + "=" * 60)
    ckd_foods, ckd_report = model.filter(["Kidney Disease"])
    print(f"CKD Safe Foods: {len(ckd_foods)} / {ckd_report['total_foods_before']}")
    print("Dietary Guidelines:")
    print(" ", model.get_dietary_guidelines("Kidney Disease"))

    # Test Case 3: Gout
    print("\n" + "=" * 60)
    gout_foods, gout_report = model.filter(["Gout"])
    print(f"Gout Safe Foods: {len(gout_foods)} / {gout_report['total_foods_before']}")
    print("\n--- Filter Log ---")
    for log in gout_report['filter_log']:
        print(log)

    print("\n--- Supported Diseases ---")
    for d in model.list_supported_diseases():
        print(f"  • {d}")
