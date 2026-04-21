"""
Dangerous: deletes all documents from 'users' and 'plans' collections in the configured MongoDB
and clears the local outputs/users_registry.json (backing it up first).
Run this from project root with your virtualenv activated.
Example: .\.venv\Scripts\Activate.ps1; python .\scripts\clear_mongo_and_local.py
"""

from dotenv import load_dotenv
import os, sys
from pymongo import MongoClient
from pathlib import Path
import shutil

load_dotenv()
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME")

if not MONGO_URI:
    print("MONGO_URI not set in .env — aborting.")
    sys.exit(1)

client = MongoClient(MONGO_URI)
db = client[MONGO_DB] if MONGO_DB else client.get_default_database()

print("This script WILL DELETE all documents in 'users' and 'plans' collections and clear local registry.")
print("Type YES to proceed, anything else to abort:")
resp = input().strip()
if resp != 'YES':
    print("Aborted by user.")
    sys.exit(0)

# backup local registry
ROOT = Path(__file__).resolve().parents[1]
outputs_dir = ROOT / 'outputs'
outputs_dir.mkdir(parents=True, exist_ok=True)
local_reg = outputs_dir / 'users_registry.json'
backup = outputs_dir / 'users_registry.json.bak'
if local_reg.exists():
    shutil.copy(local_reg, backup)
    print(f"Backed up local registry to {backup}")
else:
    print("Local registry file not found — skipping local backup.")

# delete from mongo
try:
    users_result = db['users'].delete_many({})
    plans_result = db['plans'].delete_many({})
    print(f"Deleted {users_result.deleted_count} documents from 'users'")
    print(f"Deleted {plans_result.deleted_count} documents from 'plans'")
except Exception as e:
    print('Mongo deletion error:', e)
    sys.exit(1)

# overwrite local registry
try:
    local_reg.write_text('{"users": {}, "id_counter": 0}', encoding='utf-8')
    print(f"Cleared local registry at {local_reg}")
except Exception as e:
    print('Failed to clear local registry:', e)
    sys.exit(1)

print('Done.')
