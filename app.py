"""
app.py — AI Personalised NRS Web Application
Flask server with new/returning user auth + region preference + full recommendation.
"""
import os, sys, json, traceback
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from flask import Flask, render_template, request, jsonify
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
from utils import db as mdb
# Per user request: store passwords as plain text (INSECURE).
# Provide passthrough functions so existing code paths continue to work.
def generate_password_hash(p):
    return p

def check_password_hash(stored, candidate):
    return stored == candidate
from bson.objectid import ObjectId
from datetime import datetime

from models.food_filter_pipeline import FoodFilteringPipeline
from recommendation_model.recommender import DietRecommender
from utils.user_registry import (
    generate_user_id, register_user, user_exists, get_user,
    save_user_profile, touch_last_run, list_users
)

app = Flask(__name__, template_folder="templates", static_folder="static")

print("Loading pipeline...")
_pipeline    = FoodFilteringPipeline()
_recommender = DietRecommender()
print("Ready — http://localhost:5000")

def _list(data, key):
    val = data.get(key, [])
    if isinstance(val, str):
        val = [v.strip() for v in val.split(",") if v.strip()]
    return [v for v in val if v]

def _str(data, key, default=""):
    return str(data.get(key, default)).strip()

def _int(data, key, default=3):
    try: return int(data.get(key, default))
    except: return default

@app.route("/")
def index():
    return render_template("index.html")

# ── User Registry Endpoints ─────────────────────────────────────────────────

@app.route("/api/user/new", methods=["POST"])
def new_user():
    """Register a new user and return their auto-generated ID. Accepts optional password and stores in Mongo if available."""
    try:
        data      = request.get_json(force=True)
        name      = _str(data,"name","User")
        age       = _str(data,"age","30")
        sex       = _str(data,"sex","male")
        weight_kg = _str(data,"weight_kg","70")
        height_cm = _str(data,"height_cm","170")
        password  = _str(data,"password","")

        user_id = generate_user_id()
        # require password for new users
        if not password:
            return jsonify({"error":"Password is required when registering."}), 400
        # Save to local registry (fallback)
        register_user(user_id, name, age, sex,
                      weight_kg=weight_kg, height_cm=height_cm)

        # If Mongo is configured, save user there too
        try:
            if mdb.users_col is not None:
                doc = {
                    "user_id": user_id,
                    "name": name,
                    "age": age,
                    "sex": sex,
                    "weight_kg": weight_kg,
                    "height_cm": height_cm,
                    "dietary_preference": _str(data,"dietary_preference","none"),
                    "allergies": _list(data,'allergies'),
                    "diseases": _list(data,'diseases'),
                    "dislikes": _list(data,'dislikes'),
                    "registered_at": datetime.utcnow(),
                    "last_run": None,
                }
                if password:
                    doc['password_hash'] = generate_password_hash(password)
                mdb.users_col.insert_one(doc)
        except Exception:
            traceback.print_exc()

        return jsonify({"status":"ok","user_id":user_id,"name":name})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":str(e)}), 500


