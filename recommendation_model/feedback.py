"""
recommendation_model/feedback.py
==================================
Adaptive softmax-temperature tuning based on user meal ratings.

This module is purely additive: if there is no rating history (new user,
DB unavailable, too few ratings), it always falls back to the existing
fixed default (12.0) — identical to current system behaviour. Nothing
that already works can break by adding this file.

Concept
-------
Softmax temperature controls exploration vs. exploitation in _pick():
  - Lower temperature  -> more deterministic -> leans on top-scoring foods
  - Higher temperature -> more random        -> spreads chances more evenly

Here we adjust temperature PER USER based on their average meal rating
(1-5 stars, already collected via /api/meal/rate -> meal_ratings collection):

  - High average rating (>= 4.0) -> user is happy with picks
        -> lower temperature -> exploit more (stick closer to top scorers)
  - Low average rating (<= 2.5)  -> user is unhappy with picks
        -> raise temperature -> explore more (give lower-scored foods a
           better chance, in case the scoring formula is under-rating
           something this user actually likes)
  - Anything in between, or insufficient data -> keep the default

This is a simple, explainable heuristic — NOT a learned/gradient-based
model. It mirrors temperature annealing / epsilon-decay ideas from
reinforcement learning, but the adjustment rule itself is hand-designed,
not fit to data. That is an honest, presentable limitation with a clear
next step (learning-to-rank / contextual bandit) if asked in a viva.
"""

from typing import List, Optional

# ── Tunable constants (documented, not hidden magic numbers) ────────────────
BASE_TEMPERATURE = 12.0  # current fixed default used everywhere today
MIN_RATINGS_REQUIRED = 5  # don't adapt on a noisy/small sample
HIGH_RATING_THRESHOLD = 4.0  # avg rating at/above which we exploit more
LOW_RATING_THRESHOLD = 2.5  # avg rating at/below which we explore more
EXPLOIT_MULTIPLIER = 0.7  # shrinks temperature  (12.0 -> 8.4)
EXPLORE_MULTIPLIER = 1.4  # grows temperature    (12.0 -> 16.8)

# Safety bounds so temperature can never collapse to near-zero (would make
# selection fully deterministic / break softmax numerically) or blow up
# to pure randomness regardless of how ratings trend over time.
MIN_TEMPERATURE = 4.0
MAX_TEMPERATURE = 24.0


def _fetch_user_ratings(user_id: str, mdb_db) -> List[float]:
    """
    Pull all star ratings (1-5) a user has given, from the existing
    meal_ratings collection. Fails safe -> returns [] on any problem,
    so the caller always has a well-defined fallback path.
    """
    if mdb_db is None or not user_id:
        return []
    try:
        cursor = mdb_db["meal_ratings"].find(
            {"user_id": user_id}, {"rating": 1, "_id": 0}
        )
        return [float(r["rating"]) for r in cursor if "rating" in r]
    except Exception:
        return []


def compute_adaptive_temperature(
    user_id: str,
    mdb_db,
    base_temperature: float = BASE_TEMPERATURE,
) -> float:
    """
    Compute this user's current softmax temperature for _pick().

    Parameters
    ----------
    user_id          : the user's NRSxxxx id (or "GUEST"/"anonymous" -> no tuning)
    mdb_db           : the raw MongoDB `db` handle (utils.db.db). May be None.
    base_temperature : fallback value if there isn't enough signal to adapt.

    Returns
    -------
    float  — always a valid, bounded temperature. Never raises.
    """
    if not user_id or user_id.upper() in ("GUEST", "ANONYMOUS"):
        return base_temperature

    ratings = _fetch_user_ratings(user_id, mdb_db)

    if len(ratings) < MIN_RATINGS_REQUIRED:
        return base_temperature

    avg_rating = sum(ratings) / len(ratings)

    if avg_rating >= HIGH_RATING_THRESHOLD:
        new_temp = base_temperature * EXPLOIT_MULTIPLIER
    elif avg_rating <= LOW_RATING_THRESHOLD:
        new_temp = base_temperature * EXPLORE_MULTIPLIER
    else:
        new_temp = base_temperature

    # Clamp to safe bounds regardless of multiplier math above.
    new_temp = max(MIN_TEMPERATURE, min(MAX_TEMPERATURE, new_temp))
    return round(new_temp, 2)


