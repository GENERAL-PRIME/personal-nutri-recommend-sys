import joblib
import pandas as pd
from middleware.acm.nlp_utils import extract_features
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent / "models" / "activity_model.pkl"
model = joblib.load(MODEL_PATH)

FEATURE_NAMES = ["age", "gender", "met", "duration", "frequency", "weekly_met"]


def predict_activity_class(age, sex, activity_text):
    met, duration, frequency, weekly_met = extract_features(activity_text)
    gender_bin = 1 if sex.upper() == "M" else 0

    X = pd.DataFrame(
        [[age, gender_bin, met, duration, frequency, weekly_met]], columns=FEATURE_NAMES
    )

    return model.predict(X)[0].lower()
