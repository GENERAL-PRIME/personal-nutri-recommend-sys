"""
utils/db.py
============
MongoDB Atlas connection module for NutriAI.

Reads MONGO_URI from environment / .env and provides:
  - users_col  : user accounts, hashed passwords, last_plan_id
  - plans_col  : full recommendation payloads per user
  - db         : raw database object (used by data_loader)

If MONGO_URI is not set or connection fails, all are None and the app
logs a clear error — there is no silent CSV fallback in this version
because all data now lives in MongoDB Atlas.
"""

import os
import traceback

users_col = None
plans_col = None
db        = None

# ── Load .env if present (local dev) ─────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional in production (env vars set by platform)

_MONGO_URI = os.environ.get("MONGO_URI", "").strip()
_DB_NAME   = os.environ.get("MONGO_DB_NAME", "nutriai").strip()

if _MONGO_URI:
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

        _client = MongoClient(
            _MONGO_URI,
            serverSelectionTimeoutMS = 8000,
            connectTimeoutMS         = 8000,
            socketTimeoutMS          = 30000,
            retryWrites              = True,
            # Connection pool: keep alive for Flask workers
            maxPoolSize              = 20,
            minPoolSize              = 2,
        )
        # Ping to verify before accepting traffic
        _client.admin.command("ping")

        _db       = _client[_DB_NAME]
        users_col = _db["users"]
        plans_col = _db["plans"]

        # ── Indexes ────────────────────────────────────────────────────────────
        users_col.create_index("user_id", unique=True)
        plans_col.create_index("user_id")
        plans_col.create_index([("user_id", 1), ("created_at", -1)])

        import sys as _sys
        _sys.modules[__name__].db = _db

        print(f"[MongoDB] ✅  Connected to '{_DB_NAME}' on Atlas.")

    except ImportError:
        print("[MongoDB] ⚠  pymongo not installed. Run: pip install pymongo[srv]")
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        print(f"[MongoDB] ✗  Connection failed: {e}")
        print("[MongoDB]    Verify MONGO_URI and Atlas network access list.")
    except Exception:
        print("[MongoDB] ✗  Unexpected error:")
        traceback.print_exc()
else:
    print("[MongoDB] ℹ  MONGO_URI not set — set it in .env or as an environment variable.")