def explain_temperature(
    user_id: str, mdb_db, base_temperature: float = BASE_TEMPERATURE
) -> dict:
    """
    Optional helper for demo/debugging: returns the temperature AND the
    reasoning behind it, so the UI (or your presentation) can show a
    human-readable explanation instead of just a number.

    Example return:
        {
            "user_id": "NRS0007",
            "num_ratings": 8,
            "avg_rating": 4.3,
            "base_temperature": 12.0,
            "final_temperature": 8.4,
            "mode": "exploit",
            "reason": "Average rating 4.3 >= 4.0 -> leaning on top-scoring foods more."
        }
    """
    ratings = _fetch_user_ratings(user_id, mdb_db)
    n = len(ratings)

    if not user_id or user_id.upper() in ("GUEST", "ANONYMOUS"):
        return {
            "user_id": user_id,
            "num_ratings": n,
            "avg_rating": None,
            "base_temperature": base_temperature,
            "final_temperature": base_temperature,
            "mode": "default",
            "reason": "Guest/anonymous user — no personalization applied.",
        }

    if n < MIN_RATINGS_REQUIRED:
        return {
            "user_id": user_id,
            "num_ratings": n,
            "avg_rating": None,
            "base_temperature": base_temperature,
            "final_temperature": base_temperature,
            "mode": "default",
            "reason": f"Only {n} rating(s) so far — need {MIN_RATINGS_REQUIRED}+ before adapting.",
        }

    avg_rating = round(sum(ratings) / n, 2)
    final_temp = compute_adaptive_temperature(user_id, mdb_db, base_temperature)

    if avg_rating >= HIGH_RATING_THRESHOLD:
        mode = "exploit"
        reason = f"Average rating {avg_rating} >= {HIGH_RATING_THRESHOLD} -> leaning on top-scoring foods more."
    elif avg_rating <= LOW_RATING_THRESHOLD:
        mode = "explore"
        reason = f"Average rating {avg_rating} <= {LOW_RATING_THRESHOLD} -> exploring more varied/lower-ranked foods."
    else:
        mode = "default"
        reason = f"Average rating {avg_rating} is in the neutral zone -> keeping default temperature."

    return {
        "user_id": user_id,
        "num_ratings": n,
        "avg_rating": avg_rating,
        "base_temperature": base_temperature,
        "final_temperature": final_temp,
        "mode": mode,
        "reason": reason,
    }


# ─────────────────────────────────────────────────────────────────────────
# Standalone sanity test — run this file directly with a fake in-memory
# ratings list to verify the logic WITHOUT needing MongoDB at all.
#   python recommendation_model/feedback.py
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    class _FakeCollection:
        def __init__(self, ratings):
            self._ratings = ratings

        def find(self, *_args, **_kwargs):
            return [{"rating": r} for r in self._ratings]

    class _FakeDB:
        def __init__(self, ratings):
            self._col = _FakeCollection(ratings)

        def __getitem__(self, _name):
            return self._col

    scenarios = {
        "New user, no ratings": [],
        "Too few ratings (3)": [5, 5, 4],
        "Happy user (avg 4.6)": [5, 5, 4, 5, 4, 5],
        "Unhappy user (avg 2.0)": [2, 1, 2, 3, 2, 2],
        "Neutral user (avg 3.2)": [3, 3, 4, 3, 3, 3],
    }

    print(
        f"{'Scenario':<28} {'#Ratings':<10} {'AvgRating':<10} {'Temperature':<12} Mode"
    )
    print("-" * 80)
    for label, ratings in scenarios.items():
        fake_db = _FakeDB(ratings)
        result = explain_temperature("NRS_TEST", fake_db)
        avg_display = result["avg_rating"] if result["avg_rating"] is not None else "-"
        print(
            f"{label:<28} {result['num_ratings']:<10} {str(avg_display):<10} "
            f"{result['final_temperature']:<12} {result['mode']}"
        )
