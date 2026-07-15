"""
recommendation_model/meal_planner.py  v3.0
==========================================
CUISINE-COHERENT INDIAN THALI MEAL PLANNER

Staple is chosen first. Every other role (protein, vegetable,
accompaniment, beverage) is constrained by the staple's cuisine type
and pairing rules. Results are realistic combinations people actually eat.

  Idli/Dosa   → Sambar + Coconut Chutney + Filter Coffee
  Roti/Paratha → Dal/Paneer + Sabzi + Raita + Chai
  Rice         → Dal/Curry + Sabzi + Raita/Salad
  Biryani      → Raita + Salad  (no extra protein needed)
  Poha/Upma    → Dahi/Chutney + Chai
"""

import random
import pandas as pd
from typing import Dict, List, Optional, Set, Tuple

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

ZONE_CUISINES = {
    "north": [
        "North Indian",
        "Kashmiri",
        "Awadhi",
        "Punjabi",
        "Rajasthani",
        "UP",
        "Haryanvi",
        "Himachali",
        "Kumaoni",
        "Garhwali",
        "Sindhi",
    ],
    "south": [
        "South Indian",
        "Kerala",
        "Tamil Nadu",
        "Karnataka",
        "Andhra",
        "Chettinad",
        "Hyderabadi",
        "Telangana",
        "Mangalorean",
        "Coorg",
        "Nair",
        "Syrian Christian",
    ],
    "east": [
        "Bengali",
        "Odia",
        "Bihari",
        "Assamese",
        "Northeast Indian",
        "Naga",
        "Mizo",
        "Tripuri",
        "Sikkimese",
        "Arunachali",
        "Manipuri",
        "Khasi",
        "Nepali/Sikkimese",
        "Jharkhand",
    ],
    "west": ["Maharashtrian", "Gujarati", "Goan", "Konkan", "Malvani", "Saraswat"],
    "central": ["Madhya Pradesh", "Chhattisgarhi", "Jain", "Bundelkhandi"],
}

# Cuisines that must NEVER appear for a given zone (exclusion list)
ZONE_EXCLUDE = {
    "north": [
        "South Indian",
        "Kerala",
        "Tamil Nadu",
        "Karnataka",
        "Andhra",
        "Chettinad",
        "Hyderabadi",
        "Telangana",
        "Bengali",
        "Odia",
        "Assamese",
        "Northeast Indian",
        "Naga",
        "Mizo",
        "Manipuri",
        "Goan",
        "Konkan",
    ],
    "south": [
        "North Indian",
        "Punjabi",
        "Rajasthani",
        "Kashmiri",
        "Awadhi",
        "UP",
        "Haryanvi",
        "Bengali",
        "Odia",
        "Assamese",
        "Northeast Indian",
        "Gujarati",
        "Goan",
        "Konkan",
    ],
    "east": [
        "South Indian",
        "Kerala",
        "Tamil Nadu",
        "Karnataka",
        "Andhra",
        "Chettinad",
        "Hyderabadi",
        "Telangana",
        "North Indian",
        "Punjabi",
        "Rajasthani",
        "Kashmiri",
        "Awadhi",
        "Gujarati",
        "Goan",
        "Konkan",
        "Rajasthani",
    ],
    "west": [
        "South Indian",
        "Kerala",
        "Tamil Nadu",
        "Karnataka",
        "Andhra",
        "Hyderabadi",
        "Bengali",
        "Odia",
        "Assamese",
        "Northeast Indian",
        "Kashmiri",
        "Naga",
    ],
    "central": [
        "South Indian",
        "Kerala",
        "Tamil Nadu",
        "Goan",
        "Hyderabadi",
        "Bengali",
        "Assamese",
        "Northeast Indian",
        "Naga",
        "Mizo",
        "Manipuri",
    ],
    "any": [],
}

# Which proteins / accompaniments / beverages pair with which staple_type
# East Indian staple pairings — fish curry, dalma, cholar dal, mustard-based dishes
EAST_BREAKFAST_COMBOS = [
    ["Luchi", "Aloor Dom"],
    ["Luchi", "Cholar Dal"],
    ["Muri", "Chanachur"],
    ["Pitha", "Mishti Doi"],
    ["Idli", "Sambar"],  # fallback
]

PAIRING_RULES = {
    "east_breakfast": {
        "protein_kw": [
            "dalma",
            "cholar",
            "moong",
            "lentil",
            "mishti doi",
            "dahi",
            "curd",
            "fish",
            "egg",
            "sorshe",
            "mustard",
            "posto",
            "panch phoron",
        ],
        "protein_cats": ["dals & legumes", "dairy & paneer", "seafood", "egg dishes"],
        "acc_kw": ["mishti doi", "doi", "achar", "kasundi", "mustard sauce", "posto"],
        "bev_kw": ["cha", "tea", "chai", "milk", "lassi", "coconut water"],
        "skip": [],
    },
    "south_breakfast": {
        "protein_kw": [
            "sambar",
            "rasam",
            "coconut chutney",
            "kadala",
            "parippu",
            "molagapodi",
            "avial",
            "khatta dal",
            "moru",
            "curd",
        ],
        "protein_cats": ["dals & legumes", "dairy & paneer"],
        "acc_kw": [
            "coconut chutney",
            "tomato chutney",
            "mint chutney",
            "sambar",
            "gun powder",
            "gunpowder",
            "idli podi",
        ],
        "bev_kw": ["coffee", "filter coffee", "rose milk", "chai", "tea", "milk"],
        "skip": [],
    },
    "roti": {
        "protein_kw": [
            "dal",
            "daal",
            "rajma",
            "chole",
            "chana",
            "maa",
            "pindi",
            "paneer",
            "chicken",
            "mutton",
            "egg",
            "fish",
            "kadhi",
            "arhar",
            "moong",
            "urad",
            "haleem",
            "keema",
        ],
        "protein_cats": [
            "dals & legumes",
            "dairy & paneer",
            "meat dishes",
            "egg dishes",
            "seafood",
        ],
        "acc_kw": [
            "raita",
            "dahi",
            "curd",
            "pickle",
            "achar",
            "salad",
            "green chutney",
            "mint chutney",
            "kachumber",
        ],
        "bev_kw": ["chai", "lassi", "buttermilk", "chaas", "tea", "milk", "lassi"],
        "skip": [],
    },
    "rice": {
        "protein_kw": [
            "dal",
            "sambar",
            "rasam",
            "curry",
            "kadhi",
            "fish",
            "chicken",
            "prawn",
            "rajma",
            "chole",
            "kootu",
            "avial",
            "dalma",
            "amti",
            "daal",
            "lentil",
        ],
        "protein_cats": ["dals & legumes", "meat dishes", "seafood", "dairy & paneer"],
        "acc_kw": [
            "raita",
            "dahi",
            "papad",
            "pappad",
            "pickle",
            "achar",
            "chutney",
            "kachumber",
            "salad",
        ],
        "bev_kw": ["buttermilk", "chaas", "lassi", "jaljeera", "kokum", "sol kadhi"],
        "skip": [],
    },
    "biryani": {
        "protein_kw": [],
        "protein_cats": [],
        "acc_kw": ["raita", "salan", "mirchi", "onion salad", "kachumber"],
        "bev_kw": ["lassi", "buttermilk", "chaas", "sharbat", "jaljeera"],
        "skip": ["protein", "vegetable"],
    },
    "snack_breakfast": {
        "protein_kw": ["curd", "dahi", "raita", "lassi", "buttermilk", "chaas"],
        "protein_cats": ["dairy & paneer"],
        "acc_kw": ["green chutney", "coconut chutney", "tamarind chutney"],
        "bev_kw": ["chai", "tea", "coffee", "milk", "green tea"],
        "skip": ["vegetable"],
    },
    "western_breakfast": {
        "protein_kw": [
            "egg",
            "milk",
            "yogurt",
            "omelette",
            "bhurji",
            "cheddar",
            "peanut butter",
            "greek yogurt",
            "paneer",
        ],
        "protein_cats": ["egg dishes", "dairy & paneer"],
        "acc_kw": ["fruit", "salad", "honey"],
        "bev_kw": ["tea", "coffee", "milk", "juice", "green tea"],
        "skip": [],
    },
    "other": {
        "protein_kw": [],
        "protein_cats": ["dals & legumes", "dairy & paneer", "meat dishes"],
        "acc_kw": ["raita", "salad", "chutney"],
        "bev_kw": ["chai", "water", "buttermilk", "lassi"],
        "skip": [],
    },
}

# Slot structure: ordered list of roles
SLOT_STRUCTURE = {
    "breakfast": ["staple", "protein", "beverage"],
    "mid_morning": ["fruit", "snack", "beverage"],
    "lunch": ["staple", "protein", "vegetable", "accompaniment", "beverage"],
    "afternoon": ["snack", "beverage"],
    "evening_snack": ["snack", "beverage"],
    "dinner": ["staple", "protein", "vegetable", "accompaniment"],
}

