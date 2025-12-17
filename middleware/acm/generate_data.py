import random
import pandas as pd


activities = [
    ("sleeping", 0.9),
    ("sitting", 1.2),
    ("standing", 1.5),
    ("reading", 1.3),
    ("desk work", 1.5),
    ("driving", 2.0),
    ("slow walking", 2.0),
    ("walking", 2.5),
    ("brisk walking", 3.8),
    ("walking uphill", 6.0),
    ("stairs climbing", 8.0),
    ("cooking", 2.5),
    ("cleaning", 3.5),
    ("sweeping", 3.3),
    ("mopping", 3.8),
    ("gardening", 4.0),
    ("washing clothes", 3.0),
    ("yoga", 3.0),
    ("stretching", 2.8),
    ("pilates", 3.5),
    ("cycling slow", 4.0),
    ("cycling", 6.0),
    ("cycling fast", 8.0),
    ("jogging", 7.0),
    ("running", 8.0),
    ("running fast", 10.0),
    ("skipping rope", 10.0),
    ("football", 7.0),
    ("cricket", 5.0),
    ("badminton", 6.0),
    ("tennis", 7.3),
    ("basketball", 8.0),
    ("swimming", 7.0),
    ("boxing", 9.0),
    ("gym light", 4.0),
    ("gym workout", 7.0),
    ("weight training", 6.0),
    ("crossfit", 9.0),
    ("hiit", 9.5),
    ("dancing slow", 3.0),
    ("dancing", 5.5),
    ("dancing fast", 7.0),
]


# -------------------------------------------------
# AGE SCALING (CONTINUOUS)
# -------------------------------------------------
def age_scale(age):
    if age < 30:
        return 1.0 + (30 - age) * 0.005
    else:
        return max(0.65, 1.0 - (age - 30) * 0.01)


# -------------------------------------------------
# AGE-SENSITIVE CLASSIFICATION
# -------------------------------------------------
def classify(age, weekly_met):
    base = {"Sedentary": 300, "Light": 600, "Moderate": 1200, "Active": 2000}

    scale = age_scale(age)

    t1 = base["Sedentary"] * scale
    t2 = base["Light"] * scale
    t3 = base["Moderate"] * scale
    t4 = base["Active"] * scale

    if weekly_met < t1:
        return "Sedentary"
    elif weekly_met < t2:
        return "Light"
    elif weekly_met < t3:
        return "Moderate"
    elif weekly_met < t4:
        return "Active"
    else:
        return "Very Active"


# -------------------------------------------------
# DATA GENERATION
# -------------------------------------------------
rows = []

for _ in range(5000):
    age = random.randint(18, 75)
    gender = random.choice([0, 1])  # 1 = male, 0 = female
    activity, met = random.choice(activities)
    duration = random.choice([20, 30, 45, 60])
    freq = random.randint(2, 6)

    weekly_met = met * duration * freq
    label = classify(age, weekly_met)

    rows.append([age, gender, met, duration, freq, weekly_met, label])

df = pd.DataFrame(
    rows,
    columns=["age", "gender", "met", "duration", "frequency", "weekly_met", "label"],
)

df.to_csv("acm/data/activity_data.csv", index=False)
print("Dataset generated:", len(df))
