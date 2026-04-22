"""
app.py — NutriAI  (MongoDB-only, no local file storage)
"""
import os, sys, traceback
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify
from datetime import datetime, timezone
from bson.objectid import ObjectId

from utils import db as mdb

def _require_mongo():
    if mdb.users_col is None or mdb.plans_col is None:
        raise RuntimeError(
            "MongoDB is not connected. Check MONGO_URI in .env and whitelist "
            "0.0.0.0/0 in MongoDB Atlas → Network Access."
        )

def _hash_pw(p): return p
def _check_pw(stored, candidate): return stored == candidate

print("Loading pipeline from MongoDB datasets...")
from models.food_filter_pipeline import FoodFilteringPipeline
from recommendation_model.recommender import DietRecommender
_pipeline    = FoodFilteringPipeline()
_recommender = DietRecommender()
print("Ready — http://localhost:5000")

app = Flask(__name__, template_folder="templates", static_folder="static")

def _ls(d,k):
    v=d.get(k,[]);
    if isinstance(v,str): v=[x.strip() for x in v.split(",") if x.strip()]
    return [x for x in v if x]
def _s(d,k,df=""): return str(d.get(k,df)).strip()
def _i(d,k,df=3):
    try: return int(d.get(k,df))
    except: return df
def _safe(doc):
    return {k:(str(v) if isinstance(v,ObjectId) else v) for k,v in doc.items() if k!="password_hash"}