# Calorie % per role per slot
SLOT_CAL_PCT = {
    "breakfast": {"staple": 0.50, "protein": 0.30, "beverage": 0.20},
    "mid_morning": {"fruit": 0.50, "snack": 0.30, "beverage": 0.20},
    "lunch": {
        "staple": 0.35,
        "protein": 0.28,
        "vegetable": 0.20,
        "accompaniment": 0.10,
        "beverage": 0.07,
    },
    "afternoon": {"snack": 0.60, "beverage": 0.40},
    "evening_snack": {"snack": 0.60, "beverage": 0.40},
    "dinner": {
        "staple": 0.38,
        "protein": 0.30,
        "vegetable": 0.22,
        "accompaniment": 0.10,
    },
}

ROLE_FALLBACKS = {
    "fruit": ["snack", "other"],
    "vegetable": ["protein", "snack"],
    "accompaniment": ["vegetable", "snack"],
    "beverage": ["snack"],
    "staple": ["snack"],
    "protein": ["vegetable", "snack"],
    "snack": ["fruit"],
}

UNIT_HINDI = {
    "piece": "नग/पीस",
    "bowl": "कटोरी",
    "glass": "गिलास",
    "cup": "कप",
    "katori": "कटोरी",
    "plate": "प्लेट",
    "gram": "ग्राम",
    "tablespoon": "चम्मच",
}

# ─────────────────────────────────────────────────────────────────────────────
#  REALISTIC MEAL TEMPLATES
#  Each template is a list of (role, keyword_fragments) tuples.
#  The planner tries to match these against the food DB, producing
#  coherent meals that real Indians actually eat.
# ─────────────────────────────────────────────────────────────────────────────

