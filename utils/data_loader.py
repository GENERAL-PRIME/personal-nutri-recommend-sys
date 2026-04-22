"""
utils/data_loader.py
======================
Loads all four datasets (food, allergy, disease, dislike) from MongoDB.
Falls back to CSV files if MongoDB is not connected (local dev only).

Usage:
    from utils.data_loader import load_datasets
    food_df, allergy_df, disease_df, dislike_df = load_datasets()

The first call loads from MongoDB and caches in memory.
Subsequent calls return the cached DataFrames (fast).
"""

import os
import sys
import pandas as pd
from typing import Tuple

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── In-memory cache ────────────────────────────────────────────────────────────
_CACHE: dict = {}


def _csv_path(filename: str) -> str:
    return os.path.join(_PROJECT_ROOT, "datasets", filename)


def _load_from_mongo(collection_name: str) -> pd.DataFrame:
    """Load a collection from MongoDB into a DataFrame."""
    from utils import db as mdb
    col = getattr(mdb, f"{collection_name}_col", None) if hasattr(mdb, f"{collection_name}_col") else None

    # db.py only exposes users_col and plans_col — datasets use db directly
    if mdb.db is None:
        raise RuntimeError("MongoDB not connected")

    coll = mdb.db[collection_name]
    docs = list(coll.find({}, {"_id": 0}))   # exclude Mongo _id field
    if not docs:
        raise ValueError(f"Collection '{collection_name}' is empty in MongoDB")
    return pd.DataFrame(docs)


def _load_df(collection_name: str, csv_filename: str) -> pd.DataFrame:
    """Try MongoDB first, fall back to CSV."""
    # Try MongoDB
    try:
        df = _load_from_mongo(collection_name)
        print(f"[DataLoader] ✅  Loaded '{collection_name}' from MongoDB ({len(df)} rows)")
        return df
    except Exception as e:
        print(f"[DataLoader] ⚠   MongoDB load failed for '{collection_name}': {e}")

    # Fall back to CSV
    csv = _csv_path(csv_filename)
    if os.path.exists(csv):
        df = pd.read_csv(csv)
        print(f"[DataLoader] ℹ   Loaded '{collection_name}' from CSV ({len(df)} rows)")
        return df

    raise FileNotFoundError(
        f"Could not load '{collection_name}' from MongoDB or CSV.\n"
        f"Run 'python migrate_to_mongo.py' to upload datasets to MongoDB first."
    )


def load_datasets(force_reload: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns (food_df, allergy_df, disease_df, dislike_df).
    Results are cached after the first call.

    Args:
        force_reload: if True, clears cache and reloads from source.
    """
    global _CACHE
    if force_reload:
        _CACHE.clear()

    if "food" not in _CACHE:
        _CACHE["food"]    = _load_df("food_data",         "food_data.csv")
        _CACHE["allergy"] = _load_df("allergy_data",      "allergy_data.csv")
        _CACHE["disease"] = _load_df("disease_diet_data", "disease_diet_data.csv")
        _CACHE["dislike"] = _load_df("dislike_data",      "dislike_data.csv")

    return (
        _CACHE["food"].copy(),
        _CACHE["allergy"].copy(),
        _CACHE["disease"].copy(),
        _CACHE["dislike"].copy(),
    )


def get_food_df()    -> pd.DataFrame: return load_datasets()[0]
def get_allergy_df() -> pd.DataFrame: return load_datasets()[1]
def get_disease_df() -> pd.DataFrame: return load_datasets()[2]
def get_dislike_df() -> pd.DataFrame: return load_datasets()[3]
