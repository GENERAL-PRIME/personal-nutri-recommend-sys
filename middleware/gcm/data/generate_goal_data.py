import csv
import random

random.seed(42)

# ---------- LOSS ----------
LOSS_TEMPLATES = [
    "I want to lose {}",
    "Trying to reduce {}",
    "Need to burn {}",
    "Planning to cut {}",
    "My goal is fat loss and {}",
    "I want to get lean by losing {}",
    "Trying to drop {}",
    "Looking to decrease {}",
    "I am aiming to lose {}",
    "I want to slim down by reducing {}",
]

LOSS_TERMS = [
    "weight",
    "body fat",
    "belly fat",
    "extra kilos",
    "fat",
    "calories",
    "excess weight",
    "unwanted fat",
    "overall body fat",
    "waist fat",
]

LOSS_MODIFIERS = ["", " safely", " naturally", " over time", " in a healthy way"]

# ---------- MAINTAIN ----------
MAINTAIN_TEMPLATES = [
    "I want to maintain my {}",
    "Just trying to stay {}",
    "My goal is to remain {}",
    "Focus is overall {}",
    "I want to keep my {} stable",
    "Trying to stay in {}",
    "No weight change, just {}",
    "My aim is to preserve my {}",
    "I want to continue being {}",
]

MAINTAIN_TERMS = [
    "weight",
    "fitness",
    "health",
    "shape",
    "physique",
    "current body",
    "overall wellness",
    "present fitness level",
    "body condition",
]

MAINTAIN_MODIFIERS = [
    "",
    " long term",
    " consistently",
    " without weight change",
    " as it is",
]

# ---------- GAIN ----------
GAIN_TEMPLATES = [
    "I want to gain {}",
    "Trying to build {}",
    "Need to increase {}",
    "My goal is muscle gain and {}",
    "Looking to add {}",
    "Want to bulk up and gain {}",
    "Trying to put on {}",
    "I am aiming to increase {}",
    "I want to grow my {}",
]

GAIN_TERMS = [
    "muscle",
    "muscle mass",
    "weight",
    "body mass",
    "strength",
    "size",
    "healthy weight",
    "lean muscle",
    "overall mass",
]

GAIN_MODIFIERS = [
    "",
    " naturally",
    " in a healthy way",
    " for strength",
    " for gym training",
]


def generate_samples(templates, terms, modifiers, label, n):
    samples = []
    for _ in range(n):
        t = random.choice(templates)
        term = random.choice(terms)
        mod = random.choice(modifiers)
        text = f"{t.format(term)}{mod}"
        samples.append((text, label))
    return samples


def main():
    data = []
    data += generate_samples(LOSS_TEMPLATES, LOSS_TERMS, LOSS_MODIFIERS, "loss", 1000)
    data += generate_samples(
        MAINTAIN_TEMPLATES, MAINTAIN_TERMS, MAINTAIN_MODIFIERS, "maintain", 1000
    )
    data += generate_samples(GAIN_TEMPLATES, GAIN_TERMS, GAIN_MODIFIERS, "gain", 1000)

    random.shuffle(data)

    with open("goal_intent_data.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["goal_text", "label"])
        writer.writerows(data)

    print("✅ Generated balanced dataset: 3,000 samples")


if __name__ == "__main__":
    main()
