"""
utils/db.py
============
MongoDB connection module for NutriAI.

Reads MONGO_URI from .env and returns two collections:
  - users_col  : stores user accounts + hashed passwords + last_plan_id
  - plans_col  : stores full recommendation payloads per user

If MONGO_URI is not set or connection fails, both are None
and the app falls back to the local JSON registry gracefully.
"""

import os
import traceback

users_col = None
plans_col = None
db = None

_MONGO_URI = os.environ.get("MONGO_URI", "")
_DB_NAME   = os.environ.get("MONGO_DB_NAME", "nutriai")

if _MONGO_URI:
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

        _client = MongoClient(
            _MONGO_URI,
            serverSelectionTimeoutMS=5000,   # 5 s timeout
            connectTimeoutMS=5000,
        )
        # Ping to confirm connection before continuing
        _client.admin.command("ping")

        _db       = _client[_DB_NAME]
        users_col = _db["users"]
        plans_col = _db["plans"]

        # ── Indexes ────────────────────────────────────────────────────────────
        # user_id must be unique across the users collection
        users_col.create_index("user_id", unique=True)
        # Fast lookup of plans by user
        plans_col.create_index("user_id")
        # Fast lookup of plans by creation date (for last-plan retrieval)
        plans_col.create_index([("user_id", 1), ("created_at", -1)])

        print(f"[MongoDB] ✅  Connected to '{_DB_NAME}' database.")

        # ── Export raw db object for data_loader ──────────────────────────────
        import builtins as _bi
        # make db accessible as utils.db.db
        import sys as _sys
        _this_module = _sys.modules[__name__]
        _this_module.db = _db

    except ImportError:
        print("[MongoDB] ⚠  pymongo not installed. Run: pip install pymongo")
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"[MongoDB] ⚠  Could not connect: {e}")
        print("[MongoDB]    Falling back to local JSON registry.")
        users_col = None
        plans_col = None
    except Exception:
        print("[MongoDB] ⚠  Unexpected error during connection:")
        traceback.print_exc()
        users_col = None
        plans_col = None
else:
    print("[MongoDB] ℹ  MONGO_URI not set — using local JSON registry only.")