@app.route("/api/user/login", methods=["POST"])
def login_user():
    """Validate returning user ID and return their saved profile. If Mongo is configured authenticate and return last saved plan."""
    try:
        data    = request.get_json(force=True)
        user_id = _str(data,"user_id","").upper()
        password = _str(data,"password","")

        # Try Mongo first if available
        try:
            if mdb.users_col is not None:
                u = mdb.users_col.find_one({"user_id": user_id})
                if not u:
                    # fall back to file-based registry
                    if not user_exists(user_id):
                        return jsonify({"error":f"User ID '{user_id}' not found."}), 404
                    record = get_user(user_id)
                    return jsonify({"status":"ok","user":record})
                # verify password if set
                ph = u.get('password_hash')
                if ph:
                    # account has a password — require a password and verify it
                    if not password:
                        return jsonify({"error":"Password required."}), 401
                    if not check_password_hash(ph, password):
                        return jsonify({"error":"Invalid credentials."}), 401
                else:
                    # account has no password set (legacy/migrated). If caller provided a password,
                    # treat it as an invalid attempt to avoid allowing arbitrary passwords.
                    if password:
                        return jsonify({"error":"Invalid credentials."}), 401
                # build safe user object to return (no password hash) and convert ObjectId to str
                safe_user = {}
                for k, v in u.items():
                    if k == 'password_hash':
                        continue
                    if isinstance(v, ObjectId):
                        safe_user[k] = str(v)
                    else:
                        safe_user[k] = v
                # fetch last plan if exists
                last_plan = None
                # last_plan id may be stored as ObjectId or string
                last_pid = u.get('last_plan_id') or safe_user.get('last_plan_id')
                if last_pid and mdb.plans_col is not None:
                    try:
                        p = None
                        if isinstance(last_pid, ObjectId):
                            p = mdb.plans_col.find_one({"_id": last_pid})
                        else:
                            # try as ObjectId string first, then raw value
                            try:
                                p = mdb.plans_col.find_one({"_id": ObjectId(str(last_pid))})
                            except Exception:
                                p = mdb.plans_col.find_one({"_id": last_pid})
                        if p:
                            last_plan = p.get('payload')
                    except Exception:
                        traceback.print_exc()
                return jsonify({"status":"ok","user":safe_user,"last_plan":last_plan})
        except Exception:
            traceback.print_exc()

        # Fallback to file registry
        if not user_exists(user_id):
            return jsonify({"error":f"User ID '{user_id}' not found."}), 404
        record = get_user(user_id)
        return jsonify({"status":"ok","user":record})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":str(e)}), 500


