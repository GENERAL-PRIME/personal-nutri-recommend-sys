#!/usr/bin/env python3
"""
NutriAI Diagnostics — Run from your project root:
  cd personal-nutri-recommend
  python diagnose.py
"""
import sys, os, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PASS = "  [PASS]"
FAIL = "  [FAIL]"
WARN = "  [WARN]"

print("\n" + "="*60)
print("  NutriAI Server Diagnostics")
print("="*60)

errors = []

# ── 1. .env file ─────────────────────────────────────────────
print("\n1. Checking .env file...")
env_path = os.path.join(HERE, '.env')
if os.path.exists(env_path):
    with open(env_path) as f: lines = f.read()
    if 'MONGO_URI' in lines:
        print(f"{PASS} .env found with MONGO_URI")
    else:
        print(f"{FAIL} .env found but MONGO_URI is MISSING")
        errors.append(".env missing MONGO_URI")
else:
    print(f"{FAIL} .env file NOT FOUND at: {env_path}")
    errors.append(".env file missing — create it with MONGO_URI=...")

# ── 2. Load .env ──────────────────────────────────────────────
print("\n2. Loading environment variables...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    uri = os.environ.get('MONGO_URI','')
    if uri:
        print(f"{PASS} MONGO_URI loaded (length={len(uri)})")
    else:
        print(f"{FAIL} MONGO_URI is empty after load_dotenv()")
        errors.append("MONGO_URI empty after dotenv load")
except ImportError:
    print(f"{FAIL} python-dotenv not installed")
    errors.append("pip install python-dotenv")

# ── 3. MongoDB ────────────────────────────────────────────────
print("\n3. Testing MongoDB connection...")
try:
    from utils import db as mdb
    if mdb.db is not None and mdb.users_col is not None:
        # Try a real ping
        mdb.db.command('ping')
        count = mdb.users_col.count_documents({})
        print(f"{PASS} MongoDB connected! Users in DB: {count}")
    else:
        print(f"{FAIL} MongoDB NOT connected (db={mdb.db}, users_col={mdb.users_col})")
        print(f"       This is the ROOT CAUSE of 'Server error' on login")
        errors.append("MongoDB not connected")
except Exception as e:
    print(f"{FAIL} MongoDB error: {e}")
    errors.append(f"MongoDB: {e}")

# ── 4. Python module imports ──────────────────────────────────
print("\n4. Testing module imports...")
mods = [
    ("meal_planner",         "recommendation_model.meal_planner"),
    ("recommender",          "recommendation_model.recommender"),
    ("food_filter_pipeline", "models.food_filter_pipeline"),
    ("calculator",           "recommendation_model.calculator"),
    ("allergy_filter",       "models.allergy_filter"),
    ("disease_filter",       "models.disease_filter"),
    ("dislike_filter",       "models.dislike_filter"),
    ("data_loader",          "utils.data_loader"),
    ("helpers",              "utils.helpers"),
]
for name, path in mods:
    try:
        __import__(path)
        print(f"{PASS} {name}")
    except Exception as e:
        print(f"{FAIL} {name}: {e}")
        errors.append(f"Import {name}: {e}")

# ── 5. Check meal_planner version ────────────────────────────
print("\n5. Checking meal_planner.py version...")
try:
    import inspect
    from recommendation_model.meal_planner import build_weekly_plan, build_daily_plan
    sig_weekly = inspect.signature(build_weekly_plan)
    sig_daily  = inspect.signature(build_daily_plan)
    params_w = list(sig_weekly.parameters.keys())
    params_d = list(sig_daily.parameters.keys())
    print(f"  build_weekly_plan params: {params_w}")
    print(f"  build_daily_plan params:  {params_d}")
    if 'diet_pref' in params_w:
        print(f"{PASS} New meal_planner.py (v4.0) detected")
    else:
        print(f"{WARN} Old meal_planner.py detected — replace with downloaded version")
except Exception as e:
    print(f"{FAIL} {e}")

# ── 6. __pycache__ check ─────────────────────────────────────
print("\n6. Checking __pycache__ for stale bytecode...")
import glob
pyc_files = glob.glob(os.path.join(HERE, '**', '*.pyc'), recursive=True)
if pyc_files:
    print(f"{WARN} Found {len(pyc_files)} cached .pyc files")
    print(f"       If you replaced .py files and see errors, delete __pycache__:")
    print(f"       find . -type d -name __pycache__ | xargs rm -rf")
else:
    print(f"{PASS} No .pyc cache issues")

# ── Summary ───────────────────────────────────────────────────
print("\n" + "="*60)
if errors:
    print(f"  FOUND {len(errors)} ERROR(S):")
    for i, e in enumerate(errors, 1):
        print(f"  {i}. {e}")
    print()
    if any("MongoDB" in e for e in errors):
        print("  SOLUTION FOR 'Server error' on login:")
        print("  ----------------------------------------")
        print("  The 'Server error' alert happens because Flask crashes")
        print("  at startup when MongoDB is not connected. Every request")
        print("  returns an HTML error page instead of JSON, causing the")
        print("  JavaScript catch() to show 'Server error'.")
        print()
        print("  Fix steps:")
        print("  1. Ensure .env exists in personal-nutri-recommend/")
        print("  2. .env must contain: MONGO_URI=mongodb+srv://...")
        print("  3. In MongoDB Atlas -> Network Access -> Add IP 0.0.0.0/0")
        print("  4. Stop Flask (Ctrl+C)")
        print("  5. Delete cache: find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null")
        print("  6. Restart: python app.py")
        print("  7. Watch terminal output for '[MongoDB] Connected' message")
else:
    print("  ALL CHECKS PASSED!")
    print("  If still getting 'Server error', try:")
    print("  1. find . -type d -name __pycache__ | xargs rm -rf")
    print("  2. python app.py   (watch for any error in terminal)")
print("="*60 + "\n")
