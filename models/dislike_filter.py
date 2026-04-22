"""
Food Filtering Model - Dislike / Preference Based
===================================================
Filters foods based on user's stated food dislikes, dietary choices,
cultural restrictions, and personal taste preferences.
"""

import os, sys
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
from typing import List, Dict, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class DislikeFoodFilter:

    # ── Boolean column filters ────────────────────────────────────────────────
    BOOLEAN_FILTERS = {
        'vegan':          ('is_vegan',      True),
        'vegetarian':     ('is_vegetarian', True),
        'non-vegetarian': ('is_vegetarian', False),
    }

    # ── Category-level filters ────────────────────────────────────────────────
    CATEGORY_FILTERS = {
        'seafood':      ['seafood'],
        'red meat':     ['meat dishes'],
        'eggs':         ['egg dishes', 'eggs & poultry'],
        'dairy':        ['dairy', 'dairy & paneer', 'dairy & fats'],
        'nuts':         ['nuts & seeds'],
        'legumes':      ['legumes', 'dals & legumes'],
        'soy':          ['soy products'],
        'grains':       ['grains', 'breads & flatbreads'],
    }

    # ── Special rules: handled entirely by custom logic in filter() ───────────
    # Keys must be lowercase.  Each entry is a dict describing what to do.
    SPECIAL_RULES = {

        # ── Jain Diet ─────────────────────────────────────────────────────────
        # Jains avoid: meat, fish, eggs, root/underground vegetables,
        # onion, garlic. Dairy IS allowed.
        'jain diet': {
            'description': 'Jain diet — no meat/fish/eggs, no root/underground vegetables',
            'remove_non_vegetarian': True,   # is_vegetarian == False
            'remove_eggs':           True,   # contains_eggs == True
            # keyword match on food_name (case-insensitive)
            'name_keywords': [
                'potato','aloo','carrot','gajar','beet','chukandar',
                'radish','mooli','turnip','yam','suran','zimikand',
                'arbi','colocasia','lotus stem','kamal kakdi',
                'sweet potato','shakarkand','tapioca',
                'onion','pyaaz','garlic','lahasun',
                'leek','shallot','spring onion','scallion',
                'meat stock','bone broth','chicken stock',
                'egg nog','boiled egg','fried egg','scrambled egg',
                'poached egg','egg drop','egg sauce',
            ],
        },

        # ── Fried Foods ───────────────────────────────────────────────────────
        'fried foods': {
            'description': 'Fried foods — pakoras, vadai, puri, samosa, etc.',
            'name_keywords': [
                'pakora','pakoda','vada','wada','vadai','bonda',
                'samosa','kachori','puri','poori','bhatura','bhature',
                'fafda','sev ','papdi','murukku','chakli',
                'fried','fry ','fritter','aigrette',
                'bread roll','potato bonda','bread pakora',
            ],
        },

        # ── Spicy Foods ───────────────────────────────────────────────────────
        'spicy foods': {
            'description': 'Spicy/hot foods — vindaloo, laal maas, mirchi, etc.',
            'name_keywords': [
                'vindaloo','laal maas','chettinad','mirchi ka salan',
                'hot and sour','schezwan','chilli chicken','chilli paneer',
                'chilli sauce','green chilli sauce','chilli ',
                'szechuan','szechwan',
            ],
        },

        # ── No Beef ──────────────────────────────────────────────────────────
        'no beef': {
            'description': 'No beef and beef-derived products',
            'id_prefix': ['B0'],   # all B001–B020
            'name_keywords': ['beef','steak','burger patty'],
        },

        # ── No Pork ──────────────────────────────────────────────────────────
        'no pork': {
            'description': 'No pork and pork-derived products',
            'id_prefix': ['P0'],   # all P001–P020
            'name_keywords': ['pork','bacon','ham ','chourico','sorpotel','pandi'],
        },
    }

    # ── Root vegetable keywords (also used stand-alone) ───────────────────────
    ROOT_VEG_KEYWORDS = [
        'potato','aloo','carrot','gajar','beet','chukandar',
        'radish','mooli','turnip','yam','suran','zimikand',
        'arbi','colocasia','lotus stem','kamal kakdi',
        'sweet potato','shakarkand','tapioca',
        'onion','pyaaz','garlic','lahasun',
    ]

    def __init__(self, food_data_path=None, dislike_data_path=None,
                 food_df=None, dislike_df=None):
        """Accept either file paths OR pre-loaded DataFrames (from MongoDB)."""
        if food_df is not None and dislike_df is not None:
            self.food_df    = food_df.copy()
            self.dislike_df = dislike_df.copy()
        elif food_data_path and dislike_data_path:
            self.food_df    = pd.read_csv(food_data_path)
            self.dislike_df = pd.read_csv(dislike_data_path)
        else:
            raise ValueError("Provide either DataFrames or file paths to DislikeFoodFilter")
        self._preprocess()

    def _preprocess(self):
        bool_cols = ['is_vegetarian', 'is_vegan', 'contains_eggs',
                     'contains_dairy', 'contains_nuts', 'contains_fish',
                     'contains_shellfish']
        for col in bool_cols:
            if col in self.food_df.columns:
                self.food_df[col] = (
                    self.food_df[col].astype(str).str.lower() == 'true'
                )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _name_mask(self, df: pd.DataFrame, keywords: list) -> pd.Series:
        """Return boolean mask for rows whose food_name contains any keyword."""
        lower_name = df['food_name'].str.lower()
        return lower_name.apply(lambda n: any(k in n for k in keywords))

    def _prefix_mask(self, df: pd.DataFrame, prefixes: list) -> pd.Series:
        """Return boolean mask for rows whose food_id starts with any prefix."""
        return df['food_id'].apply(
            lambda fid: any(fid.startswith(p) for p in prefixes)
        )

    def _apply_special_rule(
        self, df: pd.DataFrame, rule_key: str
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Apply a SPECIAL_RULES entry. Returns (filtered_df, removed_names)."""
        rule = self.SPECIAL_RULES[rule_key]
        removed = []

        # Remove non-vegetarian
        if rule.get('remove_non_vegetarian'):
            mask = df['is_vegetarian'] == False
            removed += df[mask]['food_name'].tolist()
            df = df[~mask]

        # Remove egg-containing foods
        if rule.get('remove_eggs') and 'contains_eggs' in df.columns:
            mask = df['contains_eggs'] == True
            removed += df[mask]['food_name'].tolist()
            df = df[~mask]

        # Remove by food_id prefix
        if rule.get('id_prefix'):
            mask = self._prefix_mask(df, rule['id_prefix'])
            removed += df[mask]['food_name'].tolist()
            df = df[~mask]

        # Remove by food name keywords
        if rule.get('name_keywords'):
            mask = self._name_mask(df, rule['name_keywords'])
            removed += df[mask]['food_name'].tolist()
            df = df[~mask]

        return df, list(set(removed))

    def _get_dislike_rules(self, dislike_name: str) -> Optional[pd.Series]:
        """Look up dislike_data.csv (exact then partial match)."""
        exact = self.dislike_df[
            self.dislike_df['dislike_name'].str.lower() == dislike_name.lower()
        ]
        if not exact.empty:
            return exact.iloc[0]
        partial = self.dislike_df[
            self.dislike_df['dislike_name'].str.lower().str.contains(
                dislike_name.lower(), regex=False
            )
        ]
        if not partial.empty:
            return partial.iloc[0]
        return None

    def _parse_food_ids(self, id_string: str) -> List[str]:
        if not id_string or str(id_string).strip() in ('nan', ''):
            return []
        return [x.strip() for x in str(id_string).split(',') if x.strip()]

    # ── Public filter ─────────────────────────────────────────────────────────

    def filter(
        self,
        user_dislikes: List[str],
        input_foods_df: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, Dict]:

        base_df = input_foods_df.copy() if input_foods_df is not None \
                  else self.food_df.copy()

        if not user_dislikes:
            return base_df, {
                'status':             'no_dislikes',
                'total_foods_before': len(base_df),
                'total_foods_after':  len(base_df),
                'total_removed':      0,
                'removed_by_dislike': {},
                'filter_log':         [],
            }

        safe_df = base_df.copy()
        filter_log         = []
        removed_by_dislike = {}
        not_found          = []

        for dislike in user_dislikes:
            dislike_lower = dislike.strip().lower()
            before = len(safe_df)

            # ── 1. Special rules (Jain, Fried, Spicy, No Beef, No Pork) ──────
            if dislike_lower in self.SPECIAL_RULES:
                safe_df, removed_names = self._apply_special_rule(
                    safe_df, dislike_lower
                )
                removed = before - len(safe_df)
                desc    = self.SPECIAL_RULES[dislike_lower]['description']
                if removed > 0:
                    removed_by_dislike[dislike] = removed_names
                    filter_log.append(
                        f"[{dislike.upper()}] {desc} → removed {removed} foods"
                    )
                else:
                    filter_log.append(f"[{dislike.upper()}] {desc} → none removed")
                continue

            # ── 2. Boolean preference filters (vegan / vegetarian) ────────────
            if dislike_lower in self.BOOLEAN_FILTERS:
                col, value = self.BOOLEAN_FILTERS[dislike_lower]
                if col in safe_df.columns:
                    removed_names = safe_df[safe_df[col] != value]['food_name'].tolist()
                    safe_df       = safe_df[safe_df[col] == value]
                    removed       = before - len(safe_df)
                    if removed > 0:
                        removed_by_dislike[dislike] = removed_names
                        filter_log.append(
                            f"[{dislike.upper()}] Preference '{col}=={value}'"
                            f" → removed {removed} foods"
                        )
                continue

            # ── 3. Category-level filters ─────────────────────────────────────
            if dislike_lower in self.CATEGORY_FILTERS:
                cat_keywords  = self.CATEGORY_FILTERS[dislike_lower]
                mask          = safe_df['category'].str.lower().apply(
                    lambda c: any(kw in c for kw in cat_keywords)
                )
                removed_names = safe_df[mask]['food_name'].tolist()
                safe_df       = safe_df[~mask]
                removed       = before - len(safe_df)
                if removed > 0:
                    removed_by_dislike[dislike] = removed_names
                    filter_log.append(
                        f"[{dislike.upper()}] Category filter → removed {removed} foods"
                    )
                continue

            # ── 4. Dataset-driven rules (dislike_data.csv) ────────────────────
            rules = self._get_dislike_rules(dislike)
            if rules is not None:
                removed_names = []

                food_ids = self._parse_food_ids(rules.get('related_food_ids', ''))
                if food_ids:
                    removed_names += safe_df[safe_df['food_id'].isin(food_ids)]['food_name'].tolist()
                    safe_df = safe_df[~safe_df['food_id'].isin(food_ids)]

                cat_str = str(rules.get('related_categories', '')).strip()
                if cat_str and cat_str != 'nan':
                    for cat in [c.strip().lower() for c in cat_str.split(',') if c.strip()]:
                        cat_mask = safe_df['category'].str.lower().str.contains(
                            cat, regex=False
                        )
                        removed_names += safe_df[cat_mask]['food_name'].tolist()
                        safe_df = safe_df[~cat_mask]

                removed = before - len(safe_df)
                if removed > 0:
                    removed_by_dislike[dislike] = list(set(removed_names))
                    filter_log.append(
                        f"[{dislike.upper()}] {rules.get('notes','')} → removed {removed} foods"
                    )
                else:
                    filter_log.append(f"[{dislike.upper()}] No matching foods found")
            else:
                not_found.append(dislike)
                filter_log.append(
                    f"[WARNING] '{dislike}' not in database — skipped"
                )

        return safe_df.reset_index(drop=True), {
            'status':              'filtered',
            'input_dislikes':      user_dislikes,
            'dislikes_not_found':  not_found,
            'total_foods_before':  len(base_df),
            'total_foods_after':   len(safe_df),
            'total_removed':       len(base_df) - len(safe_df),
            'removed_by_dislike':  removed_by_dislike,
            'filter_log':          filter_log,
        }

    def list_supported_dislikes(self) -> List[str]:
        special  = list(self.SPECIAL_RULES.keys())
        boolean  = list(self.BOOLEAN_FILTERS.keys())
        category = list(self.CATEGORY_FILTERS.keys())
        dataset  = self.dislike_df['dislike_name'].tolist()
        return sorted(set(special + boolean + category + dataset))
