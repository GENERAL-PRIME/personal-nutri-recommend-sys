import joblib


def save_model(obj, path):
    joblib.dump(obj, path)


def load_model(path):
    return joblib.load(path)
