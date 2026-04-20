# Personalized Nutrition Recommendation System (NutriAI)

A compact web application and recommendation engine that generates personalised 7-day diet plans based on a user's profile (age, sex, weight, height), allergies, medical conditions and food dislikes. The project includes a food-filtering pipeline, a recommendation model and a simple web UI to register users and generate plans.

---

## Project layout

```
food_filter_project/
│
├── app.py                        ← Flask web app (serves the UI and recommendation API)
├── main.py                       ← CLI / alternative entry (interactive scripts)
├── templates/                    ← HTML templates (UI)
├── recommendation_model/         ← recommender, planner and helpers
├── models/                       ← food filtering pipeline (allergy/disease/dislike filters)
├── datasets/                     ← CSV data used by pipeline
├── outputs/                      ← generated plans / registry (users_registry.json)
├── requirements.txt              ← Python dependencies
├── README.md                     ← this file
└── ...
```

---

## Quick start (web UI)

1. Create and activate a Python 3.10+ virtual environment (recommended).

2. Install dependencies:

    ```powershell
    pip install -r requirements.txt
    ```

3. Start the Flask app (development):

    ```powershell
    python app.py
    ```

The app listens on http://localhost:5000. Open that URL in your browser.

Notes:
- The left sidebar lets you register a new user (auto-generated ID) or sign-in as a returning user using a saved `NRSxxxx` ID.
- After signing in, enter/confirm personal info and press "Generate My Diet Plan" to build a 7-day plan.

---

## Quick start (CLI)

Some utilities and the food-filter pipeline can be used from the command line. You can run the interactive CLI with:

```powershell
python main.py
```

Follow on-screen prompts to create a profile and export filtered foods.

---

## Important files

- `app.py` — Flask server providing the UI and API endpoints (`/api/options`, `/api/user/new`, `/api/user/login`, `/api/recommend`).
- `templates/index.html` — Single page UI (client-side JS handles rendering & API calls).
- `models/food_filter_pipeline.py` — Chains allergy, disease and dislike filters to produce the safe food list.
- `recommendation_model/recommender.py` — Builds the weekly meal plan from safe foods and user targets.
- `outputs/users_registry.json` — Stores registered users and last run timestamps.

---

## Notes & troubleshooting

- If the UI appears unresponsive, open browser DevTools (Console) — client-side JS errors are usually visible and indicate which function or element failed.
- New user registration returns an auto-generated ID. Save it (shown in the UID banner) for returning sign-ins.
- If plan generation fails with a server error referencing low safe-food count, loosen restrictions (remove some dislikes/allergies or change dietary preference) and try again.

---

## Contributing

This repo contains both the filtering logic and a simple web front-end. When making changes:
- Run the Flask app locally to verify UI flows.
- Keep datasets/ and outputs/ unchanged unless intentionally updating data or saving outputs.

---

If you want the README tailored to only the web app or the CLI subset, tell me which and I will trim it further.
