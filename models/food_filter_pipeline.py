"""
models/food_filter_pipeline.py
Master pipeline: chains AllergyFilter → DiseaseFilter → DislikeFilter.
"""

import os
import sys
import pandas as pd
from typing import List, Dict
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from models.allergy_filter import AllergyFoodFilter
from models.disease_filter import DiseaseFoodFilter
from models.dislike_filter  import DislikeFoodFilter
from utils.helpers import dataset_path, output_path, export_json, timestamp_str


class FoodFilteringPipeline:

    def __init__(self):
        food_path    = dataset_path("food_data.csv")
        allergy_path = dataset_path("allergy_data.csv")
        disease_path = dataset_path("disease_diet_data.csv")
        dislike_path = dataset_path("dislike_data.csv")

        self.allergy_filter = AllergyFoodFilter(food_path, allergy_path)
        self.disease_filter = DiseaseFoodFilter(food_path, disease_path)
        self.dislike_filter = DislikeFoodFilter(food_path, dislike_path)

    def run(self, user_profile: Dict) -> Dict:
        user_id   = user_profile.get("user_id",  "anonymous")
        allergies = [a.strip() for a in user_profile.get("allergies", []) if a.strip()]
        diseases  = [d.strip() for d in user_profile.get("diseases",  []) if d.strip()]
        dislikes  = [d.strip() for d in user_profile.get("dislikes",  []) if d.strip()]

        diet_pref = user_profile.get("dietary_preference", "").strip().lower()
        if diet_pref == "jain" and "Jain Diet" not in dislikes:
            dislikes = ["Jain Diet"] + dislikes
        elif diet_pref in ("vegetarian", "vegan") and diet_pref not in [d.lower() for d in dislikes]:
            dislikes = [diet_pref] + dislikes

        log = [
            f"Pipeline started — user: {user_id}",
            f"  Allergies ({len(allergies)}): {allergies or 'None'}",
            f"  Diseases  ({len(diseases)}): {diseases or 'None'}",
            f"  Dislikes  ({len(dislikes)}): {dislikes or 'None'}",
        ]

        after_allergy, allergy_report = self.allergy_filter.filter(allergies)
        severity_warnings = self.allergy_filter.get_severity_warning(allergies)
        log.append(f"\nStage 1 [Allergy] : {allergy_report.get('total_foods_before',0)} → {allergy_report.get('total_foods_after', len(after_allergy))} foods")

        after_disease, disease_report = self.disease_filter.filter(diseases, after_allergy)
        log.append(f"Stage 2 [Disease] : {disease_report.get('total_foods_before', len(after_allergy))} → {disease_report.get('total_foods_after', len(after_disease))} foods")

        final_foods, dislike_report = self.dislike_filter.filter(dislikes, after_disease)
        log.append(f"Stage 3 [Dislike] : {dislike_report.get('total_foods_before', len(after_disease))} → {dislike_report.get('total_foods_after', len(final_foods))} foods")
        log.append(f"\n✅ Final safe foods: {len(final_foods)}")

        if "disease_score" not in final_foods.columns:
            final_foods["disease_score"] = 50
        final_foods = final_foods.sort_values(
            ["disease_score", "calories_per_100g"], ascending=[False, True]
        ).reset_index(drop=True)

        def _has(kw): return any(kw in d.lower() for d in diseases)

        rec_ctx = {
            "user_id": user_id, "name": user_profile.get("name",""),
            "age": user_profile.get("age",""), "sex": user_profile.get("sex",""),
            "weight_kg": user_profile.get("weight_kg",""), "height_cm": user_profile.get("height_cm",""),
            "dietary_preference": diet_pref,
            "has_diabetes":        _has("diabetes"),
            "has_hypertension":    _has("hypertension") or _has("blood pressure"),
            "has_kidney_disease":  _has("kidney") or _has("ckd"),
            "has_gout":            _has("gout"),
            "has_heart_disease":   _has("heart") or _has("cad"),
            "has_pcos":            _has("pcos"),
            "has_obesity":         _has("obesity"),
            "has_high_cholesterol":_has("cholesterol"),
            "has_anemia":          _has("anemia"),
            "has_fatty_liver":     _has("fatty liver"),
            "is_vegetarian": diet_pref in ("vegetarian","vegan") or any("vegetarian" in d.lower() for d in dislikes),
            "is_vegan":      diet_pref == "vegan" or any("vegan" == d.lower() for d in dislikes),
            "calorie_limit_kcal":   self._calorie_limit(diseases),
            "sodium_limit_mg":      self._sodium_limit(diseases),
            "sugar_limit_g":        self._sugar_limit(diseases),
            "protein_target_g":     self._protein_target(diseases, user_profile),
            "total_safe_foods":     len(final_foods),
            "safe_food_ids":        final_foods["food_id"].tolist(),
            "critical_allergies":   severity_warnings,
            "active_allergies":     allergies,
            "active_diseases":      diseases,
        }

        return {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "input_profile": user_profile,
            "safe_food_list": final_foods,
            "safe_food_ids": final_foods["food_id"].tolist(),
            "recommendation_context": rec_ctx,
            "stage_reports": {"allergy": allergy_report, "disease": disease_report, "dislike": dislike_report},
            "pipeline_log": log,
            "severity_warnings": severity_warnings,
        }

    def _calorie_limit(self, diseases):
        for d in diseases:
            if any(k in d.lower() for k in ["diabetes","obesity","heart","fatty liver","cholesterol"]):
                return 1800
        return 2200

    def _sodium_limit(self, diseases):
        for d in diseases:
            if any(k in d.lower() for k in ["hypertension","blood pressure","heart","kidney","ckd"]):
                return 1500
        return 2300

    def _sugar_limit(self, diseases):
        for d in diseases:
            if "diabetes" in d.lower():
                return 25
        return 50

    def _protein_target(self, diseases, profile):
        try:
            w = float(profile.get("weight_kg", 70))
        except (ValueError, TypeError):
            w = 70.0
        for d in diseases:
            if "kidney" in d.lower() or "ckd" in d.lower():
                return round(w * 0.6, 1)
        return round(w * 0.8, 1)

    def save_output(self, result: Dict, label: str = "") -> dict:
        """
        Save pipeline output to outputs/ as JSON and CSV.
        - If the user already has output files, they are UPDATED (overwritten).
        - If no files exist for this user, new files are CREATED.
        - Filename format: {user_id}_safe_foods.json / .csv  (no timestamp in name)
        - The JSON stores created_at (first run) and last_updated (every run).
        """
        import json as _json
        uid      = result["user_id"]
        suffix   = f"_{label}" if label else ""
        json_file = output_path(f"{uid}{suffix}_safe_foods.json")
        csv_file  = output_path(f"{uid}{suffix}_safe_foods.csv")

        now = datetime.now().isoformat()
        is_update = os.path.exists(json_file)

        # Preserve created_at from the original file if this is an update
        created_at = now
        if is_update:
            try:
                with open(json_file) as f:
                    old_data = _json.load(f)
                created_at = old_data.get("created_at", now)
            except Exception:
                created_at = now

        # Build export payload
        payload = dict(
            **result["recommendation_context"],
            safe_foods   = result["safe_food_list"].to_dict(orient="records"),
            created_at   = created_at,
            last_updated = now,
        )

        export_json(payload, json_file)
        result["safe_food_list"].to_csv(csv_file, index=False)

        return {
            "json":      json_file,
            "csv":       csv_file,
            "is_update": is_update,
            "created_at":   created_at,
            "last_updated": now,
        }
