"""
utils/user_registry.py
Central user registry — stores every user's full profile including
health data (allergies, diseases, dislikes) so returning users can
add to or remove from their existing lists precisely.
"""

import os, sys, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.helpers import output_path, cyan, green, yellow, bold, red, print_warning

REGISTRY_FILE = output_path("users_registry.json")
ID_PREFIX  = "NRS"
ID_PADDING = 4


# ── I/O ───────────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(REGISTRY_FILE):
        return {"users": {}, "id_counter": 0}
    try:
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        print_warning("Registry corrupted — starting fresh.")
        return {"users": {}, "id_counter": 0}


def _save(registry: dict):
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


# ── ID generation ─────────────────────────────────────────────────────────────

def generate_user_id() -> str:
    registry = _load()
    registry["id_counter"] += 1
    new_id = f"{ID_PREFIX}{str(registry['id_counter']).zfill(ID_PADDING)}"
    while new_id in registry["users"]:
        registry["id_counter"] += 1
        new_id = f"{ID_PREFIX}{str(registry['id_counter']).zfill(ID_PADDING)}"
    _save(registry)
    return new_id


# ── CRUD ──────────────────────────────────────────────────────────────────────

def register_user(user_id: str, name: str, age: str, sex: str,
                  weight_kg: str = "", height_cm: str = "",
                  dietary_preference: str = "none",
                  allergies: list = None,
                  diseases: list  = None,
                  dislikes: list  = None) -> bool:
    registry = _load()
    if user_id in registry["users"]:
        return False
    registry["users"][user_id] = {
        "user_id":            user_id,
        "name":               name,
        "age":                age,
        "sex":                sex,
        "weight_kg":          weight_kg,
        "height_cm":          height_cm,
        "dietary_preference": dietary_preference,
        "allergies":          allergies or [],
        "diseases":           diseases  or [],
        "dislikes":           dislikes  or [],
        "registered_at":      datetime.now().isoformat(),
        "last_run":           None,
    }
    _save(registry)
    return True


def user_exists(user_id: str) -> bool:
    return user_id in _load()["users"]


def get_user(user_id: str) -> dict | None:
    return _load()["users"].get(user_id)


def save_user_profile(user_id: str, profile: dict):
    """
    Overwrite the full stored profile for an existing user.
    Called after every successful pipeline run to keep registry in sync.
    """
    registry = _load()
    if user_id not in registry["users"]:
        return
    stored = registry["users"][user_id]
    stored["name"]               = profile.get("name",               stored.get("name",""))
    stored["age"]                = profile.get("age",                stored.get("age",""))
    stored["sex"]                = profile.get("sex",                stored.get("sex",""))
    stored["weight_kg"]          = profile.get("weight_kg",          stored.get("weight_kg",""))
    stored["height_cm"]          = profile.get("height_cm",          stored.get("height_cm",""))
    stored["dietary_preference"] = profile.get("dietary_preference", stored.get("dietary_preference","none"))
    stored["allergies"]          = profile.get("allergies",          stored.get("allergies",[]))
    stored["diseases"]           = profile.get("diseases",           stored.get("diseases",[]))
    stored["dislikes"]           = profile.get("dislikes",           stored.get("dislikes",[]))
    _save(registry)


def touch_last_run(user_id: str):
    registry = _load()
    if user_id in registry["users"]:
        registry["users"][user_id]["last_run"] = datetime.now().isoformat()
        _save(registry)


def update_user_meta(user_id: str, name: str = None, age: str = None,
                     sex: str = None, weight_kg: str = None, height_cm: str = None):
    registry = _load()
    if user_id not in registry["users"]:
        return
    u = registry["users"][user_id]
    if name:       u["name"]       = name
    if age:        u["age"]        = age
    if sex:        u["sex"]        = sex
    if weight_kg:  u["weight_kg"]  = weight_kg
    if height_cm:  u["height_cm"]  = height_cm
    _save(registry)


def list_users() -> list[dict]:
    return list(_load()["users"].values())


def get_all_ids() -> list[str]:
    return list(_load()["users"].keys())


# ── Display ───────────────────────────────────────────────────────────────────

def print_user_card(record: dict):
    print(f"\n    {cyan('User ID')}       :  {bold(record['user_id'])}")
    print(f"    {cyan('Name')}          :  {record['name']}")
    print(f"    {cyan('Age / Sex')}     :  {record.get('age','—')} / {record.get('sex','—')}")
    print(f"    {cyan('Weight/Height')} :  {record.get('weight_kg','—')} kg / {record.get('height_cm','—')} cm")
    print(f"    {cyan('Diet Pref')}     :  {record.get('dietary_preference','none')}")
    allergies = record.get('allergies', [])
    diseases  = record.get('diseases',  [])
    dislikes  = record.get('dislikes',  [])
    print(f"    {cyan('Allergies')}     :  {yellow(', '.join(allergies) if allergies else 'None')}")
    print(f"    {cyan('Diseases')}      :  {yellow(', '.join(diseases)  if diseases  else 'None')}")
    print(f"    {cyan('Dislikes')}      :  {yellow(', '.join(dislikes)  if dislikes  else 'None')}")
    print(f"    {cyan('Registered')}    :  {record['registered_at'][:19].replace('T',' ')}")
    last = record.get('last_run')
    if last:
        print(f"    {cyan('Last run')}      :  {last[:19].replace('T',' ')}")
