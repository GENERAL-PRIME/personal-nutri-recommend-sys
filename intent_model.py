# backend/nlp/intent_model.py
import os
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

MODEL_DIR = "backend/models"
MODEL_PATH = os.path.join(MODEL_DIR, "intent_model.joblib")
VEC_PATH = os.path.join(MODEL_DIR, "intent_vec.joblib")

class IntentPredictor:
    def __init__(self):
        self.model = None
        self.vectorizer = None
        if os.path.exists(MODEL_PATH) and os.path.exists(VEC_PATH):
            self.model = joblib.load(MODEL_PATH)
            self.vectorizer = joblib.load(VEC_PATH)

    def predict(self, text):
        if self.model is None or self.vectorizer is None:
            # simple heuristic fallback
            t = text.lower()
            if any(k in t for k in ["plan", "diet", "calorie", "meal"]):
                return "get_plan"
            if any(k in t for k in ["i am", "age", "height", "weight", "kg", "cm", "lbs"]):
                return "set_profile"
            if any(k in t for k in ["allergy", "allergic", "vegan", "vegetarian"]):
                return "update_profile"
            if any(k in t for k in ["thank", "thanks", "bye"]):
                return "goodbye"
            return "unknown"
        X = self.vectorizer.transform([text])
        return self.model.predict(X)[0]

def train_intent_model(intents_csv="data/intents.csv"):
    """
    Train a TF-IDF + LinearSVC intent model.
    Expects intents_csv with columns: text,intent
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    df = pd.read_csv(intents_csv)
    vec = TfidfVectorizer(ngram_range=(1,2), max_features=3000)
    X = vec.fit_transform(df["text"].values)
    y = df["intent"].values
    clf = LinearSVC()
    clf.fit(X,y)
    joblib.dump(clf, MODEL_PATH)
    joblib.dump(vec, VEC_PATH)
    print("Saved intent model to", MODEL_PATH)

if __name__ == "__main__":
    train_intent_model()