@app.route("/api/user/update_meta", methods=["POST"])
def update_meta():
    """Update basic info for an existing user (also update Mongo if available)."""
    try:
        data    = request.get_json(force=True)
        user_id = _str(data,"user_id","").upper()
        if mdb.users_col:
            # try update in Mongo
            try:
                upd = {}
                if _str(data,'name'): upd['name'] = _str(data,'name')
                if _str(data,'age'): upd['age'] = _str(data,'age')
                if _str(data,'sex'): upd['sex'] = _str(data,'sex')
                if _str(data,'weight_kg'): upd['weight_kg'] = _str(data,'weight_kg')
                if _str(data,'height_cm'): upd['height_cm'] = _str(data,'height_cm')
                if upd:
                    mdb.users_col.update_one({"user_id":user_id},{"$set":upd})
            except Exception:
                traceback.print_exc()
        # keep file registry in sync
        from utils.user_registry import update_user_meta
        update_user_meta(user_id,
            name      = _str(data,"name") or None,
            age       = _str(data,"age")  or None,
            sex       = _str(data,"sex")  or None,
            weight_kg = _str(data,"weight_kg") or None,
            height_cm = _str(data,"height_cm") or None,
        )
        return jsonify({"status":"ok"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":str(e)}), 500


@app.route("/api/user/set_password", methods=["POST"])
def set_password():
    """Set or update a user's password in Mongo. If the account already has a password, the current password must be provided and verified."""
    try:
        data = request.get_json(force=True)
        user_id = _str(data, 'user_id', '').upper()
        current = _str(data, 'current_password', '')
        new_pw = _str(data, 'new_password', '')
        if not user_id or not new_pw:
            return jsonify({"error":"user_id and new_password are required."}), 400

        if mdb.users_col is None:
            return jsonify({"error":"Database not configured."}), 500

        u = mdb.users_col.find_one({"user_id": user_id})
        if not u:
            return jsonify({"error":f"User ID '{user_id}' not found."}), 404

        ph = u.get('password_hash')
        if ph:
            # require current password when account already has a password
            if not current:
                return jsonify({"error":"Current password required to change password."}), 401
            if not check_password_hash(ph, current):
                return jsonify({"error":"Invalid current password."}), 401

        # set new password hash
        new_hash = generate_password_hash(new_pw)
        mdb.users_col.update_one({"user_id": user_id}, {"$set": {"password_hash": new_hash}})
        return jsonify({"status":"ok","message":"Password set/updated."})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":str(e)}), 500


# ── Options ─────────────────────────────────────────────────────────────────

@app.route("/api/options", methods=["GET"])
def get_options():
    return jsonify({
        "dietary_preferences":[
            {"value":"none",       "label":"No preference"},
            {"value":"vegetarian", "label":"Vegetarian"},
            {"value":"vegan",      "label":"Vegan"},
            {"value":"jain",       "label":"Jain"},
            {"value":"halal",      "label":"Halal"},
        ],
        "goals":[
            {"value":"weight_loss_aggressive","label":"Aggressive Weight Loss (~0.7 kg/week)"},
            {"value":"weight_loss",           "label":"Weight Loss (~0.5 kg/week)"},
            {"value":"weight_loss_mild",       "label":"Mild Weight Loss (~0.25 kg/week)"},
            {"value":"maintain",               "label":"Maintain Current Weight"},
            {"value":"weight_gain_mild",       "label":"Mild Weight Gain (~0.25 kg/week)"},
            {"value":"weight_gain",            "label":"Weight Gain (~0.5 kg/week)"},
            {"value":"muscle_gain",            "label":"Muscle Gain (Lean Bulk)"},
        ],
        "activity_levels":[
            {"value":"sedentary",         "label":"Sedentary (desk job, no exercise)"},
            {"value":"lightly_active",    "label":"Lightly Active (1-3 days/week)"},
            {"value":"moderately_active", "label":"Moderately Active (3-5 days/week)"},
            {"value":"very_active",       "label":"Very Active (6-7 days/week)"},
            {"value":"extra_active",      "label":"Extra Active (athlete/physical job)"},
        ],
        "region_zones":[
            {"value":"any",     "label":"No preference (Pan-Indian)"},
            {"value":"north",   "label":"North India (Punjabi, Kashmiri, Rajasthani, Awadhi...)"},
            {"value":"south",   "label":"South India (Kerala, Tamil Nadu, Karnataka, Andhra...)"},
            {"value":"east",    "label":"East India (Bengali, Odia, Bihari, Northeast...)"},
            {"value":"west",    "label":"West India (Maharashtrian, Gujarati, Goan...)"},
            {"value":"central", "label":"Central India (Madhya Pradesh, Chhattisgarh, Jharkhand...)"},
        ],
        "meal_counts":[3,4,5,6],
        "allergies":["gluten","wheat","celiac","dairy","milk","lactose","nuts","tree nuts","peanuts","eggs","shellfish","fish","seafood","soy","sesame","sulfites","histamine","fodmap","fructose"],
        "diseases":["Type 2 Diabetes","Type 1 Diabetes","Hypertension","Heart Disease","Kidney Disease","Gout","PCOS","Hypothyroidism","Hyperthyroidism","Anemia","Celiac Disease","IBD","GERD","Fatty Liver Disease","Obesity","Osteoporosis","High Cholesterol","Lactose Intolerance","Cancer","Thyroid Cancer"],
        "dislikes":["Seafood","Red Meat","Eggs","Dairy Products","Mushrooms","Nuts & Seeds","Legumes / Beans","Bitter Gourd (Karela)","Bottle Gourd (Lauki)","Onion & Garlic","Leafy Greens","Spicy Foods","Bitter Foods","Fried Foods","Tofu / Soy Products","Sprouts","Jain Diet","No Beef","No Pork","vegan","vegetarian"],
    })

# ── Main Recommendation ─────────────────────────────────────────────────────

@app.route("/api/recommend", methods=["POST"])
def recommend():
    try:
        data = request.get_json(force=True)

        profile = {
            "user_id":            _str(data,"user_id","WEB_USER"),
            "name":               _str(data,"name","User"),
            "age":                _str(data,"age","30"),
            "sex":                _str(data,"sex","male"),
            "weight_kg":          _str(data,"weight_kg","70"),
            "height_cm":          _str(data,"height_cm","170"),
            "dietary_preference": _str(data,"dietary_preference","none"),
            "allergies":          _list(data,"allergies"),
            "diseases":           _list(data,"diseases"),
            "dislikes":           _list(data,"dislikes"),
        }
        rec_inputs = {
            "goal":          _str(data,"goal","maintain"),
            "activity_level":_str(data,"activity_level","moderately_active"),
            "meal_count":    _int(data,"meal_count",3),
            "region_zone":   _str(data,"region_zone","any"),
        }

        fr  = _pipeline.run(profile)
        safe_df = fr["safe_food_list"]
        ctx     = fr["recommendation_context"]

        if len(safe_df) < 8:
            return jsonify({"error":f"Only {len(safe_df)} safe foods after filtering. Loosen your restrictions.","safe_food_count":len(safe_df)}), 400

        rec = _recommender.run(
            safe_foods_df          = safe_df,
            recommendation_context = ctx,
            goal                   = rec_inputs["goal"],
            activity_level         = rec_inputs["activity_level"],
            meal_count             = rec_inputs["meal_count"],
            region_zone            = rec_inputs["region_zone"],
        )

        # Save to registry if real user
        uid = profile["user_id"]
        if user_exists(uid):
            save_user_profile(uid, profile)
            touch_last_run(uid)

        # Save plan to Mongo if available
        try:
            if mdb.plans_col is not None and uid and uid != 'WEB_USER':
                plan_doc = {
                    "user_id": uid,
                    "created_at": datetime.utcnow(),
                    "payload": {
                        "user": {"name": profile['name'], "user_id": uid},
                        "filter_summary": {
                            "total_foods":1352,
                            "safe_food_count":len(safe_df),
                            "allergy_removed":fr["stage_reports"]["allergy"].get("total_removed",0),
                            "disease_removed":fr["stage_reports"]["disease"].get("total_removed",0),
                            "dislike_removed":fr["stage_reports"]["dislike"].get("total_removed",0),
                            "severity_warnings":fr["severity_warnings"],
                        },
                        "metrics": rec["metrics"].__dict__ if hasattr(rec["metrics"], '__dict__') else rec["metrics"],
                        "recommendation_context": {k:v for k,v in ctx.items() if k!="safe_food_ids"},
                        "weekly_plan": rec["weekly_plan"],
                        "weekly_avg": rec["weekly_avg"],
                        "nutritional_gaps": rec["nutritional_gaps"],
                        "insights": rec["insights"],
                        "tips": rec["tips"],
                        "goal_label": rec["goal_label"],
                        "activity_label": rec["activity_label"],
                        "region_zone": rec_inputs["region_zone"],
                    }
                }
                res = mdb.plans_col.insert_one(plan_doc)
                # update user's last_plan_id
                try:
                    if mdb.users_col is not None:
                        mdb.users_col.update_one({"user_id": uid}, {"$set": {"last_plan_id": res.inserted_id, "last_run": datetime.utcnow()}})
                except Exception:
                    # fallback if users_col update fails
                    pass
        except Exception:
            traceback.print_exc()

        m = rec["metrics"]
        return jsonify({
            "status":"ok",
            "user":{"name":profile["name"],"user_id":uid},
            "filter_summary":{
                "total_foods":1352,
                "safe_food_count":len(safe_df),
                "allergy_removed":fr["stage_reports"]["allergy"].get("total_removed",0),
                "disease_removed":fr["stage_reports"]["disease"].get("total_removed",0),
                "dislike_removed":fr["stage_reports"]["dislike"].get("total_removed",0),
                "severity_warnings":fr["severity_warnings"],
            },
            "metrics":{
                "bmi":m.bmi,"bmi_category":m.bmi_category,
                "bmr":round(m.bmr,0),"tdee":round(m.tdee,0),
                "target_calories":round(m.target_calories,0),
                "ibw_kg":m.ibw_kg,
                "protein_g":m.protein_g,"carbs_g":m.carbs_g,"fat_g":m.fat_g,
                "fiber_g":m.fiber_g,"sodium_mg":m.sodium_mg,"water_ml":m.water_ml,
                "calcium_mg":m.calcium_mg,"iron_mg":m.iron_mg,
                "vitamin_c_mg":m.vitamin_c_mg,"vitamin_d_iu":m.vitamin_d_iu,
                "potassium_mg":m.potassium_mg,
                "protein_kcal":round(m.protein_kcal,0),
                "carbs_kcal":round(m.carbs_kcal,0),
                "fat_kcal":round(m.fat_kcal,0),
                "meal_calories":m.meal_calories,
            },
            "recommendation_context":{k:v for k,v in ctx.items() if k!="safe_food_ids"},
            "weekly_plan":rec["weekly_plan"],
            "weekly_avg":rec["weekly_avg"],
            "nutritional_gaps":rec["nutritional_gaps"],
            "insights":rec["insights"],
            "tips":rec["tips"],
            "goal_label":rec["goal_label"],
            "activity_label":rec["activity_label"],
            "region_zone":rec_inputs["region_zone"],
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error":str(e)}), 500

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  AI Personalised NRS — Web Interface")
    print("  Open: http://localhost:5000")
    print("="*55 + "\n")
    app.run(debug=False, port=5000, host="0.0.0.0")
