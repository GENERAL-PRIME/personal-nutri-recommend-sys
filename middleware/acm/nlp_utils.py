import re

MET_TABLE = {
    "slow walking": 2.0,
    "walking": 2.5,
    "brisk walking": 3.8,
    "jogging": 7.0,
    "running": 8.0,
    "cycling": 6.0,
    "yoga": 3.0,
    "gym": 7.0,
}


def extract_features(text):
    text = text.lower()

    # Activity
    activity = "walking"
    for k in MET_TABLE:
        if k in text:
            activity = k
            break

    met = MET_TABLE[activity]

    # Duration
    dur_match = re.search(r"(\d+)\s*(hr|hour|hrs|hours|min|minute|minutes)", text)
    duration = int(dur_match.group(1)) if dur_match else 30
    if dur_match and dur_match.group(2).startswith("h"):
        duration *= 60

    # Frequency
    freq_match = re.search(r"(\d+)\s*(days|times)", text)
    frequency = int(freq_match.group(1)) if freq_match else 3

    weekly_met = met * duration * frequency

    return met, duration, frequency, weekly_met