MEAL_TEMPLATES = {
    # ════════════════════════════════════════════════════════════════════════
    #  EAST ZONE — Bengali / Odia / Bihari / Assamese
    #  Breakfast: luchi-aloor dom, roti-torkari, muri-chanachur, bread-egg
    #  Lunch: rice + dal + fish/meat/egg + bhaja + papad (THE standard Bengali lunch)
    #  Dinner: roti/chapati + sabzi/egg/fish curry (lighter than lunch)
    #  Weekend lunch/dinner: biryani / fried rice + gravy (cheat meal)
    # ════════════════════════════════════════════════════════════════════════
    "east_breakfast": [
        # Authentic Bengali/Odia breakfast — light, never heavy
        [("staple", "luchi"), ("protein", "aloor dom"), ("beverage", "tea")],
        [("staple", "luchi"), ("protein", "cholar dal"), ("beverage", "cha")],
        [("staple", "roti"), ("protein", "aloo sabzi"), ("beverage", "tea")],
        [("staple", "paratha"), ("protein", "aloo"), ("beverage", "tea")],
        [
            ("staple", "bread"),
            ("protein", "egg"),
            ("protein", "butter"),
            ("beverage", "tea"),
        ],
        [("staple", "bread"), ("protein", "omelette"), ("beverage", "tea")],
        [("staple", "poha"), ("protein", "dahi"), ("beverage", "tea")],
        [("staple", "muri"), ("protein", "dahi"), ("beverage", "tea")],
        [("staple", "upma"), ("protein", "dahi"), ("beverage", "tea")],
        [("staple", "pitha"), ("protein", "doi"), ("beverage", "tea")],
    ],
    "east_lunch": [
        # Classic Bengali lunch — rice is mandatory, fish/meat/egg + dal + bhaja
        [
            ("staple", "rice"),
            ("protein", "fish curry"),
            ("protein", "dal"),
            ("vegetable", "begun bhaja"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "macher jhol"),
            ("protein", "dal"),
            ("vegetable", "aloo bhaja"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "kosha mangsho"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "shorshe ilish"),
            ("protein", "dal"),
            ("vegetable", "bhaja"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "egg curry"),
            ("protein", "dal"),
            ("vegetable", "aloo posto"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "chingri malai curry"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "dalma"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "chicken curry"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "moong dal"),
            ("vegetable", "aloo posto"),
            ("accompaniment", "papad"),
        ],
    ],
    "east_lunch_weekend": [
        # Weekend cheat meals — Bengali style
        [
            ("staple", "chicken biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "mutton biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "egg biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "fried rice"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "chowmein"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
    ],
    "east_dinner": [
        # Lighter than lunch — roti/chapati based
        [
            ("staple", "roti"),
            ("protein", "egg curry"),
            ("vegetable", "aloo sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "fish curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "roti"),
            ("protein", "aloo sabzi"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "khichdi"),
            ("protein", "dal"),
            ("accompaniment", "pickle"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "luchi"),
            ("protein", "cholar dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
    ],
    "east_dinner_weekend": [
        [
            ("staple", "fried rice"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "chowmein"),
            ("protein", "chicken manchurian"),
            ("accompaniment", "salad"),
        ],
        [("staple", "luchi"), ("protein", "kosha mangsho"), ("accompaniment", "salad")],
    ],
    # ════════════════════════════════════════════════════════════════════════
    #  NORTH ZONE — Punjabi / UP / Rajasthani / Awadhi
    #  Breakfast: paratha + dahi/pickle, bread-butter, poha, upma, bread-egg
    #  Lunch: roti + dal/paneer/chicken + sabzi + raita
    #  Dinner: roti/chapati + dal/sabzi (lighter), khichdi sometimes
    # ════════════════════════════════════════════════════════════════════════
    "north_breakfast": [
        [
            ("staple", "paratha"),
            ("protein", "curd"),
            ("accompaniment", "pickle"),
            ("beverage", "chai"),
        ],
        [
            ("staple", "paratha"),
            ("protein", "aloo"),
            ("accompaniment", "pickle"),
            ("beverage", "chai"),
        ],
        [
            ("staple", "bread"),
            ("protein", "butter"),
            ("protein", "omelette"),
            ("beverage", "tea"),
        ],
        [
            ("staple", "bread"),
            ("protein", "egg"),
            ("protein", "butter"),
            ("beverage", "tea"),
        ],
        [("staple", "poha"), ("protein", "dahi"), ("beverage", "chai")],
        [("staple", "upma"), ("protein", "dahi"), ("beverage", "chai")],
        [("staple", "puri"), ("protein", "aloo sabzi"), ("beverage", "chai")],
        [("staple", "bread"), ("protein", "paneer"), ("beverage", "tea")],
        [("staple", "oats"), ("protein", "milk"), ("beverage", "tea")],
    ],
    "north_lunch": [
        [
            ("staple", "roti"),
            ("protein", "dal makhani"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
            ("beverage", "lassi"),
        ],
        [
            ("staple", "roti"),
            ("protein", "rajma"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
            ("beverage", "lassi"),
        ],
        [
            ("staple", "roti"),
            ("protein", "paneer"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "rice"),
            ("protein", "dal tadka"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "chole"),
            ("vegetable", "sabzi"),
            ("accompaniment", "onion"),
            ("beverage", "lassi"),
        ],
        [
            ("staple", "rice"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "roti"),
            ("protein", "kadhi"),
            ("vegetable", "aloo"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "roti"),
            ("protein", "mutton curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "rice"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
    ],
    "north_lunch_weekend": [
        [
            ("staple", "chicken biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "mutton biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "chole bhature"),
            ("accompaniment", "onion"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "paneer biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
    ],
    "north_dinner": [
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "palak"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "roti"),
            ("protein", "paneer"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "egg bhurji"),
            ("vegetable", "sabzi"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "khichdi"),
            ("protein", "dal"),
            ("accompaniment", "papad"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "bhindi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "aloo sabzi"),
            ("protein", "dal"),
            ("accompaniment", "pickle"),
        ],
    ],
    "north_dinner_weekend": [
        [
            ("staple", "paratha"),
            ("protein", "paneer"),
            ("accompaniment", "raita"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "naan"),
            ("protein", "butter chicken"),
            ("protein", "dal"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "roti"),
            ("protein", "mutton curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
    ],
    # ════════════════════════════════════════════════════════════════════════
    #  SOUTH ZONE — Kerala / Tamil Nadu / Karnataka / Andhra
    #  Breakfast: idli-sambar, dosa-chutney, pongal, upma, puttu
    #  Lunch: rice + sambar + rasam + poriyal + curd
    #  Dinner: idli/dosa/roti + dal (lighter)
    # ════════════════════════════════════════════════════════════════════════
    "south_breakfast": [
        [
            ("staple", "idli"),
            ("protein", "sambar"),
            ("accompaniment", "coconut chutney"),
            ("beverage", "coffee"),
        ],
        [
            ("staple", "dosa"),
            ("protein", "sambar"),
            ("accompaniment", "coconut chutney"),
            ("beverage", "coffee"),
        ],
        [("staple", "upma"), ("protein", "coconut chutney"), ("beverage", "coffee")],
        [
            ("staple", "pongal"),
            ("protein", "sambar"),
            ("accompaniment", "coconut chutney"),
            ("beverage", "coffee"),
        ],
        [("staple", "idiyappam"), ("protein", "coconut milk"), ("beverage", "tea")],
        [("staple", "puttu"), ("protein", "kadala curry"), ("beverage", "tea")],
        [("staple", "appam"), ("protein", "stew"), ("beverage", "tea")],
        [("staple", "bread"), ("protein", "egg"), ("beverage", "tea")],
        [
            ("staple", "rava idli"),
            ("protein", "sambar"),
            ("accompaniment", "chutney"),
            ("beverage", "coffee"),
        ],
    ],
    "south_lunch": [
        [
            ("staple", "rice"),
            ("protein", "sambar"),
            ("vegetable", "poriyal"),
            ("accompaniment", "rasam"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "rasam"),
            ("vegetable", "kootu"),
            ("accompaniment", "papad"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "rice"),
            ("protein", "fish curry"),
            ("vegetable", "thoran"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "rice"),
            ("protein", "avial"),
            ("vegetable", "poriyal"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "chicken curry"),
            ("vegetable", "poriyal"),
            ("accompaniment", "rasam"),
        ],
        [
            ("staple", "rice"),
            ("protein", "prawn curry"),
            ("vegetable", "thoran"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "rice"),
            ("protein", "egg curry"),
            ("vegetable", "poriyal"),
            ("accompaniment", "papad"),
        ],
    ],
    "south_lunch_weekend": [
        [
            ("staple", "chicken biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "mutton biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "fish biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "meals rice"),
            ("protein", "sambar"),
            ("vegetable", "poriyal"),
            ("accompaniment", "papad"),
            ("accompaniment", "payasam"),
        ],
    ],
    "south_dinner": [
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [("staple", "idli"), ("protein", "sambar"), ("accompaniment", "chutney")],
        [("staple", "dosa"), ("protein", "sambar"), ("accompaniment", "chutney")],
        [
            ("staple", "chapati"),
            ("protein", "egg curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "rice"),
            ("protein", "rasam"),
            ("vegetable", "poriyal"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
    ],
    "south_dinner_weekend": [
        [
            ("staple", "fried rice"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "parotta"),
            ("protein", "chicken curry"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "naan"),
            ("protein", "paneer"),
            ("protein", "dal"),
            ("accompaniment", "raita"),
        ],
    ],
    # ════════════════════════════════════════════════════════════════════════
    #  WEST ZONE — Maharashtrian / Gujarati / Goan
    #  Breakfast: poha, upma, thepla, dhokla, bread-butter
    #  Lunch: rice/roti + dal/sabzi + curd
    # ════════════════════════════════════════════════════════════════════════
    "west_breakfast": [
        [("staple", "poha"), ("protein", "peanuts"), ("beverage", "chai")],
        [("staple", "upma"), ("protein", "curd"), ("beverage", "chai")],
        [
            ("staple", "thepla"),
            ("protein", "curd"),
            ("accompaniment", "pickle"),
            ("beverage", "chai"),
        ],
        [
            ("staple", "dhokla"),
            ("accompaniment", "green chutney"),
            ("beverage", "chai"),
        ],
        [
            ("staple", "bread"),
            ("protein", "butter"),
            ("protein", "egg"),
            ("beverage", "chai"),
        ],
        [("staple", "bread"), ("protein", "omelette"), ("beverage", "chai")],
        [
            ("staple", "idli"),
            ("protein", "sambar"),
            ("accompaniment", "coconut chutney"),
            ("beverage", "coffee"),
        ],
        [("staple", "sabudana khichdi"), ("protein", "peanuts"), ("beverage", "chai")],
    ],
    "west_lunch": [
        [
            ("staple", "rice"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "rice"),
            ("protein", "fish curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "paneer"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "rice"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "chole"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
    ],
    "west_lunch_weekend": [
        [
            ("staple", "chicken biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "mutton biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [("staple", "pav bhaji"), ("protein", "butter"), ("accompaniment", "onion")],
    ],
    "west_dinner": [
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "egg curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "khichdi"),
            ("protein", "dal"),
            ("accompaniment", "papad"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "roti"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "roti"),
            ("protein", "fish curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
    ],
    "west_dinner_weekend": [
        [
            ("staple", "fried rice"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "naan"),
            ("protein", "paneer"),
            ("protein", "dal"),
            ("accompaniment", "raita"),
        ],
    ],
    # ════════════════════════════════════════════════════════════════════════
    #  CENTRAL ZONE — MP / Chhattisgarh
    # ════════════════════════════════════════════════════════════════════════
    "central_breakfast": [
        [("staple", "poha"), ("protein", "dahi"), ("beverage", "chai")],
        [
            ("staple", "paratha"),
            ("protein", "curd"),
            ("accompaniment", "pickle"),
            ("beverage", "chai"),
        ],
        [("staple", "bread"), ("protein", "egg"), ("beverage", "tea")],
        [("staple", "upma"), ("protein", "curd"), ("beverage", "chai")],
        [("staple", "idli"), ("protein", "sambar"), ("beverage", "coffee")],
    ],
    "central_lunch": [
        [
            ("staple", "rice"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "rice"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "paneer"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
    ],
    "central_lunch_weekend": [
        [
            ("staple", "chicken biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [("staple", "biryani"), ("accompaniment", "raita"), ("accompaniment", "salad")],
    ],
    "central_dinner": [
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "egg"),
            ("vegetable", "sabzi"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "khichdi"),
            ("protein", "dal"),
            ("accompaniment", "papad"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "roti"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
    ],
    "central_dinner_weekend": [
        [
            ("staple", "fried rice"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "naan"),
            ("protein", "paneer"),
            ("protein", "dal"),
            ("accompaniment", "raita"),
        ],
    ],
    # ════════════════════════════════════════════════════════════════════════
    #  GENERIC / PAN-INDIAN (any zone)
    # ════════════════════════════════════════════════════════════════════════
    "any_breakfast": [
        # Light Indian breakfasts — exactly how Indians eat in the morning
        [("staple", "poha"), ("protein", "dahi"), ("beverage", "chai")],
        [("staple", "upma"), ("protein", "coconut chutney"), ("beverage", "coffee")],
        [
            ("staple", "idli"),
            ("protein", "sambar"),
            ("accompaniment", "chutney"),
            ("beverage", "coffee"),
        ],
        [
            ("staple", "dosa"),
            ("protein", "sambar"),
            ("accompaniment", "chutney"),
            ("beverage", "coffee"),
        ],
        [
            ("staple", "paratha"),
            ("protein", "curd"),
            ("accompaniment", "pickle"),
            ("beverage", "chai"),
        ],
        [
            ("staple", "paratha"),
            ("protein", "aloo"),
            ("accompaniment", "pickle"),
            ("beverage", "chai"),
        ],
        [
            ("staple", "bread"),
            ("protein", "butter"),
            ("protein", "omelette"),
            ("beverage", "tea"),
        ],
        [
            ("staple", "bread"),
            ("protein", "egg"),
            ("protein", "butter"),
            ("beverage", "tea"),
        ],
        [("staple", "oats"), ("protein", "milk"), ("beverage", "tea")],
        [("staple", "daliya"), ("protein", "milk"), ("beverage", "tea")],
        [("staple", "puri"), ("protein", "aloo sabzi"), ("beverage", "chai")],
    ],
    "any_lunch": [
        # Substantial Indian lunches — rice or roti based
        [
            ("staple", "rice"),
            ("protein", "dal tadka"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
            ("beverage", "buttermilk"),
        ],
        [
            ("staple", "rice"),
            ("protein", "fish curry"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "rice"),
            ("protein", "chicken curry"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "rice"),
            ("protein", "egg curry"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "rajma"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "paneer"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "rice"),
            ("protein", "sambar"),
            ("vegetable", "poriyal"),
            ("accompaniment", "papad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "chole"),
            ("vegetable", "sabzi"),
            ("accompaniment", "onion salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "aloo gobi"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "rice"),
            ("protein", "mutton curry"),
            ("protein", "dal"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
    ],
    "any_lunch_weekend": [
        [
            ("staple", "chicken biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "kachumber"),
        ],
        [
            ("staple", "mutton biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "egg biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "veg biryani"),
            ("accompaniment", "raita"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "fried rice"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "chowmein"),
            ("protein", "chicken manchurian"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "chole bhature"),
            ("accompaniment", "onion"),
            ("accompaniment", "pickle"),
        ],
        [("staple", "pav bhaji"), ("protein", "butter"), ("accompaniment", "onion")],
    ],
    "any_dinner": [
        # Lighter than lunch — roti/chapati dominant
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "palak"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "egg bhurji"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "khichdi"),
            ("protein", "dal"),
            ("accompaniment", "papad"),
            ("accompaniment", "curd"),
        ],
        [
            ("staple", "roti"),
            ("protein", "paneer"),
            ("vegetable", "bhindi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "dal"),
            ("vegetable", "aloo sabzi"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "chapati"),
            ("protein", "chicken curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "roti"),
            ("protein", "fish curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "roti"),
            ("protein", "egg curry"),
            ("vegetable", "sabzi"),
            ("accompaniment", "pickle"),
        ],
    ],
    "any_dinner_weekend": [
        [
            ("staple", "fried rice"),
            ("protein", "chicken curry"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "chowmein"),
            ("protein", "chicken manchurian"),
            ("accompaniment", "salad"),
        ],
        [
            ("staple", "naan"),
            ("protein", "butter chicken"),
            ("protein", "dal"),
            ("accompaniment", "raita"),
        ],
        [
            ("staple", "paratha"),
            ("protein", "paneer"),
            ("accompaniment", "raita"),
            ("accompaniment", "pickle"),
        ],
        [
            ("staple", "luchi"),
            ("protein", "cholar dal"),
            ("protein", "aloo sabzi"),
            ("accompaniment", "salad"),
        ],
    ],
    # ════════════════════════════════════════════════════════════════════════
    #  SNACKS — very light, fruit/dry fruit dominant
    # ════════════════════════════════════════════════════════════════════════
    "mid_morning": [
        # Very light — fruit, dry fruits, fruit juice
        [("fruit", "banana"), ("beverage", "water")],
        [("fruit", "apple"), ("snack", "almonds")],
        [("fruit", "orange"), ("snack", "walnuts")],
        [("fruit", "guava"), ("beverage", "green tea")],
        [("snack", "makhana"), ("beverage", "green tea")],
        [("snack", "mixed nuts"), ("beverage", "coconut water")],
        [("fruit", "seasonal fruit"), ("beverage", "lemon water")],
        [("snack", "sprouts"), ("beverage", "lemon water")],
        [("fruit", "mango"), ("beverage", "water")],
        [("snack", "chana"), ("beverage", "buttermilk")],
        [("fruit", "pomegranate"), ("beverage", "green tea")],
        [("fruit", "papaya"), ("beverage", "water")],
    ],
    "afternoon": [
        [("snack", "samosa"), ("beverage", "chai")],
        [("snack", "bhel puri"), ("beverage", "chai")],
        [("snack", "dhokla"), ("accompaniment", "chutney"), ("beverage", "chai")],
        [("snack", "roasted chana"), ("beverage", "tea")],
        [("snack", "poha"), ("beverage", "chai")],
        [("snack", "pakora"), ("beverage", "chai")],
        [("snack", "makhana"), ("beverage", "green tea")],
        [("snack", "murukku"), ("beverage", "chai")],
        [("snack", "namkeen"), ("beverage", "chai")],
        [("snack", "mathri"), ("beverage", "chai")],
        [("fruit", "banana"), ("beverage", "green tea")],
        [("snack", "boiled egg"), ("beverage", "chai")],
    ],
    "evening_snack": [
        [("snack", "sprouts"), ("beverage", "lemon water")],
        [("snack", "makhana"), ("beverage", "green tea")],
        [("fruit", "apple"), ("beverage", "water")],
        [("snack", "roasted chana"), ("beverage", "buttermilk")],
        [("snack", "mixed nuts"), ("snack", "dates")],
        [("snack", "peanuts"), ("beverage", "chai")],
        [("snack", "yogurt"), ("snack", "nuts")],
        [("fruit", "banana"), ("beverage", "milk")],
        [("snack", "boiled egg"), ("beverage", "green tea")],
        [("fruit", "seasonal fruit"), ("beverage", "water")],
    ],
}


def _get_template_key(slot: str, zone: str, is_weekend: bool = False) -> str:
    """Get the best template key for a given slot and zone. Weekend gets special templates."""
    if is_weekend and slot in ("lunch", "dinner"):
        for wk in [f"{zone}_{slot}_weekend", f"any_{slot}_weekend"]:
            if wk in MEAL_TEMPLATES:
                return wk
    zone_slots = {
        "breakfast": f"{zone}_breakfast",
        "lunch": f"{zone}_lunch",
        "dinner": f"{zone}_dinner",
    }
    key = zone_slots.get(slot, slot)
    if key not in MEAL_TEMPLATES:
        key = f"any_{slot}" if f"any_{slot}" in MEAL_TEMPLATES else slot
    if key not in MEAL_TEMPLATES:
        key = "mid_morning" if slot in ("mid_morning",) else "afternoon"
    return key


def _find_food_by_kw(df, role, kw_fragments, used_today_ids, rng, fallback_any=True):
    """Find a food matching role + keyword, not already used today."""
    cands = df[df["meal_role"] == role].copy()
    if cands.empty:
        return None
    # Exclude used
    cands = cands[~cands["food_id"].isin(used_today_ids)]
    if cands.empty:
        cands = df[df["meal_role"] == role].copy()

    # Try keyword match
    kw_lower = kw_fragments.lower()
    kw_words = [w.strip() for w in kw_lower.split() if len(w.strip()) >= 3]
    name_col = cands["food_name"].str.lower()

    # Try exact phrase first
    mask = name_col.str.contains(kw_lower, na=False, regex=False)
    matched = cands[mask]

    # Try partial word match if no exact match
    if matched.empty and kw_words:
        for word in kw_words:
            m = cands[name_col.str.contains(word, na=False, regex=False)]
            if not m.empty:
                matched = m
                break

    pool = matched if not matched.empty else (cands if fallback_any else None)
    if pool is None or pool.empty:
        return None

    # Pick top scorer with some randomness
    if "_s" in pool.columns:
        top = pool.nlargest(min(8, len(pool)), "_s")
    else:
        top = pool.head(min(8, len(pool)))
    return top.iloc[rng.randint(0, len(top) - 1)]


def _build_slot_from_template(
    safe_df,
    slot,
    target_kcal,
    metrics,
    used_today,
    used_yesterday,
    rng,
    preferred_region="any",
    festive_mode=None,
    diet_pref=None,
    is_weekend=False,
):
    """
    Build a meal slot using template-based selection for coherent, realistic meals.
    Falls back to role-by-role if template match fails.
    """
    zone = preferred_region if preferred_region and preferred_region != "any" else "any"
    template_key = _get_template_key(slot, zone, is_weekend=is_weekend)
    templates = MEAL_TEMPLATES.get(template_key, MEAL_TEMPLATES.get(f"any_{slot}", []))

    # Also try generic templates as fallback pool
    generic_key = f"any_{slot}"
    if generic_key in MEAL_TEMPLATES and generic_key != template_key:
        templates = templates + MEAL_TEMPLATES[generic_key]

    # Score each template by how well we can fill it from the food DB
    used_today_ids = set(used_today.keys())

    # Pre-score all foods once for efficiency
    safe_df = safe_df.copy()
    safe_df["_s"] = safe_df.apply(
        lambda r: _score(
            r, slot, metrics, used_yesterday, preferred_region, diet_pref=diet_pref
        ),
        axis=1,
    )

    # Shuffle and try templates
    template_indices = list(range(len(templates)))
    rng.shuffle(template_indices)

    best_items = []
    best_coverage = 0

    for ti in template_indices[:6]:  # Try up to 6 templates
        template = templates[ti]
        items_try = []
        coverage = 0
        local_used = set(used_today_ids)

        for role, kw in template:
            food = _find_food_by_kw(safe_df, role, kw, local_used, rng)
            if food is not None:
                coverage += 1
                local_used.add(food["food_id"])
                items_try.append((role, food))
            else:
                # Fallback: any food of this role
                cands = safe_df[
                    (safe_df["meal_role"] == role)
                    & (~safe_df["food_id"].isin(local_used))
                ]
                if not cands.empty:
                    top = cands.nlargest(min(5, len(cands)), "_s")
                    food = top.iloc[rng.randint(0, len(top) - 1)]
                    coverage += 0.5  # partial credit
                    local_used.add(food["food_id"])
                    items_try.append((role, food))

        if coverage > best_coverage:
            best_coverage = coverage
            best_items = items_try
        if best_coverage >= len(template) * 0.8:
            break  # Good enough

    if not best_items:
        return None  # Caller will fallback to role-by-role

    # Calculate calorie targets per role
    cal_pcts = SLOT_CAL_PCT.get(slot, {})
    if not cal_pcts:
        n = len(best_items)
        cal_pcts = {role: 1.0 / n for role, _ in best_items}

    items = []
    for role, food in best_items:
        role_kcal = target_kcal * cal_pcts.get(
            role, target_kcal / max(len(best_items), 1) / target_kcal
        )
        it = _item(food, role_kcal, _role_label(role, slot))
        items.append(it)
        used_today[food["food_id"]] = used_today.get(food["food_id"], 0) + 1

    return items


def _role_label(role, slot):
    labels = {
        "staple": "मुख्य / Main",
        "protein": (
            "दाल/करी / Dal-Curry" if slot in ("lunch", "dinner") else "साथ / Side"
        ),
        "vegetable": "सब्जी / Sabzi",
        "accompaniment": "साइड / Side",
        "beverage": "पेय / Drink",
        "fruit": "फल / Fruit",
        "snack": "नाश्ता / Snack",
    }
    return labels.get(role, role)


# ─────────────────────────────────────────────────────────────────────────────
#  SERVING SIZE
# ─────────────────────────────────────────────────────────────────────────────


def _calc_serving(row, target_kcal):
    unit = str(row.get("serving_unit", "gram"))
    piece_g = float(row.get("piece_weight_g", 100))
    cal100 = max(float(row.get("calories_per_100g", 50)), 1)

    if unit == "gram":
        raw = target_kcal * 100 / cal100
        portion_g = max(30, min(round(raw / 5) * 5, 450))
        food_kcal = cal100 * portion_g / 100
        return portion_g, round(food_kcal, 1), f"{portion_g:.0f}g", f"{portion_g:.0f}g"

    kcal_per = cal100 * piece_g / 100
    if kcal_per <= 0:
        kcal_per = 50
    n = max(1, round(target_kcal / kcal_per))
    caps = {"piece": 4, "bowl": 2, "glass": 2, "cup": 2, "katori": 2, "plate": 1}
    n = min(n, caps.get(unit, 3))
    portion_g = piece_g * n
    food_kcal = cal100 * portion_g / 100
    hu = UNIT_HINDI.get(unit, unit)
    pl = "s" if n > 1 and unit in ("piece", "bowl", "glass", "cup") else ""
    return (
        portion_g,
        round(food_kcal, 1),
        f"{n} {unit}{pl}",
        f"{n} {hu} ({portion_g:.0f}g)",
    )


# ─────────────────────────────────────────────────────────────────────────────
#  SCORING
# ─────────────────────────────────────────────────────────────────────────────


def _score(
    row,
    slot,
    metrics,
    used_yesterday,
    preferred_region=None,
    cuisine_hint=None,
    diet_pref=None,
    **kwargs,
):
    """
    Improved scoring function (v2).

    Architecture: three separate budget pools that are combined at the end,
    keeping each concern bounded and preventing one signal from drowning others.

      Pool A – nutritional quality   (0-50 pts)  — disease_score mapped + GI/fiber/sodium
      Pool B – goal alignment        (0-20 pts)  — protein density, calorie fit for goal
      Pool C – contextual fit        (0-30 pts)  — slot timing, region, cuisine, variety

    Final score = A + B + C, range 0-100.
    Softmax temperature in the caller then handles the probabilistic selection.
    """
    import math

    gi = float(row.get("glycemic_index", 0))
    fiber = float(row.get("fiber_g", 0))
    prot = float(row.get("protein_g", 0))
    sodium = float(row.get("sodium_mg", 0))
    cal100 = float(row.get("calories_per_100g", 100))
    sat_fat = float(row.get("saturated_fat_g", 0))
    meal_type = str(row.get("meal_type", "")).lower()
    goal = getattr(metrics, "goal", "maintain")

    # ── Pool A: Nutritional quality (0-50) ───────────────────────────────────
    # disease_score is already a normalized 0-100 from DiseaseFoodFilter.
    # We map it to 0-25 as the disease-suitability sub-score.
    disease_raw = float(row.get("disease_score", 50))
    disease_sub = (disease_raw / 100.0) * 25.0  # 0-25

    # GI sub-score (0-12): low GI is better; unknown(0) is mildly negative
    if gi == 0:
        gi_sub = 4.0  # unknown — neutral-negative
    elif gi <= 40:
        gi_sub = 12.0
    elif gi <= 55:
        gi_sub = 9.0
    elif gi <= 70:
        gi_sub = 5.0
    else:
        gi_sub = 0.0  # high GI

    # Fiber sub-score (0-7): linear up to 10g/100g → full marks
    fiber_sub = min(7.0, (fiber / 10.0) * 7.0)

    # Sodium penalty (0-6 deducted from 6): smooth curve
    if sodium == 0:
        sodium_sub = 6.0
    else:
        # 0mg → 6, 800mg → 0, linear; cap at 0
        sodium_sub = max(0.0, 6.0 * (1.0 - sodium / 800.0))

    pool_A = min(50.0, disease_sub + gi_sub + fiber_sub + sodium_sub)

    # ── Pool B: Goal alignment (0-20) ────────────────────────────────────────
    pool_B = 0.0

    if goal in ("weight_loss", "weight_loss_aggressive", "muscle_gain"):
        # Protein density bonus: sigmoid-like, saturates at ~30g/100g
        pool_B += min(10.0, (prot / 30.0) * 10.0)
        # Calorie penalty for weight loss: >350 kcal/100g is dense
        if goal in ("weight_loss", "weight_loss_aggressive"):
            pool_B += max(0.0, 5.0 * (1.0 - max(0, cal100 - 200) / 300.0))
        else:
            pool_B += 5.0  # muscle_gain: calorie density neutral

    elif goal in ("weight_gain", "weight_gain_mild"):
        # Calorie density bonus: higher kcal/100g = better for bulking
        pool_B += min(10.0, (cal100 / 400.0) * 10.0)
        # Protein bonus (secondary for gain)
        pool_B += min(5.0, (prot / 20.0) * 5.0)
        pool_B += 5.0  # base bonus for calorie-dense foods (already filtered safe)

    else:  # maintain
        # Balanced: moderate protein, moderate calories
        pool_B += min(7.0, (prot / 20.0) * 7.0)
        cal_ideal = 150  # per 100g
        pool_B += max(0.0, 8.0 - abs(cal100 - cal_ideal) / 30.0)

    pool_B = max(0.0, min(20.0, pool_B))

    # Snack slot: penalise high-calorie items
    if slot in ("mid_morning", "afternoon", "evening_snack") and cal100 > 400:
        pool_B = max(0.0, pool_B - 8.0)

    # ── Pool C: Contextual fit (0-30) ────────────────────────────────────────
    pool_C = 0.0

    # Meal-slot timing (0-12) — penalise mismatches strongly
    if slot == "breakfast":
        if "breakfast" in meal_type:
            pool_C += 12.0
        elif "snack" in meal_type:
            pool_C += 6.0
        elif "lunch_dinner" in meal_type and "breakfast" not in meal_type:
            pool_C += 0.0  # heavy mains at breakfast — no points
        else:
            pool_C += 4.0  # neutral / multi-type
    elif slot in ("lunch", "dinner"):
        if "lunch_dinner" in meal_type:
            pool_C += 12.0
        elif "breakfast" in meal_type and "lunch_dinner" not in meal_type:
            pool_C += 2.0  # light breakfast items at main meal — minor penalty
        else:
            pool_C += 5.0
    elif slot in ("mid_morning", "afternoon", "evening_snack"):
        if "snack" in meal_type or "snacks" in meal_type:
            pool_C += 12.0
        elif "breakfast" in meal_type:
            pool_C += 7.0
        else:
            pool_C += 3.0

    # Regional preference (0-10)
    if preferred_region and preferred_region != "any":
        food_region = str(row.get("region_zone", "pan_indian"))
        if food_region == preferred_region:
            pool_C += 10.0
        elif food_region == "pan_indian":
            pool_C += 4.0
        # else: 0 (wrong region)
    else:
        pool_C += 4.0  # 'any' region — mild bonus to pan-indian neutrality

    # Cuisine coherence (0-8)
    if cuisine_hint:
        ct = str(row.get("cuisine_type", ""))
        if ct == cuisine_hint:
            pool_C += 8.0
        elif ct in ("Indian", "Pan-Indian"):
            pool_C += 2.0

    # Variety: penalise recently used foods (0 or -5 equivalent mapped to no points)
    if row["food_id"] in used_yesterday:
        pool_C = max(0.0, pool_C - 6.0)

    # Diet preference signal (0-6) — kept proportional, not dominant
    if not diet_pref or diet_pref in ("none", ""):
        is_veg = row.get("is_vegetarian", True)
        cat = str(row.get("category", "")).lower()
        fn = str(row.get("food_name", "")).lower()
        non_veg_kw = (
            "chicken",
            "mutton",
            "fish",
            "prawn",
            "egg",
            "keema",
            "crab",
            "omelette",
            "bhurji",
        )
        if is_veg is False or str(is_veg).lower() == "false":
            pool_C += 4.0
        if cat in ("meat dishes", "seafood", "egg dishes"):
            pool_C += 1.5
        if any(k in fn for k in non_veg_kw):
            pool_C += 0.5

    pool_C = max(0.0, min(30.0, pool_C))

    total = pool_A + pool_B + pool_C
    return max(round(total, 2), 1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  PICK ONE FOOD
# ─────────────────────────────────────────────────────────────────────────────


def _pick(
    safe_df,
    role,
    slot,
    metrics,
    used_today,
    used_yesterday,
    rng,
    preferred_region=None,
    cuisine_hint=None,
    kw_boost=None,
    diet_pref=None,
    temperature=12.0,
):
    # Exclude foods already used today
    exhausted = {fid for fid, cnt in used_today.items() if cnt >= 1}
    roles_to_try = [role] + ROLE_FALLBACKS.get(role, [])

    for try_role in roles_to_try:
        cands = safe_df[
            (safe_df["meal_role"] == try_role) & (~safe_df["food_id"].isin(exhausted))
        ].copy()
        if cands.empty:
            # Allow reuse if no other options
            cands = safe_df[safe_df["meal_role"] == try_role].copy()
        if cands.empty:
            continue

        # Keyword boost: narrow to relevant foods first
        if kw_boost:
            kw_mask = (
                cands["food_name"]
                .str.lower()
                .apply(lambda n: any(k.lower() in n for k in kw_boost))
            )
            boosted = cands[kw_mask]
            if len(boosted) >= 2:
                cands = boosted

        cands = cands.copy()
        cands["_s"] = cands.apply(
            lambda r: _score(
                r, slot, metrics, used_yesterday, preferred_region, cuisine_hint
            ),
            axis=1,
        )
        # Use top 30 candidates with weighted random selection for variety
        pool = cands.nlargest(min(30, len(cands)), "_s")
        # Apply softmax-like temperature to scores for better diversity
        scores = pool["_s"].values
        # Temperature scaling: lower temp = more deterministic, higher = more random
        temp = temperature
        scaled = scores / temp
        scaled = scaled - scaled.max()  # numerical stability
        import math

        exp_s = [math.exp(s) for s in scaled]
        total = sum(exp_s)
        weights = [e / total for e in exp_s]

        try:
            idx = rng.choices(range(len(pool)), weights=weights, k=1)[0]
            chosen = pool.iloc[idx]
        except Exception:
            if pool.empty:
                continue
            chosen = pool.iloc[0]

        used_today[chosen["food_id"]] = used_today.get(chosen["food_id"], 0) + 1
        return chosen

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD ITEM DICT
# ─────────────────────────────────────────────────────────────────────────────


def _item(row, target_kcal, slot_label):
    portion_g, food_kcal, qty_d, qty_l = _calc_serving(row, target_kcal)
    f = portion_g / 100.0
    raw_h = row.get("food_name_hindi", "")
    hindi = (
        ""
        if (not raw_h or str(raw_h).strip().lower() in ("nan", "none", ""))
        else str(raw_h).strip()
    )
    bilin = f"{row['food_name']} / {hindi}" if hindi else row["food_name"]
    return {
        "food_id": row["food_id"],
        "food_name": row["food_name"],
        "food_name_hindi": hindi,
        "food_name_bilingual": bilin,
        "category": row.get("category", ""),
        "cuisine_type": row.get("cuisine_type", ""),
        "meal_role": row.get("meal_role", "other"),
        "slot_label": slot_label,
        "serving_unit": str(row.get("serving_unit", "gram")),
        "piece_weight_g": float(row.get("piece_weight_g", 100)),
        "qty_display": qty_d,
        "qty_label": qty_l,
        "portion_g": round(portion_g, 0),
        "calories": round(food_kcal, 1),
        "protein_g": round(float(row.get("protein_g", 0)) * f, 1),
        "carbs_g": round(float(row.get("carbs_g", 0)) * f, 1),
        "fat_g": round(float(row.get("fat_g", 0)) * f, 1),
        "fiber_g": round(float(row.get("fiber_g", 0)) * f, 1),
        "sodium_mg": round(float(row.get("sodium_mg", 0)) * f, 1),
        "disease_score": float(row.get("disease_score", 50)),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD ONE SLOT
# ─────────────────────────────────────────────────────────────────────────────

# Diet-specific non-veg keywords to exclude from templates
_NONVEG_KEYWORDS = [
    "chicken",
    "mutton",
    "lamb",
    "goat",
    "beef",
    "pork",
    "fish",
    "prawn",
    "shrimp",
    "crab",
    "lobster",
    "squid",
    "octopus",
    "egg",
    "keema",
    "kheema",
    "haleem",
    "nihari",
    "roganjosh",
    "seekh",
    "tandoori chicken",
    "chicken curry",
    "fish curry",
    "kosha mangsho",
    "shorshe ilish",
    "chingri",
    "crab curry",
    "macher",
    "ilish",
    "hilsa",
    "rohu",
    "katla",
    "bekti",
    "pomfret",
    "surmai",
    "bombil",
    "kingfish",
    "mackerel",
    "sardine",
]
_VEG_PROTEIN_KW = [
    "dal",
    "daal",
    "lentil",
    "rajma",
    "chole",
    "chana",
    "paneer",
    "tofu",
    "soya",
    "moong",
    "masoor",
    "arhar",
    "toor",
    "urad",
    "kadhi",
    "sambar",
    "rasam",
    "kootu",
    "dalma",
    "cholar",
    "mung",
    "matki",
    "lobiya",
    "black-eyed pea",
]
_VEGAN_EXCLUDE_KW = [
    "milk",
    "dahi",
    "curd",
    "yogurt",
    "paneer",
    "ghee",
    "butter",
    "cream",
    "cheese",
    "lassi",
    "buttermilk",
    "chaas",
    "kheer",
    "payasam",
    "raita",
    "mishti doi",
    "sheer khurma",
    "halwa with milk",
    "egg",
    "omelette",
    "bhurji",
]
_JAIN_EXCLUDE_KW = [
    "potato",
    "aloo",
    "carrot",
    "gajar",
    "beet",
    "radish",
    "mooli",
    "turnip",
    "yam",
    "arbi",
    "sweet potato",
    "shakarkand",
    "onion",
    "pyaaz",
    "garlic",
    "lahasun",
    "leek",
    "shallot",
    "spring onion",
    "chicken",
    "mutton",
    "fish",
    "egg",
    "beef",
    "pork",
    "prawn",
    "shrimp",
    "meat",
    "keema",
]
_HALAL_EXCLUDE_KW = [
    "pork",
    "bacon",
    "ham",
    "sausage",
    "lard",
    "pepperoni",
    "prosciutto",
    "alcohol",
    "wine",
    "beer",
    "rum cake",
    "pork ribs",
]


def _filter_templates_by_diet(templates, diet_pref):
    """Filter meal templates to only include diet-appropriate combinations."""
    if not diet_pref or diet_pref in ("none", ""):
        return templates

    dp = diet_pref.lower()
    filtered = []

    for template in templates:
        ok = True
        for role, kw in template:
            kw_lower = kw.lower()
            if dp in ("vegetarian", "vegan", "jain"):
                # Exclude any template containing non-veg keyword
                if any(nv in kw_lower for nv in _NONVEG_KEYWORDS if len(nv) > 3):
                    ok = False
                    break
            if dp == "vegan":
                # Also exclude dairy
                if any(vx in kw_lower for vx in _VEGAN_EXCLUDE_KW if len(vx) > 3):
                    ok = False
                    break
            if dp == "jain":
                # Exclude roots and non-veg
                if any(jx in kw_lower for jx in _JAIN_EXCLUDE_KW if len(jx) > 3):
                    ok = False
                    break
            if dp == "halal":
                if any(hx in kw_lower for hx in _HALAL_EXCLUDE_KW if len(hx) > 3):
                    ok = False
                    break
        if ok:
            filtered.append(template)

    # If all templates filtered out, return safe generic templates
    if not filtered:
        return templates  # fallback to original; safe_df already filtered by dislike pipeline
    return filtered


def _build_slot(
    safe_df,
    slot,
    target_kcal,
    metrics,
    used_today,
    used_yesterday,
    rng,
    preferred_region=None,
    diet_pref=None,
    used_food_names_today=None,
    heavy_used_today=None,
    is_weekend=False,
    temperature=12.0,
):
    """
    Build one meal slot using TEMPLATE-FIRST approach for realistic Indian meal combos.
    Falls back to role-by-role only when no template matches the food DB.
    """
    used_food_names_today = used_food_names_today or set()
    heavy_used_today = heavy_used_today or set()
    zone = preferred_region if preferred_region and preferred_region != "any" else "any"

    # ── Pre-filter: remove foods used today + heavy items already used ────────
    def _not_repeat(row):
        fn = row["food_name"].lower()
        if fn in used_food_names_today:
            return False
        for hkw in _HEAVY_ONCE_PER_DAY:
            if hkw in fn and hkw in heavy_used_today:
                return False
        return True

    if used_food_names_today:
        name_mask = (
            safe_df["food_name"]
            .str.lower()
            .apply(lambda n: n not in used_food_names_today)
        )
        heavy_mask = (
            safe_df["food_name"]
            .str.lower()
            .apply(
                lambda n: not any(
                    hkw in n and hkw in heavy_used_today for hkw in _HEAVY_ONCE_PER_DAY
                )
            )
        )
        filtered = safe_df[name_mask & heavy_mask]
        if len(filtered) >= 20:
            safe_df = filtered

    # ── Score all foods once ─────────────────────────────────────────────────
    safe_df = safe_df.copy()
    safe_df["_s"] = safe_df.apply(
        lambda r: _score(
            r, slot, metrics, used_yesterday, preferred_region, diet_pref=diet_pref
        ),
        axis=1,
    )

    # ── Try template-based building ──────────────────────────────────────────
    template_key = _get_template_key(slot, zone, is_weekend=is_weekend)
    templates = MEAL_TEMPLATES.get(template_key, [])

    # Merge with generic templates as fallback pool
    generic_key = f"any_{slot}"
    if is_weekend and slot in ("lunch", "dinner"):
        generic_key = f"any_{slot}_weekend"
    extra = MEAL_TEMPLATES.get(generic_key, MEAL_TEMPLATES.get(f"any_{slot}", []))
    if extra and generic_key != template_key:
        templates = templates + extra

    # Filter templates by diet preference
    templates = _filter_templates_by_diet(templates, diet_pref)

    used_today_ids = set(used_today.keys())
    rng.shuffle(templates)

    best_items = []
    best_coverage = 0

    for tmpl in templates[:8]:
        items_try = []
        coverage = 0
        local_used = set(used_today_ids)

        for role, kw in tmpl:
            food = _find_food_by_kw(safe_df, role, kw, local_used, rng)
            if food is not None:
                coverage += 1
                local_used.add(food["food_id"])
                items_try.append((role, food))
            else:
                # Fallback: best-scoring food for this role not yet used
                cands = safe_df[
                    (safe_df["meal_role"] == role)
                    & (~safe_df["food_id"].isin(local_used))
                ]
                if not cands.empty:
                    top = cands.nlargest(min(5, len(cands)), "_s")
                    food = top.iloc[rng.randint(0, len(top) - 1)]
                    coverage += 0.4
                    local_used.add(food["food_id"])
                    items_try.append((role, food))

        if coverage > best_coverage:
            best_coverage = coverage
            best_items = items_try
        if best_coverage >= len(tmpl) * 0.85:
            break

    # ── Convert matched foods to item dicts ──────────────────────────────────
    if best_items:
        cal_pcts = SLOT_CAL_PCT.get(slot, {})
        n = len(best_items)
        if not cal_pcts:
            cal_pcts = {role: 1.0 / n for role, _ in best_items}

        items = []
        for role, food in best_items:
            role_kcal = target_kcal * cal_pcts.get(role, 1.0 / n)
            it = _item(food, role_kcal, _role_label(role, slot))
            items.append(it)
            used_today[food["food_id"]] = used_today.get(food["food_id"], 0) + 1

    else:
        # ── Hard fallback: role-by-role picking ──────────────────────────────
        structure = SLOT_STRUCTURE.get(slot, ["snack", "beverage"])
        cal_pcts = SLOT_CAL_PCT.get(slot, {r: 1 / len(structure) for r in structure})
        items = []
        for role in structure:
            role_kcal = target_kcal * cal_pcts.get(role, 0.25)
            chosen = _pick(
                safe_df,
                role,
                slot,
                metrics,
                used_today,
                used_yesterday,
                rng,
                preferred_region=preferred_region,
                diet_pref=diet_pref,
                temperature=temperature,
            )
            if chosen is not None:
                items.append(_item(chosen, role_kcal, _role_label(role, slot)))

    # ── Rule: No desserts at breakfast ───────────────────────────────────────
    if slot == "breakfast":
        DESSERT_CATS = {"desserts & sweets", "sweets", "mithai", "dessert"}
        DESSERT_KWS = (
            "kheer",
            "halwa",
            "barfi",
            "ladoo",
            "jalebi",
            "gulab jamun",
            "rasgulla",
            "cake",
            "cookie",
        )
        items = [
            it
            for it in items
            if str(it.get("category", "")).lower() not in DESSERT_CATS
            and not any(kw in it["food_name"].lower() for kw in DESSERT_KWS)
        ]

    # ── Rule: Enforce protein for rice/roti at lunch/dinner ──────────────────
    if slot in ("lunch", "dinner"):
        has_protein = any(it.get("meal_role") == "protein" for it in items)
        has_main_staple = any(
            any(
                s in it["food_name"].lower()
                for s in ("rice", "roti", "chapati", "naan", "paratha", "bread")
            )
            for it in items
            if it.get("meal_role") == "staple"
        )
        if has_main_staple and not has_protein:
            kws = (
                ["dal", "daal", "lentil", "sambar", "curry", "chicken", "fish", "egg"]
                if not diet_pref or diet_pref in ("none", "halal", "")
                else ["dal", "daal", "lentil", "sambar", "curry", "paneer"]
            )
            forced = _pick(
                safe_df,
                "protein",
                slot,
                metrics,
                used_today,
                used_yesterday,
                rng,
                preferred_region=preferred_region,
                kw_boost=kws,
                diet_pref=diet_pref,
            )
            if forced is not None:
                items.append(
                    _item(forced, target_kcal * 0.28, _role_label("protein", slot))
                )

    totals = {
        k: round(sum(i[k] for i in items), 1)
        for k in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg"]
    }

    parts = []
    for it in items:
        if it["serving_unit"] != "gram":
            parts.append(f"{it['qty_display']} {it['food_name']}")
        else:
            parts.append(f"{it['food_name']} ({it['qty_display']})")

    return {
        "slot_label": slot.replace("_", " ").title(),
        "target_kcal": round(target_kcal, 0),
        "actual_kcal": totals["calories"],
        "meal_description": " + ".join(parts),
        "foods": items,
        "totals": totals,
    }


def _role_label(role, slot):
    labels = {
        "staple": "मुख्य / Main",
        "protein": (
            "दाल/करी / Dal-Curry" if slot in ("lunch", "dinner") else "साथ / Side"
        ),
        "vegetable": "सब्जी / Sabzi",
        "accompaniment": "साइड / Side",
        "beverage": "पेय / Drink",
        "fruit": "फल / Fruit",
        "snack": "नाश्ता / Snack",
    }
    return labels.get(role, role)


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD DAILY / WEEKLY PLAN
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
#  FESTIVE / SEASONAL MODE
# ─────────────────────────────────────────────────────────────────────────────

import datetime as _dt

FESTIVE_BOOST_FOODS = {
    # keyword fragments → boost score
    "diwali": [
        "kheer",
        "halwa",
        "besan ladoo",
        "kaju katli",
        "mathri",
        "chakli",
        "gulab jamun",
        "barfi",
        "gujiya",
        "puri",
        "paneer",
    ],
    "holi": ["gujiya", "thandai", "malpua", "puran poli", "dahi vada", "namak pare"],
    "eid": ["biryani", "haleem", "sheer khurma", "sewai", "kebab", "korma", "nihari"],
    "navratri": [
        "kuttu",
        "singhara",
        "sabudana",
        "rajgira",
        "samak rice",
        "sendha namak",
        "makhana",
        "arbi",
        "sweet potato",
        "lauki",
    ],
    "onam": ["avial", "olan", "erissery", "payasam", "kaalan", "pachadi", "rice"],
    "pongal": ["pongal", "sakkarai pongal", "chakkara", "rice", "sesame"],
    "durga_puja": [
        "hilsa",
        "kosha mangsho",
        "cholar dal",
        "luchi",
        "mishti doi",
        "payesh",
        "begun bhaja",
        "aloo posto",
        "sandesh",
        "rosogolla",
    ],
    "christmas": [
        "plum cake",
        "mince pie",
        "roast",
        "mulled",
        "gingerbread",
        "chicken",
    ],
    "ganesh": ["modak", "ukadiche modak", "puran poli", "panchamrit", "coconut"],
}

SEASONAL_FOODS = {
    "winter": [
        "sarson ka saag",
        "makki ki roti",
        "gajar halwa",
        "til",
        "peanut",
        "peas",
        "methi",
        "spinach",
        "amla",
        "mustard",
        "bajra",
        "jaggery",
    ],
    "summer": [
        "mango",
        "watermelon",
        "kokum",
        "aam panna",
        "lassi",
        "curd",
        "sattu",
        "cucumber",
        "mint",
        "coconut water",
        "thandai",
        "bel sharbat",
    ],
    "monsoon": [
        "corn",
        "pakora",
        "bhutta",
        "chai",
        "hot soup",
        "dal",
        "kadhi",
        "ginger",
        "turmeric",
        "samosa",
        "vada",
    ],
    "autumn": [
        "kaddu",
        "kathal",
        "arbi",
        "sweet potato",
        "chestnut",
        "pomegranate",
        "dates",
        "fig",
        "almond",
    ],
}


def _get_season():
    month = _dt.datetime.now().month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "summer"
    if month in (6, 7, 8, 9):
        return "monsoon"
    return "autumn"


def apply_festive_seasonal_boost(df, festive_mode=None):
    """Boost disease_score for festive or seasonal foods."""
    df = df.copy()
    season = _get_season()
    seasonal_kws = SEASONAL_FOODS.get(season, [])
    if seasonal_kws:
        mask = (
            df["food_name"]
            .str.lower()
            .apply(lambda n: any(k.lower() in n for k in seasonal_kws))
        )
        df.loc[mask, "disease_score"] = (df.loc[mask, "disease_score"] + 15).clip(
            upper=100
        )

    if festive_mode and festive_mode.lower() in FESTIVE_BOOST_FOODS:
        fest_kws = FESTIVE_BOOST_FOODS[festive_mode.lower()]
        fest_mask = (
            df["food_name"]
            .str.lower()
            .apply(lambda n: any(k.lower() in n for k in fest_kws))
        )
        df.loc[fest_mask, "disease_score"] = (
            df.loc[fest_mask, "disease_score"] + 30
        ).clip(upper=100)
    return df


# Heavy items that should appear at most ONCE per day across all slots
_HEAVY_ONCE_PER_DAY = [
    "biryani",
    "pulao",
    "tehri",
    "dum",  # one-pot rice dishes
    "puri",
    "bhatura",
    "paratha",
    "luchi",  # fried/heavy breads (max once)
    "haleem",
    "nihari",
    "korma",  # heavy gravies
]
# Items that must NEVER appear in dinner if already had at lunch (very heavy)
_NO_REPEAT_LUNCH_DINNER = [
    "biryani",
    "haleem",
    "nihari",
    "puri",
    "bhatura",
]


def build_daily_plan(
    safe_df,
    metrics,
    day_num,
    used_yesterday=None,
    seed=42,
    preferred_region=None,
    festive_mode=None,
    diet_pref=None,
    temperature=12.0,
):
    rng = random.Random(seed + day_num * 997)
    used_today = {}
    used_yesterday = used_yesterday or set()
    meals = {}
    day_totals = {
        k: 0
        for k in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg"]
    }
    # Track food names used per day to prevent cross-slot repeats
    used_food_names_today = set()
    # Track which heavy-once items have already appeared today
    heavy_used_today = set()

    # Apply festive/seasonal boost to food scores
    boosted_df = apply_festive_seasonal_boost(safe_df, festive_mode=festive_mode)

    is_weekend = day_num in (6, 7)

    for slot, target_kcal in metrics.meal_calories.items():
        meal = _build_slot(
            boosted_df,
            slot,
            target_kcal,
            metrics,
            used_today,
            used_yesterday,
            rng,
            preferred_region,
            diet_pref=diet_pref,
            used_food_names_today=used_food_names_today,
            heavy_used_today=heavy_used_today,
            is_weekend=is_weekend,
            temperature=temperature,
        )
        meals[slot] = meal
        # Record food names used in this slot
        for f in meal["foods"]:
            fn = f["food_name"].lower()
            used_food_names_today.add(fn)
            for hkw in _HEAVY_ONCE_PER_DAY:
                if hkw in fn:
                    heavy_used_today.add(hkw)
        for k in day_totals:
            day_totals[k] += meal["totals"].get(k, 0)

    return {
        "day": day_num,
        "meals": meals,
        "totals": {k: round(v, 1) for k, v in day_totals.items()},
        "targets": {
            "calories": metrics.target_calories,
            "protein_g": metrics.protein_g,
            "carbs_g": metrics.carbs_g,
            "fat_g": metrics.fat_g,
            "fiber_g": metrics.fiber_g,
            "sodium_mg": metrics.sodium_mg,
        },
    }


def build_weekly_plan(
    safe_df,
    metrics,
    seed=42,
    preferred_region=None,
    festive_mode=None,
    diet_pref=None,
    temperature=12.0,
):
    DAYS = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    weekly = []
    used_yesterday = set()
    for i, day in enumerate(DAYS):
        day_seed = seed + i * 1009 + (hash(day) % 997)
        plan = build_daily_plan(
            safe_df,
            metrics,
            day_num=i + 1,
            used_yesterday=used_yesterday,
            seed=day_seed,
            preferred_region=preferred_region,
            festive_mode=festive_mode,
            diet_pref=diet_pref,
            temperature=temperature,
        )
        plan["day_name"] = day
        used_yesterday = {
            f["food_id"] for m in plan["meals"].values() for f in m["foods"]
        }
        weekly.append(plan)
    return weekly


def check_nutritional_gaps(daily_plan, metrics):
    t, tg = daily_plan["totals"], daily_plan["targets"]
    checks = [
        ("Calories", "calories", tg["calories"], 80, "kcal"),
        ("Protein", "protein_g", tg["protein_g"], 12, "g"),
        ("Carbs", "carbs_g", tg["carbs_g"], 20, "g"),
        ("Fat", "fat_g", tg["fat_g"], 8, "g"),
        ("Fiber", "fiber_g", tg["fiber_g"], 6, "g"),
        ("Sodium", "sodium_mg", tg["sodium_mg"], 350, "mg"),
    ]
    warnings = []
    for name, key, target, tol, unit in checks:
        if target <= 0:
            continue
        actual = t.get(key, 0)
        diff = actual - target
        if abs(diff) > tol:
            direction = "above" if diff > 0 else "below"
            warnings.append(
                f"{name}: {actual:.0f}{unit} ({direction} target {target:.0f}{unit} by {abs(diff):.0f}{unit})"
            )
    return warnings


def filter_by_region(safe_df, region_zone):
    if not region_zone or region_zone in ("any", ""):
        return safe_df
    zone_key = region_zone.lower().strip()
    cuisines = ZONE_CUISINES.get(zone_key, [])
    excludes = ZONE_EXCLUDE.get(zone_key, [])
    if not cuisines:
        return safe_df
    df = safe_df.copy()
    zone_mask = df.get("region_zone", pd.Series(dtype=str)) == zone_key
    cuisine_mask = df["cuisine_type"].isin(cuisines)
    regional = zone_mask | cuisine_mask
    # Hard-exclude cuisines that definitely don't belong to this zone
    # BUT keep pan-Indian/generic foods so we always have enough variety
    exclude_mask = df["cuisine_type"].isin(excludes)
    generic_mask = df["cuisine_type"].isin(
        [
            "Indian",
            "Pan-Indian",
            "Continental",
            "Western",
            "Asian",
            "Chinese",
            "Italian",
            "Fusion",
        ]
    )
    # Drop hard-excluded non-generic foods entirely from the regional pool
    # Only remove if there are enough regional foods remaining
    strict_exclude = exclude_mask & ~generic_mask
    regional_count = regional.sum()
    if regional_count >= 40:
        df = df[~strict_exclude].copy()
        # Recompute masks after drop
        zone_mask = df.get("region_zone", pd.Series(dtype=str)) == zone_key
        cuisine_mask = df["cuisine_type"].isin(cuisines)
        regional = zone_mask | cuisine_mask
        generic_mask = df["cuisine_type"].isin(
            [
                "Indian",
                "Pan-Indian",
                "Continental",
                "Western",
                "Asian",
                "Chinese",
                "Italian",
                "Fusion",
            ]
        )
    # Boost regional foods strongly
    df.loc[regional, "disease_score"] = (df.loc[regional, "disease_score"] + 40).clip(
        upper=100
    )
    # Slightly downrank generic foods (still available as fallback)
    generic_only = generic_mask & ~regional
    df.loc[generic_only, "disease_score"] = (
        df.loc[generic_only, "disease_score"] - 5
    ).clip(lower=1)
    return df
