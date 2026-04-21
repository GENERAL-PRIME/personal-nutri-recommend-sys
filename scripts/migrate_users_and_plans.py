# ...existing code...
from pathlib import Path
import os, json, time
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME")

if not MONGO_URI:
    raise SystemExit("MONGO_URI not set")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB] if MONGO_DB else client.get_default_database()

users_col = db["users"]
plans_col = db["plans"]

ROOT = Path(__file__).resolve().parents[1]
users_file = ROOT / "outputs" / "users_registry.json"
outputs_dir = ROOT / "outputs"

# 1) Import users_registry.json
if users_file.exists():
    print("Importing users from", users_file)
    with open(users_file, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    # expected structure may be either { user_id: {...} } or { "users": { user_id: {...} }, "id_counter": N }
    if isinstance(data, dict) and "users" in data and isinstance(data["users"], dict):
        users_map = data["users"]
    elif isinstance(data, dict):
        users_map = {k: v for k, v in data.items() if isinstance(v, dict) and k.startswith("NRS")}
    else:
        users_map = {}

    for uid, profile in users_map.items():
        # ensure profile is a dict
        if not isinstance(profile, dict):
            print(f"Skipping invalid profile for {uid}: not a dict")
            continue
        profile_out = {
            "user_id": uid,
            "name": profile.get("name"),
            "age": profile.get("age"),
            "sex": profile.get("sex"),
            "weight_kg": profile.get("weight_kg"),
            "height_cm": profile.get("height_cm"),
            "dietary_preference": profile.get("dietary_preference"),
            "registered_at": profile.get("registered_at") or datetime.now(timezone.utc),
            "last_run": profile.get("last_run"),
        }
        # upsert user: keep only insert-only fields in $setOnInsert to avoid path conflicts
        set_on_insert = {"user_id": uid, "registered_at": profile_out["registered_at"]}
        set_payload = {k: v for k, v in profile_out.items() if v is not None and k not in ("user_id", "registered_at")}
        users_col.update_one({"user_id": uid}, {"$setOnInsert": set_on_insert, "$set": set_payload}, upsert=True)
    print("Users import done.")
else:
    print("users_registry.json not found, skipping user import.")

# 2) Import existing diet plan JSON files and link to users
plan_files = list(outputs_dir.glob("*_diet_plan.json"))
plan_files.sort()
print("Found", len(plan_files), "plan files")

for pf in plan_files:
    try:
        with open(pf, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as e:
        print("Failed to load", pf, e); continue

    # find user id from filename prefix or payload
    # filename pattern NRS0001_diet_plan.json
    uid = pf.name.split("_")[0]
    created_at = datetime.utcfromtimestamp(pf.stat().st_mtime)

    doc = {
        "user_id": uid,
        "created_at": created_at,
        "payload": payload
    }
    res = plans_col.insert_one(doc)
    print("Inserted plan", pf.name, "->", res.inserted_id)

    # update user's last_plan_id to the most recent plan
    users_col.update_one({"user_id": uid}, {"$set": {"last_plan_id": res.inserted_id, "last_run": created_at}}, upsert=True)

print("Plans import done.")