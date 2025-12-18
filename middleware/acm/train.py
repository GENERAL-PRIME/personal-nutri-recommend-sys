from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from pathlib import Path
import pandas as pd
import joblib


BASE_DIR = Path(__file__).resolve().parent  # acm/
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

MODEL_DIR.mkdir(exist_ok=True)

df = pd.read_csv(DATA_DIR / "activity_data.csv")


X = df[["age", "gender", "met", "duration", "frequency", "weekly_met"]]
y = df["label"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y  # 🔥 VERY IMPORTANT
)

model = RandomForestClassifier(
    n_estimators=100, max_depth=6, min_samples_leaf=20, random_state=42
)

model.fit(X_train, y_train)

print("Training accuracy:", model.score(X_train, y_train))
print("Testing accuracy:", model.score(X_test, y_test))

joblib.dump(model, MODEL_DIR / "activity_model.pkl")
