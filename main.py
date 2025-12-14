from io_csv import load_meals_from_csv
from diseases import disease_rules
from planner import select_meals_for_day, adjust_portions_to_targets
from targets import compute_targets


def main():
    meals = load_meals_from_csv("indian_meals.csv")

    # Example inputs (replace with your UI values)
    age = int(input("Enter age (years): ") or 22)
    sex = input("Enter sex (M/F): ")
    height_cm = int(input("Enter height (cm): "))
    weight_kg = int(input("Enter weight (kg): "))
    diet_type = input("Enter diet type (veg/eggetarian/nonveg/jain): ")
    activity = input(
        "Enter activity level (sedentary/light/moderate/active/very active): "
    )
    goal = input("Enter goal (loss/maintain/gain): ")
    meal_frequency = int(input("Enter meal frequency (3-5): "))
    allergies_input = input(
        "Enter allergies (comma separated, e.g., gluten,nuts) or leave blank: "
    )
    allergies = (
        [allergy.strip().lower() for allergy in allergies_input.split(",")]
        if allergies_input
        else []
    )
    diseases_input = input(
        "Enter diseases (comma separated, e.g., diabetes,hypertension) or leave blank: "
    )
    diseases = (
        [disease.strip().lower() for disease in diseases_input.split(",")]
        if diseases_input
        else []
    )
    disliked_foods_input = input(
        "Enter disliked foods (comma separated) or leave blank: "
    )
    disliked_foods = (
        [food.strip().lower() for food in disliked_foods_input.split(",")]
        if disliked_foods_input
        else []
    )
    rules = disease_rules(diseases)
    day_meals = select_meals_for_day(
        meals,
        rules,
        allergies,
        diet_type.lower(),
        meal_frequency,
        disliked_foods=disliked_foods,
    )
    targets = compute_targets(
        age, sex, height_cm, weight_kg, activity.lower(), goal.lower()
    )
    adjusted_plan, summary = adjust_portions_to_targets(day_meals, targets)

    print("\n--- Suggested Indian Meal Plan ---\n")
    for meal in adjusted_plan:
        print(f"{meal['course'].upper()}: {meal['name']}  ({meal['portion_note']})")

    print("\n--- Nutrition Summary ---")
    for k, v in summary.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\n[ERROR]", e)
