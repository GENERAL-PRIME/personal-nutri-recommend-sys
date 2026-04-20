# ...existing code...
from pathlib import Path
import os, json
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME")

if not MONGO_URI:
    raise SystemExit("MONGO_URI not set in .env")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB] if MONGO_DB else client.get_default_database()

DATA_DIR = Path(__file__).resolve().parents[1] / "datasets"

mappings = {
    "food_data.csv": "food_data",
    "allergy_data.csv": "allergies",
    "disease_diet_data.csv": "disease_diet_data",
    "dislike_data.csv": "dislikes",
}

for fname, coll_name in mappings.items():
    f = DATA_DIR / fname
    if not f.exists():
        print(f"Skipping missing: {f}")
        continue
    print("Loading", f.name)
    df = pd.read_csv(f)
    df = df.where(pd.notnull(df), None)
    docs = df.to_dict(orient="records")
    if not docs:
        print("No rows in", f)
        continue
    coll = db[coll_name]
    # optional: create index on name if exists
    if "name" in df.columns:
        coll.create_index("name")
    # insert (non-destructive: insert_many; duplicates will duplicate unless you handle unique index)
    res = coll.insert_many(docs)
    print(f"Inserted {len(res.inserted_ids)} into {coll_name}")