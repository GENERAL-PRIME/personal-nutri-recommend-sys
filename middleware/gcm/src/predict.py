from middleware.gcm.src.preprocess import clean_text
from middleware.gcm.src.model_utils import load_model
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # gcm/
MODEL_DIR = BASE_DIR / "models"

vectorizer = load_model(MODEL_DIR / "goal_vectorizer.pkl")
model = load_model(MODEL_DIR / "goal_classifier.pkl")


def classify_goal(goal_text: str) -> str:
    text = clean_text(goal_text)
    vec = vectorizer.transform([text])
    return model.predict(vec)[0]
