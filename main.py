from io_csv import load_meals_from_csv
from diseases import disease_rules
from planner import select_meals_for_day, adjust_portions_to_targets
from targets import compute_targets


def ask(prompt: str, default=None, cast=str):
    raw = input(f"{prompt} ").strip()
    if not raw:
        return default
    try:
        return cast(raw)
    except:
        print(f"Invalid input, using default = {default}")
        return default


def ask_list(prompt: str) -> list[str]:
    raw = input(prompt).strip()
    if not raw:
        return []
    parts = [x.strip().lower() for x in raw.split(",") if x.strip()]
    return parts


def main():
    try:
        meals = load_meals_from_csv("indian_meals.csv")
        if not meals:
            print("[ERROR] Meal database is empty.")
            return
    except Exception as e:
        print("[ERROR] Could not load CSV file:", e)
        return

    print("\n===== Personalized Indian Meal Planner =====\n")

    age = ask("Enter age (years):", cast=int)
    sex = ask("Enter sex (M/F):").upper()
    height_cm = ask("Enter height (cm):", cast=int)
    weight_kg = ask("Enter weight (kg):", cast=int)

    diet_type = ask("Enter diet type (veg/eggetarian/nonveg/jain):").lower()

    activity = ask(
        "Enter activity (sedentary/light/moderate/active/very active):"
    ).lower()

    goal = ask("Enter goal (loss/maintain/gain):").lower()

    meal_frequency = ask("Enter meal frequency (3-5) :", cast=int)
    if meal_frequency < 3:
        meal_frequency = 3
    if meal_frequency > 5:
        meal_frequency = 5

    allergies = ask_list(
        "Enter allergies (comma separated, e.g. gluten,nuts) or leave blank: "
    )
    diseases = ask_list(
        "Enter diseases (comma separated, e.g. diabetes,hypertension) or leave blank: "
    )
    disliked_foods = ask_list("Enter disliked foods (comma separated) or leave blank: ")

    # --------- Build diet constraints ----------
    rules = disease_rules(diseases)

    # --------- Select meals ----------
    day_meals = select_meals_for_day(
        meals,
        rules,
        allergies,
        diet_type,
        meal_frequency,
        disliked_foods=disliked_foods,
    )

    if not day_meals:
        print("\n[ERROR] No meals matched your restriction filters!")
        return

    # --------- Compute calorie/macros targets ----------
    targets = compute_targets(age, sex, height_cm, weight_kg, activity, goal)

    # --------- Adjust portions ----------
    adjusted_plan, summary = adjust_portions_to_targets(day_meals, targets)

    # --------- Display ----------
    print("\n===== Suggested Meal Plan =====\n")
    for meal in adjusted_plan:
        print(f"{meal['course'].upper()}: {meal['name']}  ({meal['portion_note']})")

    print("\n===== Nutrition Summary (Daily) =====")
    for k, v in summary.items():
        print(f"{k:12}: {v}")

    print("\n======================================\n")
    print("Meal plan generated successfully!\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[FATAL ERROR]", e)
