import re

# -------------------------------------------------
# CANONICAL ACTIVITY → MET
# -------------------------------------------------
MET_TABLE = {
    "sleeping": 0.9,
    "sitting": 1.2,
    "standing": 1.5,
    "reading": 1.3,
    "desk work": 1.5,
    "driving": 2.0,
    "slow walking": 2.0,
    "walking": 2.5,
    "brisk walking": 3.8,
    "walking uphill": 6.0,
    "stairs climbing": 8.0,
    "cooking": 2.5,
    "cleaning": 3.5,
    "sweeping": 3.3,
    "mopping": 3.8,
    "gardening": 4.0,
    "washing clothes": 3.0,
    "yoga": 3.0,
    "stretching": 2.8,
    "pilates": 3.5,
    "cycling slow": 4.0,
    "cycling": 6.0,
    "cycling fast": 8.0,
    "jogging": 7.0,
    "running": 8.0,
    "running fast": 10.0,
    "skipping rope": 10.0,
    "football": 7.0,
    "cricket": 5.0,
    "badminton": 6.0,
    "tennis": 7.3,
    "basketball": 8.0,
    "swimming": 7.0,
    "boxing": 9.0,
    "gym light": 4.0,
    "gym workout": 7.0,
    "weight training": 6.0,
    "crossfit": 9.0,
    "hiit": 9.5,
    "dancing slow": 3.0,
    "dancing": 5.5,
    "dancing fast": 7.0,
}

# -------------------------------------------------
# USER KEYWORDS → CANONICAL ACTIVITY
# -------------------------------------------------
ACTIVITY_KEYWORDS = {
    "sleeping": ["sleep", "sleeping", "nap"],
    "sitting": ["sit", "sitting"],
    "standing": ["stand", "standing"],
    "reading": ["read", "reading"],
    "desk work": ["desk", "office", "computer", "typing", "work"],
    "driving": ["drive", "driving"],
    "slow walking": ["slow walk", "casual walk"],
    "walking": ["walk", "walking"],
    "brisk walking": ["brisk walk", "fast walk"],
    "walking uphill": ["uphill walk", "hill walking"],
    "stairs climbing": ["stairs", "stair", "climb stairs"],
    "cooking": ["cook", "cooking"],
    "cleaning": ["clean", "cleaning"],
    "sweeping": ["sweep", "sweeping"],
    "mopping": ["mop", "mopping"],
    "gardening": ["garden", "gardening"],
    "washing clothes": ["wash clothes", "laundry"],
    "yoga": ["yoga"],
    "stretching": ["stretch", "stretching"],
    "pilates": ["pilates"],
    "cycling slow": ["slow cycling"],
    "cycling": ["cycle", "cycling", "bike"],
    "cycling fast": ["fast cycling"],
    "jogging": ["jog", "jogging"],
    "running": ["run", "running"],
    "running fast": ["sprint", "fast running"],
    "skipping rope": ["skip", "skipping", "rope"],
    "football": ["football", "soccer"],
    "cricket": ["cricket"],
    "badminton": ["badminton"],
    "tennis": ["tennis"],
    "basketball": ["basketball"],
    "swimming": ["swim", "swimming"],
    "boxing": ["boxing"],
    "gym light": ["light gym"],
    "gym workout": ["gym", "workout"],
    "weight training": ["weights", "weight training"],
    "crossfit": ["crossfit"],
    "hiit": ["hiit"],
    "dancing slow": ["slow dance"],
    "dancing": ["dance", "dancing"],
    "dancing fast": ["fast dance"],
}

SEDENTARY_ACTIVITIES = {
    "sleeping",
    "sitting",
    "standing",
    "reading",
    "desk work",
    "driving",
    "gardening",
}


# -------------------------------------------------
# FEATURE EXTRACTION
# -------------------------------------------------
def extract_features(text: str):
    text = text.lower().strip()

    # -------- ACTIVITY DETECTION --------
    activity = "walking"  # safe default
    found = False

    for canonical, keywords in ACTIVITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                activity = canonical
                found = True
                break
        if found:
            break

    met = MET_TABLE[activity]

    # -------- DURATION --------
    duration = 30
    dur_match = re.search(r"(\d+)\s*(hr|hour|hrs|hours|min|minute|minutes)", text)
    if dur_match:
        duration = int(dur_match.group(1))
        if dur_match.group(2).startswith("h"):
            duration *= 60

    # 🔒 Cap duration for classification (not physiology)
    duration = min(duration, 120)

    # -------- FREQUENCY --------
    frequency = 3
    freq_match = re.search(r"(\d+)\s*(day|days|time|times)", text)
    if freq_match:
        frequency = int(freq_match.group(1))

    weekly_met = met * duration * frequency

    # 🔒 HARD CAP for sedentary activities
    if activity in SEDENTARY_ACTIVITIES:
        weekly_met = min(weekly_met, 250)

    return met, duration, frequency, weekly_met
