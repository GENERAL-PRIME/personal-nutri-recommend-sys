<<<<<<< HEAD
# 🥗 Food Filtering Module — AI Personalised NRS

Part of the **AI Personalised Nutrition Recommendation System (NRS)** project.

This module sits between the **User Profile** and the **Nutrition & Diet Recommendation Model**. It filters the full food database down to a personalised safe food list based on the user's allergies, diseases, and dislikes.

---

## 📁 Project Structure

```
food_filter_project/
│
├── main.py                        ← Entry point (run this)
│
├── models/
│   ├── allergy_filter.py          ← Stage 1: Allergy-based filtering
│   ├── disease_filter.py          ← Stage 2: Disease-based filtering
│   ├── dislike_filter.py          ← Stage 3: Preference-based filtering
│   └── food_filter_pipeline.py    ← Master pipeline (chains all 3)
│
├── datasets/
│   ├── food_data.csv              ← 100 foods with 35 nutritional columns
│   ├── allergy_data.csv           ← 14 allergy types + rules
│   ├── disease_diet_data.csv      ← 20 diseases + nutritional limits
│   └── dislike_data.csv           ← 30 dislike/preference types
│
├── utils/
│   ├── input_collector.py         ← Interactive CLI user input session
│   ├── display.py                 ← Pretty-print tables and reports
│   └── helpers.py                 ← Shared utilities (paths, colours, export)
│
├── outputs/                       ← Auto-generated on each run
│   ├── USR001_..._safe_foods.json ← For the Recommendation Model
│   └── USR001_..._safe_foods.csv  ← Spreadsheet view
│
├── .vscode/
│   ├── launch.json                ← Run configurations (F5 to launch)
│   └── settings.json              ← Editor settings
│
└── requirements.txt
```

---

## ⚙️ Setup in VSCode

### 1. Install dependencies

Open the **VSCode integrated terminal** (`Ctrl+`` `) and run:

```bash
pip install -r requirements.txt
```

### 2. Open the project folder

`File → Open Folder` → select `food_filter_project/`

### 3. Select Python interpreter

Press `Ctrl+Shift+P` → `Python: Select Interpreter` → choose Python 3.10+

### 4. Run the program

**Option A — F5 key:**
- Press `F5` or go to `Run → Start Debugging`
- Select `"▶  Run Food Filter (Interactive)"` from the dropdown

**Option B — Terminal:**
```bash
python main.py              # interactive mode (enter your own profile)
python main.py --demo       # pick a preset demo profile
```

---

## 🏃 How It Works

### Interactive Mode (`python main.py`)

The program will walk you through 5 steps:

```
Step 1 — Basic Information      (User ID, name, age, sex, weight, height)
Step 2 — Dietary Preference     (vegetarian / vegan / jain / halal / none)
Step 3 — Allergies              (enter multiple, one per line)
Step 4 — Medical Conditions     (enter multiple, one per line)
Step 5 — Food Dislikes          (enter multiple, one per line)
```

**You can enter multiple values** for allergies, diseases, and dislikes — one per line, or comma-separated on one line. Press **Enter on an empty line** to finish each section.

Example input for allergies:
```
> gluten
> shellfish
> nuts
>           ← empty line to finish
```

Or comma-separated:
```
> gluten, shellfish, nuts
>           ← empty line to finish
```

---

## 🔄 Pipeline Flow

```
User Profile (allergies, diseases, dislikes)
        │
        ▼
┌─────────────────────────┐
│  Stage 1: Allergy Filter │  Removes allergen-containing foods (hard remove)
│  14 allergen types       │  Critical safety warnings for anaphylactic allergens
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Stage 2: Disease Filter │  Applies nutritional limits (sodium, sugar, GI, etc.)
│  20 disease conditions   │  Scores remaining foods for disease suitability
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Stage 3: Dislike Filter │  Removes disliked foods / enforces dietary preferences
│  30 dislike types        │  Handles vegetarian, vegan, jain, cultural restrictions
└────────────┬────────────┘
             │
             ▼
   ✅ Safe Food List + Recommendation Context
        │
        └──→  Nutrition & Diet Recommendation Model
```

---

## 📤 Output Files (in `outputs/`)

### `*_safe_foods.json`
Forwarded to the Recommendation Model. Contains:
- `safe_food_ids` — list of safe food IDs
- `safe_foods` — full food records with nutritional data
- `recommendation_context` — disease flags, calorie/sodium/sugar limits, dietary flags

### `*_safe_foods.csv`
Same data as a spreadsheet for inspection.

---

## 🏥 Supported Allergies
gluten, wheat, celiac, dairy, milk, lactose, tree nuts, peanuts, eggs,
shellfish, fish, seafood, soy, sesame, sulfites, histamine, fodmap, fructose

## 🩺 Supported Diseases
Type 2 Diabetes, Type 1 Diabetes, Hypertension, Heart Disease, Kidney Disease (CKD),
Gout, PCOS, Hypothyroidism, Hyperthyroidism, Anemia, Celiac Disease, IBD, GERD,
Fatty Liver Disease (NAFLD), Obesity, Osteoporosis, High Cholesterol,
Lactose Intolerance, Cancer, Thyroid Cancer

## 🚫 Supported Dislikes
Seafood, Red Meat, Eggs, Dairy, Mushrooms, Nuts, Legumes, Spicy Foods,
Bitter Foods, Fried Foods, Leafy Greens, Onion & Garlic, Bitter Gourd,
Bottle Gourd, Jain Diet, No Beef, No Pork, Vegan, Vegetarian, and more
=======
# Personalized Nutrition Recommendation System
>>>>>>> 0d6f3368a9c3c4c60df0dd093b802bf61d97a4d8
