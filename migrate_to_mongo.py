"""
migrate_to_mongo.py
=====================
One-time migration script. Run this ONCE from your project root:

    python migrate_to_mongo.py

What it does:
  1. Uploads food_data.csv, allergy_data.csv, disease_diet_data.csv,
     dislike_data.csv  →  MongoDB collections (food_data, allergy_data, etc.)
  2. Migrates outputs/users_registry.json  →  users collection
  3. Migrates any existing *_diet_plan.json files  →  plans collection

Safe to re-run: existing documents are replaced, not duplicated.
"""

import os, sys, json
from pathlib import Path
from datetime import datetime, timezone

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# ── Load environment ───────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(_HERE / ".env")

# ── Check MongoDB connection ───────────────────────────────────────────────────
from utils import db as mdb

if mdb.db is None:
    print("\n❌  MongoDB is not connected.")
    print("   Check that MONGO_URI and MONGO_DB_NAME are set correctly in your .env file.")
    print("   Also make sure your IP is whitelisted in MongoDB Atlas Network Access.")
    sys.exit(1)

print(f"\n✅  Connected to MongoDB database: '{os.environ.get('MONGO_DB_NAME','nutriai')}'\n")

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# PART 1: Upload CSV datasets
# ──────────────────────────────────────────────────────────────────────────────

DATASETS_DIR = _HERE / "datasets"

CSV_TO_COLLECTION = {
    "food_data.csv":         "food_data",
    "allergy_data.csv":      "allergy_data",
    "disease_diet_data.csv": "disease_diet_data",
    "dislike_data.csv":      "dislike_data",
}

print("=" * 55)
print("PART 1 — Uploading datasets to MongoDB")
print("=" * 55)

for csv_file, coll_name in CSV_TO_COLLECTION.items():
    csv_path = DATASETS_DIR / csv_file
    if not csv_path.exists():
        print(f"  ⚠  {csv_file} not found — skipping")
        continue

    df = pd.read_csv(csv_path)
    # Replace NaN with None so MongoDB accepts it
    df = df.where(pd.notnull(df), None)
    docs = df.to_dict(orient="records")

    coll = mdb.db[coll_name]
    # Drop and re-insert for a clean slate (idempotent)
    coll.drop()
    if not docs:
        print(f"  ⚠  {csv_file} has 0 rows — skipping insert")
        continue
    # Insert in batches of 200 to avoid document size limits
    batch = 200
    inserted = 0
    for i in range(0, len(docs), batch):
        try:
            coll.insert_many(docs[i:i+batch], ordered=False)
            inserted += len(docs[i:i+batch])
        except Exception as be:
            print(f"  ⚠  Batch insert error: {be}")
    # Create useful indexes
    try:
        if coll_name == "food_data":
            coll.create_index("food_id", unique=True)
            coll.create_index("meal_role")
            coll.create_index("region_zone")
        elif coll_name == "allergy_data":
            coll.create_index("allergy_name", sparse=True)
        elif coll_name == "disease_diet_data":
            coll.create_index("disease_name", sparse=True)
        elif coll_name == "dislike_data":
            coll.create_index("dislike_name", sparse=True)
    except Exception as idx_e:
        print(f"  ⚠  Index creation note: {idx_e}")

    status = "✅" if inserted == len(docs) else "⚠ "
    print(f"  {status}  {csv_file:<30} → '{coll_name}'  ({inserted}/{len(docs)} documents)")

# ──────────────────────────────────────────────────────────────────────────────
# PART 2: Migrate existing users from users_registry.json
# ──────────────────────────────────────────────────────────────────────────────

print()
print("=" * 55)
print("PART 2 — Migrating users from users_registry.json")
print("=" * 55)

registry_path = _HERE / "outputs" / "users_registry.json"
migrated_users = 0

if registry_path.exists():
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)

    users_map = data.get("users", {})
    id_counter = data.get("id_counter", 0)

    for uid, profile in users_map.items():
        if not isinstance(profile, dict):
            continue
        doc = {
            "user_id":            uid,
            "name":               profile.get("name"),
            "age":                profile.get("age"),
            "sex":                profile.get("sex"),
            "weight_kg":          profile.get("weight_kg"),
            "height_cm":          profile.get("height_cm"),
            "dietary_preference": profile.get("dietary_preference", "none"),
            "allergies":          profile.get("allergies", []),
            "diseases":           profile.get("diseases",  []),
            "dislikes":           profile.get("dislikes",  []),
            "registered_at":      profile.get("registered_at", datetime.now(timezone.utc).isoformat()),
            "last_run":           profile.get("last_run"),
            "last_plan_id":       None,
            # NOTE: password not set for migrated users.
            # They will need to use the "Forgot/Set Password" flow.
        }
        # Upsert — don't overwrite if already in Mongo
        mdb.users_col.update_one(
            {"user_id": uid},
            {"$setOnInsert": doc},
            upsert=True
        )
        migrated_users += 1
        print(f"  ✅  Migrated user {uid} ({profile.get('name','')})")

    # Store the counter so new IDs continue from the right number
    mdb.db["counters"].update_one(
        {"_id": "user_id"},
        {"$setOnInsert": {"seq": id_counter}},
        upsert=True
    )
    print(f"\n  ID counter set to {id_counter}")
else:
    print("  ℹ   users_registry.json not found — no users migrated")

# ──────────────────────────────────────────────────────────────────────────────
# PART 3: Migrate existing diet plan JSON files
# ──────────────────────────────────────────────────────────────────────────────

print()
print("=" * 55)
print("PART 3 — Migrating diet plans from outputs/")
print("=" * 55)

from bson import ObjectId

outputs_dir = _HERE / "outputs"
plan_files  = sorted(outputs_dir.glob("*_diet_plan.json")) if outputs_dir.exists() else []
migrated_plans = 0

for pf in plan_files:
    uid = pf.stem.replace("_diet_plan", "")
    try:
        with open(pf, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"  ⚠  Failed to read {pf.name}: {e}")
        continue

    created_at = datetime.fromtimestamp(pf.stat().st_mtime, tz=timezone.utc)
    doc = {
        "user_id":    uid,
        "created_at": created_at,
        "payload":    payload,
    }
    res = mdb.plans_col.insert_one(doc)
    # Link the plan to the user
    mdb.users_col.update_one(
        {"user_id": uid},
        {"$set": {"last_plan_id": res.inserted_id, "last_run": created_at}},
        upsert=False
    )
    print(f"  ✅  Migrated plan {pf.name}  →  plan_id: {res.inserted_id}")
    migrated_plans += 1

# ──────────────────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print("Migration complete!")
print(f"  Datasets uploaded  : {len(CSV_TO_COLLECTION)}")
print(f"  Users migrated     : {migrated_users}")
print(f"  Plans migrated     : {migrated_plans}")
print()
print("IMPORTANT NEXT STEPS:")
print("  1. Make sure MongoDB Atlas → Network Access → allows 0.0.0.0/0")
print("     (so any device can connect, not just yours)")
print("  2. Run 'python app.py' — datasets now load from MongoDB")
print("  3. Migrated users have NO password. They should re-register or")
print("     an admin can set passwords via the /api/user/set_password endpoint.")
print("=" * 55)