def _gen_uid():
    """
    Atomically increment counter and return next NRS-ID.
    On startup, syncs the counter to max existing user number so
    duplicates never happen even after re-migrations.
    """
    _require_mongo()
    # One-time sync: ensure counter >= highest existing NRS number
    last_user = mdb.users_col.find_one(
        {}, sort=[("user_id", -1)], projection={"user_id": 1}
    )
    if last_user:
        try:
            existing_max = int(last_user["user_id"].replace("NRS", ""))
            mdb.db["counters"].update_one(
                {"_id": "user_id", "seq": {"$lt": existing_max}},
                {"$set": {"seq": existing_max}},
            )
        except Exception:
            pass

    # Atomically get next number, retry up to 20 times if collision
    for _ in range(20):
        r = mdb.db["counters"].find_one_and_update(
            {"_id": "user_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        uid = f"NRS{r.get('seq', 1):04d}"
        if not mdb.users_col.find_one({"user_id": uid}):
            return uid
        # uid already taken — loop increments counter again on next try
    raise RuntimeError("Could not generate a unique User ID. Please try again.")

@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/user/new", methods=["POST"])
def new_user():
    try:
        _require_mongo()
        d=request.get_json(force=True)
        pw=_s(d,"password","")
        if not pw: return jsonify({"error":"Password is required."}),400
        if len(pw)<6: return jsonify({"error":"Password must be at least 6 characters."}),400
        uid=_gen_uid()
        doc={"user_id":uid,"name":_s(d,"name","User"),"age":_s(d,"age","30"),
             "sex":_s(d,"sex","male"),"weight_kg":_s(d,"weight_kg","70"),
             "height_cm":_s(d,"height_cm","170"),
             "dietary_preference":_s(d,"dietary_preference","none"),
             "allergies":_ls(d,"allergies"),"diseases":_ls(d,"diseases"),
             "dislikes":_ls(d,"dislikes"),"password_hash":_hash_pw(pw),
             "registered_at":datetime.now(timezone.utc).isoformat(),
             "last_run":None,"last_plan_id":None}
        mdb.users_col.insert_one(doc)
        return jsonify({"status":"ok","user_id":uid,"name":doc["name"]})
    except RuntimeError as e: return jsonify({"error":str(e)}),503
    except Exception as e: traceback.print_exc(); return jsonify({"error":str(e)}),500

@app.route("/api/user/login", methods=["POST"])
def login_user():
    try:
        _require_mongo()
        d=request.get_json(force=True)
        uid=_s(d,"user_id","").upper()
        pw=_s(d,"password","")
        if not uid: return jsonify({"error":"User ID is required."}),400
        u=mdb.users_col.find_one({"user_id":uid})
        if not u: return jsonify({"error":f"User ID '{uid}' not found."}),404
        ph=u.get("password_hash","")
        if ph:
            if not pw: return jsonify({"error":"Password required."}),401
            if not _check_pw(ph,pw): return jsonify({"error":"Incorrect password."}),401
        else:
            if pw: return jsonify({"error":"This account has no password set. Leave password blank."}),401
        safe=_safe(u)
        last_plan=None
        pid=u.get("last_plan_id")
        if pid and mdb.plans_col is not None:
            try:
                p=mdb.plans_col.find_one({"_id":ObjectId(str(pid)) if not isinstance(pid,ObjectId) else pid})
                if p: last_plan=p.get("payload")
            except: traceback.print_exc()
        return jsonify({"status":"ok","user":safe,"last_plan":last_plan})
    except RuntimeError as e: return jsonify({"error":str(e)}),503
    except Exception as e: traceback.print_exc(); return jsonify({"error":str(e)}),500

@app.route("/api/user/update_meta", methods=["POST"])
def update_meta():
    try:
        _require_mongo()
        d=request.get_json(force=True)
        uid=_s(d,"user_id","").upper()
        upd={k:d[k] for k in ("name","age","sex","weight_kg","height_cm","dietary_preference","allergies","diseases","dislikes") if k in d}
        if upd: mdb.users_col.update_one({"user_id":uid},{"$set":upd})
        return jsonify({"status":"ok"})
    except RuntimeError as e: return jsonify({"error":str(e)}),503
    except Exception as e: traceback.print_exc(); return jsonify({"error":str(e)}),500

@app.route("/api/user/set_password", methods=["POST"])
def set_password():
    try:
        _require_mongo()
        d=request.get_json(force=True)
        uid=_s(d,"user_id","").upper()
        cur=_s(d,"current_password","")
        nw=_s(d,"new_password","")
        if not uid or not nw: return jsonify({"error":"user_id and new_password required."}),400
        if len(nw)<6: return jsonify({"error":"Password must be at least 6 characters."}),400
        u=mdb.users_col.find_one({"user_id":uid})
        if not u: return jsonify({"error":f"User '{uid}' not found."}),404
        ph=u.get("password_hash","")
        if ph and not _check_pw(ph,cur): return jsonify({"error":"Current password incorrect."}),401
        mdb.users_col.update_one({"user_id":uid},{"$set":{"password_hash":_hash_pw(nw)}})
        return jsonify({"status":"ok","message":"Password updated."})
    except RuntimeError as e: return jsonify({"error":str(e)}),503
    except Exception as e: traceback.print_exc(); return jsonify({"error":str(e)}),500

@app.route("/api/options", methods=["GET"])
def get_options():
    return jsonify({
        "dietary_preferences":[{"value":"none","label":"No preference"},{"value":"vegetarian","label":"Vegetarian"},{"value":"vegan","label":"Vegan"},{"value":"jain","label":"Jain"},{"value":"halal","label":"Halal"}],
        "goals":[{"value":"weight_loss_aggressive","label":"Aggressive Weight Loss (~0.7 kg/week)"},{"value":"weight_loss","label":"Weight Loss (~0.5 kg/week)"},{"value":"weight_loss_mild","label":"Mild Weight Loss (~0.25 kg/week)"},{"value":"maintain","label":"Maintain Current Weight"},{"value":"weight_gain_mild","label":"Mild Weight Gain (~0.25 kg/week)"},{"value":"weight_gain","label":"Weight Gain (~0.5 kg/week)"},{"value":"muscle_gain","label":"Muscle Gain (Lean Bulk)"}],
        "activity_levels":[{"value":"sedentary","label":"Sedentary (desk job, no exercise)"},{"value":"lightly_active","label":"Lightly Active (1-3 days/week)"},{"value":"moderately_active","label":"Moderately Active (3-5 days/week)"},{"value":"very_active","label":"Very Active (6-7 days/week)"},{"value":"extra_active","label":"Extra Active (athlete/physical job)"}],
        "region_zones":[{"value":"any","label":"No preference (Pan-Indian)"},{"value":"north","label":"North India"},{"value":"south","label":"South India"},{"value":"east","label":"East India"},{"value":"west","label":"West India"},{"value":"central","label":"Central India"}],
        "meal_counts":[3,4,5,6],
        "allergies":["gluten","wheat","celiac","dairy","milk","lactose","nuts","tree nuts","peanuts","eggs","shellfish","fish","seafood","soy","sesame","sulfites","histamine","fodmap","fructose"],
        "diseases":["Type 2 Diabetes","Type 1 Diabetes","Hypertension","Heart Disease","Kidney Disease","Gout","PCOS","Hypothyroidism","Hyperthyroidism","Anemia","Celiac Disease","IBD","GERD","Fatty Liver Disease","Obesity","Osteoporosis","High Cholesterol","Lactose Intolerance","Cancer","Thyroid Cancer"],
        "dislikes":["Seafood","Red Meat","Eggs","Dairy Products","Mushrooms","Nuts & Seeds","Legumes / Beans","Bitter Gourd (Karela)","Bottle Gourd (Lauki)","Onion & Garlic","Leafy Greens","Spicy Foods","Bitter Foods","Fried Foods","Tofu / Soy Products","Sprouts","Jain Diet","No Beef","No Pork","vegan","vegetarian"],
    })

@app.route("/api/recommend", methods=["POST"])
def recommend():
    try:
        _require_mongo()
        d=request.get_json(force=True)
        profile={"user_id":_s(d,"user_id","GUEST"),"name":_s(d,"name","User"),
                 "age":_s(d,"age","30"),"sex":_s(d,"sex","male"),
                 "weight_kg":_s(d,"weight_kg","70"),"height_cm":_s(d,"height_cm","170"),
                 "dietary_preference":_s(d,"dietary_preference","none"),
                 "allergies":_ls(d,"allergies"),"diseases":_ls(d,"diseases"),"dislikes":_ls(d,"dislikes")}
        ri={"goal":_s(d,"goal","maintain"),"activity_level":_s(d,"activity_level","moderately_active"),
            "meal_count":_i(d,"meal_count",3),"region_zone":_s(d,"region_zone","any")}
        fr=_pipeline.run(profile)
        safe_df=fr["safe_food_list"]; ctx=fr["recommendation_context"]
        if len(safe_df)<8:
            return jsonify({"error":f"Only {len(safe_df)} safe foods after filtering.","safe_food_count":len(safe_df)}),400
        rec=_recommender.run(safe_foods_df=safe_df,recommendation_context=ctx,
            goal=ri["goal"],activity_level=ri["activity_level"],
            meal_count=ri["meal_count"],region_zone=ri["region_zone"])
        m=rec["metrics"]
        payload={
            "user":{"name":profile["name"],"user_id":profile["user_id"]},
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "filter_summary":{"total_foods":1352,"safe_food_count":len(safe_df),
                "allergy_removed":fr["stage_reports"]["allergy"].get("total_removed",0),
                "disease_removed":fr["stage_reports"]["disease"].get("total_removed",0),
                "dislike_removed":fr["stage_reports"]["dislike"].get("total_removed",0),
                "severity_warnings":fr["severity_warnings"]},
            "metrics":{"bmi":m.bmi,"bmi_category":m.bmi_category,"bmr":round(m.bmr,0),"tdee":round(m.tdee,0),
                "target_calories":round(m.target_calories,0),"ibw_kg":m.ibw_kg,
                "protein_g":m.protein_g,"carbs_g":m.carbs_g,"fat_g":m.fat_g,
                "fiber_g":m.fiber_g,"sodium_mg":m.sodium_mg,"water_ml":m.water_ml,
                "calcium_mg":m.calcium_mg,"iron_mg":m.iron_mg,"vitamin_c_mg":m.vitamin_c_mg,
                "vitamin_d_iu":m.vitamin_d_iu,"potassium_mg":m.potassium_mg,
                "protein_kcal":round(m.protein_kcal,0),"carbs_kcal":round(m.carbs_kcal,0),
                "fat_kcal":round(m.fat_kcal,0),"meal_calories":m.meal_calories},
            "recommendation_context":{k:v for k,v in ctx.items() if k!="safe_food_ids"},
            "weekly_plan":rec["weekly_plan"],"weekly_avg":rec["weekly_avg"],
            "nutritional_gaps":rec["nutritional_gaps"],"insights":rec["insights"],"tips":rec["tips"],
            "goal_label":rec["goal_label"],"activity_label":rec["activity_label"],
            "region_zone":ri["region_zone"],"meal_count":ri["meal_count"],
        }
        uid=profile["user_id"]
        if uid and uid!="GUEST":
            try:
                now = datetime.now(timezone.utc)
                plan_doc = {"user_id":uid,"created_at":now,"payload":payload}
                res = mdb.plans_col.find_one_and_replace(
                    {"user_id": uid},
                    plan_doc,
                    upsert=True,
                    return_document=True,
                )
                plan_oid = res["_id"]
                mdb.users_col.update_one({"user_id":uid},{"$set":{
                    "last_plan_id":plan_oid,"last_run":now.isoformat(),
                    "allergies":profile["allergies"],"diseases":profile["diseases"],
                    "dislikes":profile["dislikes"],"dietary_preference":profile["dietary_preference"],
                    "weight_kg":profile["weight_kg"],"height_cm":profile["height_cm"],
                    "age":profile["age"],"sex":profile["sex"],"name":profile["name"]}})
            except: traceback.print_exc()
        return jsonify({"status":"ok",**payload})
    except RuntimeError as e: return jsonify({"error":str(e)}),503
    except Exception as e: traceback.print_exc(); return jsonify({"error":str(e)}),500


# ── Food Swap API ──────────────────────────────────────────────────────────────
@app.route("/api/food/swap_options", methods=["POST"])
def swap_options():
    """Return top swap alternatives for a given food_id, filtered to safe foods only."""
    try:
        from utils.data_loader import get_food_df
        d        = request.get_json(force=True)
        food_id  = _s(d, "food_id", "")
        safe_ids = set(d.get("safe_food_ids", []))  # list of food_ids still safe for user

        full_df = get_food_df()
        row = full_df[full_df["food_id"] == food_id]
        if row.empty:
            return jsonify({"error": "Food not found"}), 404
        row = row.iloc[0]

        target_role   = row.get("meal_role",  "other")
        target_cal    = float(row.get("calories_per_100g", 100))
        target_prot   = float(row.get("protein_g",  0))
        target_carbs  = float(row.get("carbs_g",    0))
        target_fat    = float(row.get("fat_g",       0))
        target_fiber  = float(row.get("fiber_g",    0))
        target_region = row.get("region_zone", "pan_indian")
        target_veg    = row.get("is_vegetarian", True)
        target_vegan  = row.get("is_vegan", False)

        # Filter candidates: same meal_role, exclude self, only safe foods
        cands = full_df[
            (full_df["meal_role"] == target_role) &
            (full_df["food_id"]   != food_id) &
            (full_df["food_id"].isin(safe_ids) if safe_ids else pd.Series([True]*len(full_df)))
        ].copy()

        if cands.empty:
            return jsonify({"options": []})

        def calc_match(r):
            # Score based on nutritional similarity (0–100%)
            cal_sim    = max(0, 1 - abs(float(r.get("calories_per_100g",100)) - target_cal)  / max(target_cal,   1) * 1.5)
            prot_sim   = max(0, 1 - abs(float(r.get("protein_g",  0)) - target_prot)  / max(target_prot+1, 1) * 2.0)
            carbs_sim  = max(0, 1 - abs(float(r.get("carbs_g",    0)) - target_carbs) / max(target_carbs+1,1) * 1.5)
            fat_sim    = max(0, 1 - abs(float(r.get("fat_g",       0)) - target_fat)   / max(target_fat+1,  1) * 1.5)
            fiber_sim  = max(0, 1 - abs(float(r.get("fiber_g",    0)) - target_fiber)  / max(target_fiber+1,1))
            # Bonus for same region
            region_bonus = 0.08 if r.get("region_zone") == target_region else 0
            # Bonus for same dietary classification
            veg_bonus    = 0.05 if r.get("is_vegetarian") == target_veg else -0.05
            # Weighted match
            score = (cal_sim*0.30 + prot_sim*0.25 + carbs_sim*0.20 + fat_sim*0.15 + fiber_sim*0.10)
            score = min(1.0, score + region_bonus + veg_bonus)
            return round(score * 100, 1)

        cands["_match"] = cands.apply(calc_match, axis=1)
        cands = cands[cands["_match"] >= 35].nlargest(6, "_match")

        if cands.empty:
            return jsonify({"options": []})

        options = []
        for _, r in cands.iterrows():
            hindi = r.get("food_name_hindi","")
            if not hindi or str(hindi).lower() in ("nan","none",""):
                hindi = ""
            options.append({
                "food_id":         r["food_id"],
                "food_name":       r["food_name"],
                "food_name_hindi": hindi,
                "category":        r.get("category",""),
                "cuisine_type":    r.get("cuisine_type",""),
                "meal_role":       r.get("meal_role",""),
                "calories_per_100g": float(r.get("calories_per_100g",0)),
                "protein_g":       float(r.get("protein_g",0)),
                "carbs_g":         float(r.get("carbs_g",0)),
                "fat_g":           float(r.get("fat_g",0)),
                "fiber_g":         float(r.get("fiber_g",0)),
                "serving_unit":    r.get("serving_unit","gram"),
                "piece_weight_g":  float(r.get("piece_weight_g",100)),
                "match_pct":       r["_match"],
                "disease_score":   float(r.get("disease_score",50)),
            })

        return jsonify({"original_food": food_id, "options": options})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__=="__main__":
    print("\n"+"="*55+"\n  NutriAI — Open: http://localhost:5000\n"+"="*55+"\n")
    app.run(debug=False,port=5000,host="0.0.0.0")
