import pandas as pd
from utils import db as mdb
from typing import Tuple

_CACHE: dict = {}

def _load_from_mongo(collection_name: str) -> pd.DataFrame:
    """Strictly loads data from MongoDB Atlas."""
    if mdb.db is None:
        raise RuntimeError("MongoDB not connected. Check your environment variables.")
        
    coll = mdb.db[collection_name]
    docs = list(coll.find({}, {"_id": 0}))   # exclude Mongo _id field
    
    if not docs:
        raise ValueError(f"Collection '{collection_name}' is empty in MongoDB.")
    print(f"[DataLoader] ✅ Successfully loaded '{collection_name}' from MongoDB ({len(docs)} rows)")    
    return pd.DataFrame(docs)

def load_datasets(force_reload: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns (food_df, allergy_df, disease_df, dislike_df) strictly from MongoDB.
    Results are cached after the first call to keep the app fast.
    """
    global _CACHE
    if force_reload:
        _CACHE.clear()

    if "food" not in _CACHE:
        print("[DataLoader] 🌐 Fetching all datasets from MongoDB...")
        _CACHE["food"]    = _load_from_mongo("food_data")
        _CACHE["allergy"] = _load_from_mongo("allergy_data")
        _CACHE["disease"] = _load_from_mongo("disease_diet_data")
        _CACHE["dislike"] = _load_from_mongo("dislike_data")

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