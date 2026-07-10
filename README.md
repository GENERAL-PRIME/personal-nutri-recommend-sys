# Personalized Nutrition Recommendation System (NutriAI)

A web application and recommendation engine that generates personalised 7-day diet plans based on a user's profile (age, sex, weight, height, dietary preference), allergies, medical conditions and food dislikes. The project includes a food-filtering pipeline, a recommendation/meal-planning model, a Flask API and a single-page web UI — all backed by MongoDB Atlas.

---

## Project layout

```
nutri_improved/
│
├── app.py                        ← Flask web app (serves the UI and all API endpoints)
├── diagnose.py                   ← Standalone script to sanity-check the MongoDB connection & data
├── requirements.txt              ← Python dependencies
├── README.md                     ← this file
│
├── templates/
│   └── index.html                ← Single-page UI (vanilla JS handles rendering & API calls)
│
├── models/                       ← Food-filtering pipeline
│   ├── allergy_filter.py
│   ├── disease_filter.py
│   ├── dislike_filter.py
│   └── food_filter_pipeline.py   ← Chains the three filters into one safe-food list
│
├── recommendation_model/         ← Recommendation & meal-planning engine
│   ├── recommender.py            ← Builds the weekly plan from the safe-food list + user targets
│   ├── meal_planner.py           ← Slot-by-slot meal assembly, macro balancing, variety rules
│   └── calculator.py             ← BMI/BMR/TDEE, macro targets, plan-duration & re-plan math
│
└── utils/
    ├── db.py                     ← MongoDB Atlas connection (users_col, plans_col, db)
    ├── data_loader.py            ← Loads food_data / allergy_data / disease_diet_data / dislike_data from Atlas
    └── helpers.py                ← Misc shared helpers
```

There is no local CSV/JSON data store in this version — `food_data`, `allergy_data`, `disease_diet_data` and `dislike_data` are all read from MongoDB Atlas collections at startup, and users/plans/check-ins are persisted to Atlas as well.

---

## Requirements

- Python 3.10+
- A MongoDB Atlas cluster (or any reachable MongoDB instance) with the reference collections populated: `food_data`, `allergy_data`, `disease_diet_data`, `dislike_data`.

---

## Setup

1. Create and activate a virtual environment (recommended):

    ```powershell
    python -m venv .venv
    .venv\Scripts\activate
    ```

2. Install dependencies:

    ```powershell
    pip install -r requirements.txt
    ```

3. Create a `.env` file in the project root with your MongoDB connection details:

    ```
    MONGO_URI=mongodb+srv://<user>:<password>@<cluster-url>/?retryWrites=true&w=majority
    MONGO_DB_NAME=Nutrition_Recommendation_System
    ```

    (`utils/db.py` loads this automatically via `python-dotenv`. If `MONGO_URI` is not set, the app logs a clear error at startup and database-backed routes will fail — there is no offline fallback.)

4. Start the Flask app:

    ```powershell
    python app.py
    ```

    The app will print connection/data-load status, then serve on **http://localhost:5000**.

5. (Optional) Verify your database setup independently before running the full app:

    ```powershell
    python diagnose.py
    ```

---

## Using the app

- **Register** a new user from the "New User" tab — fill in name, password, age, sex, weight, height and dietary preference. A `NRSxxxx` User ID is generated and shown; save it for future sign-ins.
- **Sign in** as a returning user with your `NRSxxxx` ID (and password, if set).
- Fill in / confirm your health profile (region, allergies, medical conditions, dislikes) and click **Generate My Diet Plan** to build a 7-day plan. Once a plan exists, the button switches to **Regenerate My Diet Plan**.
- From the profile dropdown you can view your weight, height, diet preference and BMI (computed live from weight/height), toggle dark mode, edit your profile, or sign out.
- Use the weekly check-in and "Before vs After" flows to track weight/waist changes over the plan duration and get an updated plan.

---

## Key API endpoints (`app.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/options` | GET | Allergy/disease/dislike option lists for the UI |
| `/api/user/new` | POST | Register a new user |
| `/api/user/login` | POST | Sign in, returns user profile + last saved plan (if any) |
| `/api/user/update_meta` | POST | Edit profile (name, age, sex, weight, height, dietary preference) |
| `/api/user/set_password` | POST | Set/change password |
| `/api/recommend` | POST | Generate/regenerate a 7-day plan |
| `/api/plan/update` | POST | Update an existing plan in place |
| `/api/food/swap_options` | POST | Get alternative food options for a meal slot |
| `/api/meal/rate` / `/api/meal/ratings/<user_id>` | POST / GET | Rate meals, fetch saved ratings |
| `/api/user/checkin` / `/api/user/checkins/<user_id>` | POST / GET | Weekly weight/waist check-ins |
| `/api/user/countdown/<user_id>` | GET | Days/weeks remaining on the current plan |
| `/api/user/before_after` | POST | Final measurements → before/after comparison + new suggested goal |
| `/api/plan/save` | POST | Persist the current plan |

---

## Notes & troubleshooting

- If the app can't connect to MongoDB, check `MONGO_URI`/`MONGO_DB_NAME` in `.env` and your Atlas cluster's network access list (IP allow-list). Startup logs will show `[MongoDB] ✗ Connection failed: ...` with the underlying error.
- If the UI appears unresponsive, open browser DevTools → Console; client-side JS errors usually point directly at the failing function.
- If plan generation fails with an error about a low safe-food count, loosen restrictions (fewer dislikes/allergies, or a different dietary preference) and try again.
- All JSON API responses are sanitized to convert `NaN`/`Infinity` floats to `null` and MongoDB `ObjectId`/`datetime` values to strings, so raw database documents can be returned safely.

---

## Recent fixes

- **Weekly check-in `500` error (`ObjectId not JSON serializable`)** — `insert_one()` mutates the inserted dict in place, adding a MongoDB `ObjectId` under `_id`; that field is now stripped before the response is serialized, and the JSON sanitizer also converts any stray `ObjectId`/`datetime` values as a safety net.
- **Dietary preference not collected at registration** — the registration form now includes a Dietary Preference selector (Non-Vegetarian / Vegetarian / Vegan / Jain / Halal) which is sent to `/api/user/new` and stored immediately, instead of always defaulting to "None" until edited afterward in the profile tab.
- **"Regenerate" button showing before any plan existed** — the Generate/Regenerate button label is now derived from whether the signed-in user actually has an existing plan (on login, after generating, and on sign-out), instead of leaking state left over from a previous session in the page.
- **BMI missing from the profile dropdown after registration** — BMI is now computed client-side directly from the user's weight/height (with the generated plan's BMI used only as a fallback), so it displays immediately after registration rather than only after a plan has been generated.

---

## Contributing

When making changes:
- Run the Flask app locally against a test Atlas database to verify UI flows end-to-end (register → generate plan → check-in → before/after).
- Keep `models/` and `recommendation_model/` changes covered by a manual run of `diagnose.py` and a fresh plan generation before committing.
- Never commit `.env` or real Atlas credentials (already covered by `.gitignore`).
