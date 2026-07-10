"""
utils/data_loader.py
=====================
Loads all four reference datasets strictly from MongoDB Atlas.

Collections expected in the database:
  food_data         → food nutritional records
  allergy_data      → allergen rules
  disease_diet_data → disease-specific nutrition rules
  dislike_data      → dislike / dietary-preference exclusion rules

All results are in-process cached after the first fetch so repeated
calls within the same worker process do not hit the network.

Call load_datasets(force_reload=True) to invalidate the cache
(e.g. after an admin data update).
"""

import pandas as pd
from utils import db as mdb
from typing import Tuple

_CACHE: dict = {}

# Expected collection names
_COLLECTIONS = {
    "food":    "food_data",
    "allergy": "allergy_data",
    "disease": "disease_diet_data",
    "dislike": "dislike_data",
}


def _load_from_mongo(key: str) -> pd.DataFrame:
    """Fetch one collection from Atlas and return as DataFrame."""
    if mdb.db is None:
        raise RuntimeError(
            "MongoDB is not connected. "
            "Make sure MONGO_URI is set and the Atlas cluster is reachable."
        )
    collection_name = _COLLECTIONS[key]
    coll = mdb.db[collection_name]

    # Exclude MongoDB _id to avoid ObjectId serialisation issues
    docs = list(coll.find({}, {"_id": 0}))

    if not docs:
        raise ValueError(
            f"Collection '{collection_name}' is empty in MongoDB Atlas. "
            "Please upload the reference data before starting the app."
        )

    df = pd.DataFrame(docs)
    print(f"[DataLoader] ✅  Loaded '{collection_name}' from Atlas ({len(df)} rows).")
    return df


def load_datasets(force_reload: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Return (food_df, allergy_df, disease_df, dislike_df) from MongoDB Atlas.

    Results are cached for the lifetime of the worker process.
    Pass force_reload=True to re-fetch all collections (e.g. after a data update).
    """
    global _CACHE
    if force_reload:
        _CACHE.clear()
        print("[DataLoader] 🔄  Cache cleared — re-fetching from Atlas.")

    if "food" not in _CACHE:
        print("[DataLoader] 🌐  Fetching all reference datasets from Atlas…")
        for key in _COLLECTIONS:
            _CACHE[key] = _load_from_mongo(key)

    return (
        _CACHE["food"].copy(),
        _CACHE["allergy"].copy(),
        _CACHE["disease"].copy(),
        _CACHE["dislike"].copy(),
    )


# Convenience accessors
def get_food_df()    -> pd.DataFrame: return load_datasets()[0]
def get_allergy_df() -> pd.DataFrame: return load_datasets()[1]
def get_disease_df() -> pd.DataFrame: return load_datasets()[2]
def get_dislike_df() -> pd.DataFrame: return load_datasets()[3]


def reload_datasets() -> None:
    """Force-reload all datasets from Atlas (call from admin endpoint)."""
    load_datasets(force_reload=True)
