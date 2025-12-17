import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import classification_report
from pathlib import Path

from preprocess import clean_text
from model_utils import save_model

# ---------- Path setup (ROBUST) ----------
BASE_DIR = Path(__file__).resolve().parent.parent  # gcm/
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

MODEL_DIR.mkdir(exist_ok=True)

# ---------- Load data ----------
df = pd.read_csv(DATA_DIR / "goal_intent_data.csv")

df["goal_text"] = df["goal_text"].apply(clean_text)

X = df["goal_text"]
y = df["label"]

# ---------- Vectorization ----------
vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")

X_vec = vectorizer.fit_transform(X)

# ---------- Train-test split (STRATIFIED) ----------
X_train, X_test, y_train, y_test = train_test_split(
    X_vec, y, test_size=0.2, random_state=42, stratify=y
)

# ---------- Model ----------
model = LinearSVC()
model.fit(X_train, y_train)

# ---------- Evaluation ----------
y_pred = model.predict(X_test)
print(classification_report(y_test, y_pred))

# ---------- Save artifacts ----------
save_model(vectorizer, MODEL_DIR / "goal_vectorizer.pkl")
save_model(model, MODEL_DIR / "goal_classifier.pkl")

print("✅ Goal Classification Model trained and saved")
