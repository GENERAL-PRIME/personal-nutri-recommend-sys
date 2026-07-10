"""
Food Filtering Model - Disease Based  (v2 — improved scoring)
=============================================================
Key improvements vs v1:
  - disease_score is a NORMALIZED 0-100 composite from weighted sub-signals.
  - Hard limits: 0 in disease table = "not applicable" (sentinel) — skipped.
  - max_calories and min_fiber are DAILY targets — used only for scoring,
    never as hard per-food exclusion filters.
  - Unknown GI (=0) is treated as neutral-negative for metabolic conditions.
  - Multiple diseases merged to strictest limit per signal.
  - All public interfaces unchanged (drop-in replacement).
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
    Combines hard exclusion + normalized composite scoring.
    """

    # Per-food hard-limit columns.  0 = sentinel "not applicable" → skip.
    # max_calories and min_fiber are DAILY targets — NOT here.
    HARD_LIMIT_COLUMNS = {
        'max_sodium_mg':        'sodium_mg',
        'max_sugar_g':          'sugar_g',
        'max_fat_g':            'fat_g',
        'max_cholesterol_mg':   'cholesterol_mg',
        'max_saturated_fat_g':  'saturated_fat_g',
        'max_glycemic_index':   'glycemic_index',
        'max_purine_mg':        'purine_mg',
        'max_potassium_mg':     'potassium_mg',
        'max_phosphorus_mg':    'phosphorus_mg',
    }

    NUTRITION_COLUMNS = {
        **HARD_LIMIT_COLUMNS,
        'max_calories': 'calories_per_100g',
        'min_fiber_g':  'fiber_g',
    }

    # Composite scoring weights (must sum to 1.0)
    _W = {
        'sodium':      0.20,
        'sugar':       0.15,
        'gi':          0.18,
        'fiber':       0.15,
        'fat':         0.10,
        'sat_fat':     0.08,
        'calories':    0.07,
        'cholesterol': 0.07,
    }

    def __init__(self, food_data_path=None, disease_data_path=None,
                 food_df=None, disease_df=None):
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
        bool_cols = [
            'contains_gluten','contains_dairy','contains_nuts','contains_eggs',
            'contains_shellfish','contains_fish','contains_soy','contains_sesame',
            'contains_peanuts','contains_sulfites','is_vegetarian','is_vegan',
        ]
        for col in bool_cols:
            if col in self.food_df.columns:
                self.food_df[col] = self.food_df[col].astype(str).str.lower() == 'true'
        numeric_cols = [
            'calories_per_100g','protein_g','carbs_g','fat_g','fiber_g',
            'sugar_g','sodium_mg','cholesterol_mg','saturated_fat_g',
            'glycemic_index','purine_mg','oxalate_mg','potassium_mg',
            'calcium_mg','iron_mg','phosphorus_mg',
        ]
        for col in numeric_cols:
            if col in self.food_df.columns:
                self.food_df[col] = pd.to_numeric(self.food_df[col], errors='coerce').fillna(0)

    def _preprocess_disease_df(self):
        for col in self.NUTRITION_COLUMNS:
            if col in self.disease_df.columns:
                self.disease_df[col] = pd.to_numeric(self.disease_df[col], errors='coerce')

    # ── Public API ─────────────────────────────────────────────────────────

    def filter(
        self,
        user_diseases: List[str],
        input_foods_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[pd.DataFrame, Dict]:

        df = input_foods_df.copy() if input_foods_df is not None else self.food_df.copy()
        report: Dict = {
            'diseases_matched':    [],
            'total_foods_before':  len(df),
            'foods_excluded_total':0,
            'scoring_applied':     False,
            'log':                 [],
        }

        if not user_diseases:
            df['disease_score'] = 50
            report['total_foods_after'] = len(df)
            return df, report

        matched_rules = self._match_diseases(user_diseases)
        if not matched_rules:
            df['disease_score'] = 50
            report['total_foods_after'] = len(df)
            report['log'].append("No matching disease rules found; default score applied.")
            return df, report

        report['diseases_matched'] = [r['disease_name'] for r in matched_rules]
        log = report['log']

        df, log = self._apply_hard_limits(df, matched_rules, log)
        df, log = self._apply_food_exclusions(df, matched_rules, log)
        report['foods_excluded_total'] = report['total_foods_before'] - len(df)

        df = self._score_foods(df, matched_rules)
        report['scoring_applied']   = True
        report['total_foods_after'] = len(df)

        df = df.sort_values('disease_score', ascending=False).reset_index(drop=True)
        return df, report

    # ── Private ───────────────────────────────────────────────────────────────

    def _match_diseases(self, user_diseases: List[str]) -> List:
        matched = []
        for ud in user_diseases:
            ud_l = ud.strip().lower()
            for _, row in self.disease_df.iterrows():
                db_l = str(row.get('disease_name', '')).lower()
                if ud_l in db_l or db_l in ud_l:
                    matched.append(row)
                    break
        return matched

    def _apply_hard_limits(self, df, rules, log):
        """
        Hard-filter only per-food nutrient columns.
        Skip limit when the rule value is 0 (sentinel = not applicable)
        or NaN.  max_calories and min_fiber are NOT here.
        """
        for rule in rules:
            disease = rule.get('disease_name', 'Unknown')
            for limit_col, food_col in self.HARD_LIMIT_COLUMNS.items():
                if food_col not in df.columns:
                    continue
                raw = rule.get(limit_col)
                if raw is None:
                    continue
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    continue
                # 0 = "not applicable" sentinel; NaN = not set → skip both
                if pd.isna(val) or val <= 0:
                    continue
                before = len(df)
                df = df[df[food_col] <= val]
                removed = before - len(df)
                if removed:
                    log.append(f"  [{disease}] Removed {removed} foods with {food_col} > {val}")
        return df, log

    def _apply_food_exclusions(self, df, rules, log):
        avoid_ids: set = set()
        for rule in rules:
            s = str(rule.get('avoid_food_ids', '')).strip()
            if s and s != 'nan':
                avoid_ids.update(x.strip() for x in s.split(',') if x.strip())
        if avoid_ids:
            before = len(df)
            df = df[~df['food_id'].isin(avoid_ids)]
            log.append(f"  Excluded {before - len(df)} disease-specific unsafe foods")
        return df, log

    def _score_foods(self, df: pd.DataFrame, rules: List) -> pd.DataFrame:
        scored   = df.copy()
        merged   = self._merge_rules(rules)
        gi_is_key = merged.get('gi') is not None and merged['gi'] < 9999

        prefer_ids: set = set()
        for rule in rules:
            s = str(rule.get('prefer_food_ids', '')).strip()
            if s and s != 'nan':
                prefer_ids.update(x.strip() for x in s.split(',') if x.strip())

        scores = []
        for _, row in scored.iterrows():
            s = self._row_score(row, merged, gi_is_key)
            if str(row.get('food_id', '')) in prefer_ids:
                s = min(s + 10.0, 100.0)
            scores.append(round(s, 1))
        scored['disease_score'] = scores
        return scored

    def _merge_rules(self, rules: List) -> Dict:
        """Strictest applicable limit per signal (skip 0/NaN)."""
        signal_col = {
            'sodium':      ('max_sodium_mg',      False),
            'sugar':       ('max_sugar_g',         False),
            'fat':         ('max_fat_g',           False),
            'sat_fat':     ('max_saturated_fat_g', False),
            'calories':    ('max_calories',        False),
            'gi':          ('max_glycemic_index',  False),
            'cholesterol': ('max_cholesterol_mg',  False),
            'fiber':       ('min_fiber_g',         True),
        }
        merged = {}
        for signal, (col, is_min) in signal_col.items():
            vals = []
            for r in rules:
                raw = r.get(col)
                if raw is None:
                    continue
                try:
                    v = float(raw)
                except (TypeError, ValueError):
                    continue
                if pd.isna(v):
                    continue
                # For max_ limits, 0 = not applicable; skip
                if not is_min and v <= 0:
                    continue
                vals.append(v)
            if vals:
                merged[signal] = max(vals) if is_min else min(vals)
        return merged

    def _row_score(self, row, merged: Dict, gi_is_key: bool) -> float:
        w = self._W

        def _clamp(val: float, limit: float) -> float:
            """Linear: val=0 → 1.0 (best), val=limit → 0.0 (worst)."""
            if limit <= 0:
                return 0.5
            return max(0.0, min(1.0, 1.0 - val / limit))

        def _fiber(val: float, daily_target: float) -> float:
            target = daily_target if daily_target > 0 else 25.0
            return min(1.0, val / target)

        total_w = 0.0
        w_sum   = 0.0

        # Sodium
        na_lim = merged.get('sodium', 2300)
        w_sum += w['sodium'] * _clamp(float(row.get('sodium_mg', 0)), na_lim)
        total_w += w['sodium']

        # Sugar
        su_lim = merged.get('sugar', 50)
        w_sum += w['sugar'] * _clamp(float(row.get('sugar_g', 0)), su_lim)
        total_w += w['sugar']

        # GI
        gi_val = float(row.get('glycemic_index', 0))
        gi_lim = merged.get('gi')
        if gi_lim and gi_lim < 9999:
            gi_sig = 0.3 if gi_val == 0 and gi_is_key else (
                0.5 if gi_val == 0 else _clamp(gi_val, gi_lim))
        else:
            if gi_val == 0:   gi_sig = 0.5
            elif gi_val <= 40: gi_sig = 1.0
            elif gi_val <= 55: gi_sig = 0.75
            elif gi_val <= 70: gi_sig = 0.5
            else:              gi_sig = 0.25
        w_sum += w['gi'] * gi_sig
        total_w += w['gi']

        # Fiber (reward)
        fiber_target = merged.get('fiber', 25.0)
        w_sum += w['fiber'] * _fiber(float(row.get('fiber_g', 0)), fiber_target)
        total_w += w['fiber']

        # Fat
        fat_lim = merged.get('fat', 70)
        w_sum += w['fat'] * _clamp(float(row.get('fat_g', 0)), fat_lim)
        total_w += w['fat']

        # Saturated fat
        sf_lim = merged.get('sat_fat', 20)
        w_sum += w['sat_fat'] * _clamp(float(row.get('saturated_fat_g', 0)), sf_lim)
        total_w += w['sat_fat']

        # Calories — daily target scaled to per-100g proxy
        cal_daily = merged.get('calories', 2200)
        cal_proxy = cal_daily / 9.0
        w_sum += w['calories'] * _clamp(float(row.get('calories_per_100g', 0)), cal_proxy)
        total_w += w['calories']

        # Cholesterol
        chol_lim = merged.get('cholesterol', 300)
        w_sum += w['cholesterol'] * _clamp(float(row.get('cholesterol_mg', 0)), chol_lim)
        total_w += w['cholesterol']

        score = (w_sum / total_w) * 100.0 if total_w > 0 else 50.0
        return round(max(0.0, min(100.0, score)), 1)
