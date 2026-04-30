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
    "north":   ["North Indian","Kashmiri","Awadhi","Punjabi","Rajasthani",
                "UP","Haryanvi","Himachali","Kumaoni","Garhwali","Sindhi"],
    "south":   ["South Indian","Kerala","Tamil Nadu","Karnataka",
                "Andhra","Chettinad","Hyderabadi","Telangana","Mangalorean",
                "Coorg","Nair","Syrian Christian"],
    "east":    ["Bengali","Odia","Bihari","Assamese","Northeast Indian",
                "Naga","Mizo","Tripuri","Sikkimese","Arunachali",
                "Manipuri","Khasi","Nepali/Sikkimese","Jharkhand"],
    "west":    ["Maharashtrian","Gujarati","Goan","Konkan","Malvani","Saraswat"],
    "central": ["Madhya Pradesh","Chhattisgarhi","Jain","Bundelkhandi"],
}

# Cuisines that must NEVER appear for a given zone (exclusion list)
ZONE_EXCLUDE = {
    "north":   ["South Indian","Kerala","Tamil Nadu","Karnataka","Andhra","Chettinad",
                "Hyderabadi","Telangana","Bengali","Odia","Assamese","Northeast Indian",
                "Naga","Mizo","Manipuri","Goan","Konkan"],
    "south":   ["North Indian","Punjabi","Rajasthani","Kashmiri","Awadhi","UP","Haryanvi",
                "Bengali","Odia","Assamese","Northeast Indian","Gujarati","Goan","Konkan"],
    "east":    ["South Indian","Kerala","Tamil Nadu","Karnataka","Andhra","Chettinad",
                "Hyderabadi","Telangana","North Indian","Punjabi","Rajasthani","Kashmiri",
                "Awadhi","Gujarati","Goan","Konkan","Rajasthani"],
    "west":    ["South Indian","Kerala","Tamil Nadu","Karnataka","Andhra","Hyderabadi",
                "Bengali","Odia","Assamese","Northeast Indian","Kashmiri","Naga"],
    "central": ["South Indian","Kerala","Tamil Nadu","Goan","Hyderabadi","Bengali",
                "Assamese","Northeast Indian","Naga","Mizo","Manipuri"],
    "any":     [],
}

# Which proteins / accompaniments / beverages pair with which staple_type
# East Indian staple pairings — fish curry, dalma, cholar dal, mustard-based dishes
EAST_BREAKFAST_COMBOS = [
    ["Luchi","Aloor Dom"],["Luchi","Cholar Dal"],["Muri","Chanachur"],
    ["Pitha","Mishti Doi"],["Idli","Sambar"],  # fallback
]

PAIRING_RULES = {
    "east_breakfast": {
        "protein_kw":   ["dalma","cholar","moong","lentil","mishti doi","dahi","curd",
                         "fish","egg","sorshe","mustard","posto","panch phoron"],
        "protein_cats": ["dals & legumes","dairy & paneer","seafood","egg dishes"],
        "acc_kw":        ["mishti doi","doi","achar","kasundi","mustard sauce","posto"],
        "bev_kw":        ["cha","tea","chai","milk","lassi","coconut water"],
        "skip":          [],
    },
    "south_breakfast": {
        "protein_kw":      ["sambar","rasam","coconut chutney","kadala","parippu",
                            "molagapodi","avial","khatta dal","moru","curd"],
        "protein_cats":    ["dals & legumes","dairy & paneer"],
        "acc_kw":          ["coconut chutney","tomato chutney","mint chutney",
                            "sambar","gun powder","gunpowder","idli podi"],
        "bev_kw":          ["coffee","filter coffee","rose milk","chai","tea","milk"],
        "skip":            [],
    },
    "roti": {
        "protein_kw":      ["dal","daal","rajma","chole","chana","maa","pindi",
                            "paneer","chicken","mutton","egg","fish","kadhi",
                            "arhar","moong","urad","haleem","keema"],
        "protein_cats":    ["dals & legumes","dairy & paneer","meat dishes",
                            "egg dishes","seafood"],
        "acc_kw":          ["raita","dahi","curd","pickle","achar","salad",
                            "green chutney","mint chutney","kachumber"],
        "bev_kw":          ["chai","lassi","buttermilk","chaas","tea","milk","lassi"],
        "skip":            [],
    },
    "rice": {
        "protein_kw":      ["dal","sambar","rasam","curry","kadhi","fish","chicken",
                            "prawn","rajma","chole","kootu","avial","dalma","amti",
                            "daal","lentil"],
        "protein_cats":    ["dals & legumes","meat dishes","seafood","dairy & paneer"],
        "acc_kw":          ["raita","dahi","papad","pappad","pickle","achar",
                            "chutney","kachumber","salad"],
        "bev_kw":          ["buttermilk","chaas","lassi","jaljeera","kokum","sol kadhi"],
        "skip":            [],
    },
    "biryani": {
        "protein_kw":      [],
        "protein_cats":    [],
        "acc_kw":          ["raita","salan","mirchi","onion salad","kachumber"],
        "bev_kw":          ["lassi","buttermilk","chaas","sharbat","jaljeera"],
        "skip":            ["protein","vegetable"],
    },
    "snack_breakfast": {
        "protein_kw":      ["curd","dahi","raita","lassi","buttermilk","chaas"],
        "protein_cats":    ["dairy & paneer"],
        "acc_kw":          ["green chutney","coconut chutney","tamarind chutney"],
        "bev_kw":          ["chai","tea","coffee","milk","green tea"],
        "skip":            ["vegetable"],
    },
    "western_breakfast": {
        "protein_kw":      ["egg","milk","yogurt","omelette","bhurji","cheddar",
                            "peanut butter","greek yogurt","paneer"],
        "protein_cats":    ["egg dishes","dairy & paneer"],
        "acc_kw":          ["fruit","salad","honey"],
        "bev_kw":          ["tea","coffee","milk","juice","green tea"],
        "skip":            [],
    },
    "other": {
        "protein_kw":      [],
        "protein_cats":    ["dals & legumes","dairy & paneer","meat dishes"],
        "acc_kw":          ["raita","salad","chutney"],
        "bev_kw":          ["chai","water","buttermilk","lassi"],
        "skip":            [],
    },
}

# Slot structure: ordered list of roles
SLOT_STRUCTURE = {
    "breakfast":     ["staple","protein","beverage"],
    "mid_morning":   ["fruit","snack","beverage"],
    "lunch":         ["staple","protein","vegetable","accompaniment","beverage"],
    "afternoon":     ["snack","beverage"],
    "evening_snack": ["snack","beverage"],
    "dinner":        ["staple","protein","vegetable","accompaniment"],
}

# Calorie % per role per slot
SLOT_CAL_PCT = {
    "breakfast":     {"staple":0.50,"protein":0.30,"beverage":0.20},
    "mid_morning":   {"fruit":0.50,"snack":0.30,"beverage":0.20},
    "lunch":         {"staple":0.35,"protein":0.28,"vegetable":0.20,
                      "accompaniment":0.10,"beverage":0.07},
    "afternoon":     {"snack":0.60,"beverage":0.40},
    "evening_snack": {"snack":0.60,"beverage":0.40},
    "dinner":        {"staple":0.38,"protein":0.30,"vegetable":0.22,"accompaniment":0.10},
}

ROLE_FALLBACKS = {
    "fruit":         ["snack","other"],
    "vegetable":     ["protein","snack"],
    "accompaniment": ["vegetable","snack"],
    "beverage":      ["snack"],
    "staple":        ["snack"],
    "protein":       ["vegetable","snack"],
    "snack":         ["fruit"],
}

UNIT_HINDI = {
    "piece":"नग/पीस","bowl":"कटोरी","glass":"गिलास",
    "cup":"कप","katori":"कटोरी","plate":"प्लेट",
    "gram":"ग्राम","tablespoon":"चम्मच",
}

# ─────────────────────────────────────────────────────────────────────────────
#  REALISTIC MEAL TEMPLATES
#  Each template is a list of (role, keyword_fragments) tuples.
#  The planner tries to match these against the food DB, producing
#  coherent meals that real Indians actually eat.
# ─────────────────────────────────────────────────────────────────────────────

MEAL_TEMPLATES = {
    # ── EAST ZONE ──────────────────────────────────────────────────────────
    "east_breakfast": [
        [("staple","luchi"), ("protein","cholar dal"), ("beverage","tea")],
        [("staple","luchi"), ("protein","aloor dom"), ("beverage","cha")],
        [("staple","pitha"), ("protein","mishti doi"), ("beverage","tea")],
        [("staple","muri"), ("protein","chanachur"), ("beverage","tea")],
        [("staple","idli"), ("protein","dalma"), ("beverage","tea")],
        [("staple","poha"), ("protein","dahi"), ("beverage","tea")],
        [("staple","paratha"), ("protein","egg"), ("beverage","tea")],
    ],
    "east_lunch": [
        [("staple","rice"), ("protein","dal"), ("vegetable","aloo posto"), ("accompaniment","papad")],
        [("staple","rice"), ("protein","fish curry"), ("vegetable","begun bhaja"), ("accompaniment","dahi")],
        [("staple","rice"), ("protein","dalma"), ("vegetable","stir fry"), ("accompaniment","pickle")],
        [("staple","rice"), ("protein","kosha mangsho"), ("vegetable","sabzi"), ("accompaniment","salad")],
        [("staple","rice"), ("protein","shorshe ilish"), ("vegetable","bhaja"), ("accompaniment","lemon")],
        [("staple","rice"), ("protein","chingri"), ("vegetable","vegetable"), ("accompaniment","papad")],
        [("staple","roti"), ("protein","dal"), ("vegetable","sabzi"), ("accompaniment","dahi")],
    ],
    "east_dinner": [
        [("staple","roti"), ("protein","dal"), ("vegetable","aloo sabzi"), ("accompaniment","salad")],
        [("staple","rice"), ("protein","moong dal"), ("vegetable","sabzi"), ("accompaniment","papad")],
        [("staple","chapati"), ("protein","egg curry"), ("vegetable","sabzi"), ("accompaniment","raita")],
        [("staple","khichdi"), ("protein","dal"), ("vegetable","papad"), ("accompaniment","pickle")],
        [("staple","roti"), ("protein","fish curry"), ("vegetable","sabzi"), ("accompaniment","salad")],
    ],
    # ── NORTH ZONE ─────────────────────────────────────────────────────────
    "north_breakfast": [
        [("staple","paratha"), ("protein","curd"), ("accompaniment","pickle"), ("beverage","chai")],
        [("staple","paratha"), ("protein","paneer"), ("beverage","chai")],
        [("staple","poha"), ("protein","dahi"), ("beverage","chai")],
        [("staple","upma"), ("protein","curd"), ("beverage","chai")],
        [("staple","bread"), ("protein","egg"), ("beverage","chai")],
        [("staple","idli"), ("protein","sambar"), ("beverage","coffee")],
        [("staple","puri"), ("protein","aloo"), ("beverage","chai")],
    ],
    "north_lunch": [
        [("staple","roti"), ("protein","dal makhani"), ("vegetable","sabzi"), ("accompaniment","raita")],
        [("staple","roti"), ("protein","rajma"), ("vegetable","sabzi"), ("accompaniment","salad")],
        [("staple","roti"), ("protein","paneer"), ("vegetable","sabzi"), ("accompaniment","raita")],
        [("staple","rice"), ("protein","dal tadka"), ("vegetable","sabzi"), ("accompaniment","papad")],
        [("staple","roti"), ("protein","chole"), ("vegetable","sabzi"), ("accompaniment","onion")],
        [("staple","rice"), ("protein","chicken curry"), ("vegetable","sabzi"), ("accompaniment","raita")],
        [("staple","roti"), ("protein","kadhi"), ("vegetable","aloo"), ("accompaniment","pickle")],
    ],
    "north_dinner": [
        [("staple","roti"), ("protein","dal"), ("vegetable","palak"), ("accompaniment","raita")],
        [("staple","roti"), ("protein","paneer"), ("vegetable","sabzi"), ("accompaniment","salad")],
        [("staple","chapati"), ("protein","egg"), ("vegetable","sabzi"), ("accompaniment","pickle")],
        [("staple","khichdi"), ("protein","dal"), ("vegetable","papad"), ("accompaniment","curd")],
        [("staple","roti"), ("protein","dal"), ("vegetable","bhindi"), ("accompaniment","salad")],
    ],
    # ── SOUTH ZONE ─────────────────────────────────────────────────────────
    "south_breakfast": [
        [("staple","idli"), ("protein","sambar"), ("accompaniment","coconut chutney"), ("beverage","coffee")],
        [("staple","dosa"), ("protein","sambar"), ("accompaniment","chutney"), ("beverage","coffee")],
        [("staple","upma"), ("protein","coconut chutney"), ("beverage","coffee")],
        [("staple","pongal"), ("protein","sambar"), ("beverage","coffee")],
        [("staple","idiyappam"), ("protein","coconut milk"), ("beverage","tea")],
        [("staple","puttu"), ("protein","kadala"), ("beverage","tea")],
        [("staple","appam"), ("protein","stew"), ("beverage","tea")],
    ],
    "south_lunch": [
        [("staple","rice"), ("protein","sambar"), ("vegetable","poriyal"), ("accompaniment","rasam")],
        [("staple","rice"), ("protein","rasam"), ("vegetable","kootu"), ("accompaniment","papad")],
        [("staple","rice"), ("protein","fish curry"), ("vegetable","thoran"), ("accompaniment","curd")],
        [("staple","rice"), ("protein","avial"), ("vegetable","stir fry"), ("accompaniment","pickle")],
        [("staple","roti"), ("protein","dal"), ("vegetable","sabzi"), ("accompaniment","curd")],
    ],
    "south_dinner": [
        [("staple","roti"), ("protein","dal"), ("vegetable","sabzi"), ("accompaniment","raita")],
        [("staple","rice"), ("protein","rasam"), ("vegetable","poriyal"), ("accompaniment","papad")],
        [("staple","idli"), ("protein","sambar"), ("accompaniment","chutney")],
        [("staple","chapati"), ("protein","egg"), ("vegetable","sabzi"), ("accompaniment","raita")],
    ],
    # ── WEST ZONE ──────────────────────────────────────────────────────────
    "west_breakfast": [
        [("staple","poha"), ("protein","peanuts"), ("beverage","chai")],
        [("staple","upma"), ("protein","curd"), ("beverage","chai")],
        [("staple","thepla"), ("protein","curd"), ("beverage","chai")],
        [("staple","dhokla"), ("accompaniment","chutney"), ("beverage","chai")],
        [("staple","idli"), ("protein","sambar"), ("beverage","coffee")],
        [("staple","bread"), ("protein","egg"), ("beverage","chai")],
    ],
    # ── GENERIC / ANY ──────────────────────────────────────────────────────
    "any_breakfast": [
        [("staple","poha"), ("protein","dahi"), ("beverage","chai")],
        [("staple","upma"), ("protein","coconut chutney"), ("beverage","coffee")],
        [("staple","idli"), ("protein","sambar"), ("beverage","coffee")],
        [("staple","dosa"), ("protein","sambar"), ("accompaniment","chutney"), ("beverage","coffee")],
        [("staple","paratha"), ("protein","curd"), ("accompaniment","pickle"), ("beverage","chai")],
        [("staple","roti"), ("protein","egg"), ("beverage","chai")],
        [("staple","bread"), ("protein","omelette"), ("beverage","tea")],
        [("staple","oats"), ("protein","milk"), ("beverage","tea")],
        [("staple","daliya"), ("protein","milk"), ("beverage","tea")],
    ],
    "any_lunch": [
        [("staple","rice"), ("protein","dal tadka"), ("vegetable","sabzi"), ("accompaniment","raita"), ("beverage","buttermilk")],
        [("staple","roti"), ("protein","rajma"), ("vegetable","sabzi"), ("accompaniment","salad")],
        [("staple","roti"), ("protein","paneer"), ("vegetable","sabzi"), ("accompaniment","raita")],
        [("staple","rice"), ("protein","sambar"), ("vegetable","poriyal"), ("accompaniment","papad")],
        [("staple","rice"), ("protein","chicken curry"), ("vegetable","sabzi"), ("accompaniment","raita")],
        [("staple","roti"), ("protein","chole"), ("vegetable","sabzi"), ("accompaniment","onion salad")],
        [("staple","biryani"), ("accompaniment","raita"), ("accompaniment","salad")],
        [("staple","roti"), ("protein","dal"), ("vegetable","aloo gobi"), ("accompaniment","pickle")],
    ],
    "any_dinner": [
        [("staple","roti"), ("protein","dal"), ("vegetable","palak"), ("accompaniment","raita")],
        [("staple","chapati"), ("protein","egg"), ("vegetable","sabzi"), ("accompaniment","salad")],
        [("staple","khichdi"), ("protein","dal"), ("vegetable","papad"), ("accompaniment","curd")],
        [("staple","roti"), ("protein","paneer"), ("vegetable","bhindi"), ("accompaniment","salad")],
        [("staple","rice"), ("protein","moong dal"), ("vegetable","stir fry"), ("accompaniment","papad")],
        [("staple","roti"), ("protein","chicken"), ("vegetable","sabzi"), ("accompaniment","raita")],
    ],
    # ── SNACKS ─────────────────────────────────────────────────────────────
    "mid_morning": [
        [("fruit","banana"), ("beverage","buttermilk")],
        [("fruit","apple"), ("snack","nuts")],
        [("snack","makhana"), ("beverage","coconut water")],
        [("fruit","seasonal fruit"), ("beverage","green tea")],
        [("snack","sprouts"), ("beverage","lemon water")],
        [("snack","chana"), ("beverage","buttermilk")],
        [("fruit","mango"), ("beverage","lassi")],
    ],
    "afternoon": [
        [("snack","samosa"), ("beverage","chai")],
        [("snack","bhel puri"), ("beverage","chai")],
        [("snack","dhokla"), ("beverage","chai")],
        [("snack","chana"), ("beverage","tea")],
        [("snack","poha"), ("beverage","chai")],
        [("snack","pakora"), ("beverage","chai")],
        [("fruit","fruit"), ("beverage","green tea")],
        [("snack","murukku"), ("beverage","chai")],
        [("snack","namkeen"), ("beverage","chai")],
    ],
    "evening_snack": [
        [("snack","sprout"), ("beverage","lemon water")],
        [("snack","makhana"), ("beverage","green tea")],
        [("fruit","fruit"), ("beverage","water")],
        [("snack","chana"), ("beverage","buttermilk")],
        [("snack","yogurt"), ("snack","nuts")],
    ],
}

def _get_template_key(slot: str, zone: str) -> str:
    """Get the best template key for a given slot and zone."""
    zone_slots = {
        "breakfast": f"{zone}_breakfast",
        "lunch":     f"{zone}_lunch",
        "dinner":    f"{zone}_dinner",
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
    return top.iloc[rng.randint(0, len(top)-1)]


def _build_slot_from_template(safe_df, slot, target_kcal, metrics,
                               used_today, used_yesterday, rng,
                               preferred_region="any", festive_mode=None):
    """
    Build a meal slot using template-based selection for coherent, realistic meals.
    Falls back to role-by-role if template match fails.
    """
    zone = preferred_region if preferred_region and preferred_region != "any" else "any"
    template_key = _get_template_key(slot, zone)
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
        lambda r: _score(r, slot, metrics, used_yesterday, preferred_region), axis=1
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
                    (safe_df["meal_role"] == role) & (~safe_df["food_id"].isin(local_used))
                ]
                if not cands.empty:
                    top = cands.nlargest(min(5, len(cands)), "_s")
                    food = top.iloc[rng.randint(0, len(top)-1)]
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
        cal_pcts = {role: 1.0/n for role, _ in best_items}
    
    items = []
    for role, food in best_items:
        role_kcal = target_kcal * cal_pcts.get(role, target_kcal / max(len(best_items), 1) / target_kcal)
        it = _item(food, role_kcal, _role_label(role, slot))
        items.append(it)
        used_today[food["food_id"]] = used_today.get(food["food_id"], 0) + 1
    
    return items


def _role_label(role, slot):
    labels = {
        "staple": "मुख्य / Main",
        "protein": "दाल/करी / Dal-Curry" if slot in ("lunch","dinner") else "साथ / Side",
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
    unit    = str(row.get("serving_unit","gram"))
    piece_g = float(row.get("piece_weight_g",100))
    cal100  = max(float(row.get("calories_per_100g",50)), 1)

    if unit == "gram":
        raw       = target_kcal * 100 / cal100
        portion_g = max(30, min(round(raw / 5) * 5, 450))
        food_kcal = cal100 * portion_g / 100
        return portion_g, round(food_kcal,1), f"{portion_g:.0f}g", f"{portion_g:.0f}g"

    kcal_per = cal100 * piece_g / 100
    if kcal_per <= 0: kcal_per = 50
    n = max(1, round(target_kcal / kcal_per))
    caps = {"piece":4,"bowl":2,"glass":2,"cup":2,"katori":2,"plate":1}
    n = min(n, caps.get(unit, 3))
    portion_g  = piece_g * n
    food_kcal  = cal100 * portion_g / 100
    hu         = UNIT_HINDI.get(unit, unit)
    pl         = "s" if n > 1 and unit in ("piece","bowl","glass","cup") else ""
    return portion_g, round(food_kcal,1), f"{n} {unit}{pl}", f"{n} {hu} ({portion_g:.0f}g)"


# ─────────────────────────────────────────────────────────────────────────────
#  SCORING
# ─────────────────────────────────────────────────────────────────────────────

def _score(row, slot, metrics, used_yesterday, preferred_region=None, cuisine_hint=None):
    score  = float(row.get("disease_score",50))
    gi     = float(row.get("glycemic_index",0))
    fiber  = float(row.get("fiber_g",0))
    prot   = float(row.get("protein_g",0))
    sodium = float(row.get("sodium_mg",0))
    cal100 = float(row.get("calories_per_100g",100))
    meal_type = str(row.get("meal_type","")).lower()

    if fiber >= 3: score += 8
    if fiber >= 6: score += 5
    if   0 < gi <= 40:  score += 12
    elif 41 <= gi <= 55: score += 5
    elif gi > 70:        score -= 10
    if sodium > 400: score -= 12
    if sodium > 800: score -= 25
    if slot in ("mid_morning","afternoon","evening_snack") and cal100 > 400:
        score -= 18

    goal = getattr(metrics,"goal","maintain")
    if goal in ("weight_loss","weight_loss_aggressive","muscle_gain"):
        score += prot * 1.0
    if goal in ("weight_gain","weight_gain_mild","muscle_gain") and cal100 > 150:
        score += 7
    if goal in ("weight_loss","weight_loss_aggressive") and cal100 > 350:
        score -= 8

    # Time-of-day realism: strongly penalize wrong-time foods
    if slot == "breakfast":
        if "lunch_dinner" in meal_type and "breakfast" not in meal_type:
            score -= 20  # heavy mains not for breakfast
        if "breakfast" in meal_type:
            score += 15
    if slot in ("lunch","dinner"):
        if "breakfast" in meal_type and "lunch_dinner" not in meal_type:
            score -= 15  # breakfast items not for lunch/dinner
        if "lunch_dinner" in meal_type:
            score += 10
    if slot in ("mid_morning","afternoon","evening_snack"):
        if "snack" in meal_type or "snacks" in meal_type:
            score += 12

    if preferred_region and preferred_region != "any":
        if str(row.get("region_zone","pan_indian")) == preferred_region:
            score += 20

    # Cuisine coherence: strongly prefer same cuisine as the staple
    if cuisine_hint:
        ct = str(row.get("cuisine_type",""))
        if ct == cuisine_hint:
            score += 28
        elif ct in ("Indian","Pan-Indian"):
            score += 3

    if row["food_id"] in used_yesterday: score -= 20
    return max(round(score,2), 1)


# ─────────────────────────────────────────────────────────────────────────────
#  PICK ONE FOOD
# ─────────────────────────────────────────────────────────────────────────────

def _pick(safe_df, role, slot, metrics, used_today, used_yesterday, rng,
          preferred_region=None, cuisine_hint=None, kw_boost=None):
    # Exclude foods already used today
    exhausted = {fid for fid,cnt in used_today.items() if cnt >= 1}
    roles_to_try = [role] + ROLE_FALLBACKS.get(role,[])

    for try_role in roles_to_try:
        cands = safe_df[
            (safe_df["meal_role"] == try_role) &
            (~safe_df["food_id"].isin(exhausted))
        ].copy()
        if cands.empty:
            # Allow reuse if no other options
            cands = safe_df[safe_df["meal_role"] == try_role].copy()
        if cands.empty:
            continue

        # Keyword boost: narrow to relevant foods first
        if kw_boost:
            kw_mask = cands["food_name"].str.lower().apply(
                lambda n: any(k.lower() in n for k in kw_boost)
            )
            boosted = cands[kw_mask]
            if len(boosted) >= 2:
                cands = boosted

        cands = cands.copy()
        cands["_s"] = cands.apply(
            lambda r: _score(r, slot, metrics, used_yesterday, preferred_region, cuisine_hint), axis=1
        )
        # Use top 30 candidates with weighted random selection for variety
        pool    = cands.nlargest(min(30,len(cands)),"_s")
        # Apply softmax-like temperature to scores for better diversity
        scores  = pool["_s"].values
        # Temperature scaling: lower temp = more deterministic, higher = more random
        temp    = 12.0
        scaled  = scores / temp
        scaled  = scaled - scaled.max()  # numerical stability
        import math
        exp_s   = [math.exp(s) for s in scaled]
        total   = sum(exp_s)
        weights = [e/total for e in exp_s]

        try:
            idx    = rng.choices(range(len(pool)), weights=weights, k=1)[0]
            chosen = pool.iloc[idx]
        except Exception:
            if pool.empty: continue
            chosen = pool.iloc[0]

        used_today[chosen["food_id"]] = used_today.get(chosen["food_id"],0) + 1
        return chosen

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD ITEM DICT
# ─────────────────────────────────────────────────────────────────────────────

def _item(row, target_kcal, slot_label):
    portion_g, food_kcal, qty_d, qty_l = _calc_serving(row, target_kcal)
    f      = portion_g / 100.0
    raw_h  = row.get("food_name_hindi","")
    hindi  = "" if (not raw_h or str(raw_h).strip().lower() in ("nan","none","")) else str(raw_h).strip()
    bilin  = f"{row['food_name']} / {hindi}" if hindi else row["food_name"]
    return {
        "food_id":row["food_id"],"food_name":row["food_name"],
        "food_name_hindi":hindi,"food_name_bilingual":bilin,
        "category":row.get("category",""),"cuisine_type":row.get("cuisine_type",""),
        "meal_role":row.get("meal_role","other"),"slot_label":slot_label,
        "serving_unit":str(row.get("serving_unit","gram")),
        "piece_weight_g":float(row.get("piece_weight_g",100)),
        "qty_display":qty_d,"qty_label":qty_l,"portion_g":round(portion_g,0),
        "calories":round(food_kcal,1),
        "protein_g": round(float(row.get("protein_g",0))*f,1),
        "carbs_g":   round(float(row.get("carbs_g",0))*f,1),
        "fat_g":     round(float(row.get("fat_g",0))*f,1),
        "fiber_g":   round(float(row.get("fiber_g",0))*f,1),
        "sodium_mg": round(float(row.get("sodium_mg",0))*f,1),
        "disease_score":float(row.get("disease_score",50)),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD ONE SLOT
# ─────────────────────────────────────────────────────────────────────────────

# Diet-specific non-veg keywords to exclude from templates
_NONVEG_KEYWORDS = [
    "chicken","mutton","lamb","goat","beef","pork","fish","prawn","shrimp","crab",
    "lobster","squid","octopus","egg","keema","kheema","haleem","nihari","roganjosh",
    "seekh","tandoori chicken","chicken curry","fish curry","kosha mangsho",
    "shorshe ilish","chingri","crab curry","macher","ilish","hilsa","rohu",
    "katla","bekti","pomfret","surmai","bombil","kingfish","mackerel","sardine",
]
_VEG_PROTEIN_KW = [
    "dal","daal","lentil","rajma","chole","chana","paneer","tofu","soya",
    "moong","masoor","arhar","toor","urad","kadhi","sambar","rasam",
    "kootu","dalma","cholar","mung","matki","lobiya","black-eyed pea",
]
_VEGAN_EXCLUDE_KW = [
    "milk","dahi","curd","yogurt","paneer","ghee","butter","cream","cheese",
    "lassi","buttermilk","chaas","kheer","payasam","raita","mishti doi",
    "sheer khurma","halwa with milk","egg","omelette","bhurji",
]
_JAIN_EXCLUDE_KW = [
    "potato","aloo","carrot","gajar","beet","radish","mooli","turnip","yam",
    "arbi","sweet potato","shakarkand","onion","pyaaz","garlic","lahasun",
    "leek","shallot","spring onion","chicken","mutton","fish","egg","beef","pork",
    "prawn","shrimp","meat","keema",
]
_HALAL_EXCLUDE_KW = [
    "pork","bacon","ham","sausage","lard","pepperoni","prosciutto",
    "alcohol","wine","beer","rum cake","pork ribs",
]

def _filter_templates_by_diet(templates, diet_pref):
    """Filter meal templates to only include diet-appropriate combinations."""
    if not diet_pref or diet_pref in ("none",""):
        return templates
    
    dp = diet_pref.lower()
    filtered = []
    
    for template in templates:
        ok = True
        for role, kw in template:
            kw_lower = kw.lower()
            if dp in ("vegetarian","vegan","jain"):
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


def _build_slot(safe_df, slot, target_kcal, metrics, used_today, used_yesterday, rng, preferred_region=None, diet_pref=None):
    structure    = SLOT_STRUCTURE.get(slot, ["snack","beverage"])
    cal_pcts     = SLOT_CAL_PCT.get(slot, {r:1/len(structure) for r in structure})
    items        = []
    staple_type  = "other"
    cuisine_hint = None
    pairing      = PAIRING_RULES["other"]

    # For east breakfast: prefer Bengali/Odia staples
    east_zone = preferred_region == "east"

    for role in structure:
        role_kcal = target_kcal * cal_pcts.get(role, 0.25)

        # Skip roles that don't apply to this staple type
        if role in pairing.get("skip",[]):
            continue

        if role == "staple":
            # For east zone breakfast, filter to regional staples first
            staple_pool = safe_df
            if east_zone and slot == "breakfast":
                east_cuisines = set(ZONE_CUISINES.get("east",[]))
                ec_mask = safe_df["cuisine_type"].isin(east_cuisines)
                if ec_mask.sum() >= 3:
                    staple_pool = safe_df[ec_mask]

            chosen = _pick(staple_pool,"staple",slot,metrics,used_today,used_yesterday,rng,
                           preferred_region=preferred_region)
            if chosen is not None:
                staple_type  = str(chosen.get("staple_type","other")) or "other"
                cuisine_hint = str(chosen.get("cuisine_type",""))
                # Choose pairing rule: east breakfast gets its own rules
                east_cuisines = set(ZONE_CUISINES.get("east",[]))
                if slot == "breakfast" and cuisine_hint in east_cuisines:
                    pairing = PAIRING_RULES.get("east_breakfast", PAIRING_RULES["snack_breakfast"])
                else:
                    pairing = PAIRING_RULES.get(staple_type, PAIRING_RULES["other"])
                items.append(_item(chosen, role_kcal, "मुख्य / Main"))

        elif role == "protein":
            chosen = _pick(safe_df,"protein",slot,metrics,used_today,used_yesterday,rng,
                           preferred_region=preferred_region,cuisine_hint=cuisine_hint,
                           kw_boost=pairing.get("protein_kw") or None)
            if chosen is not None:
                label = "दाल/करी / Dal-Curry" if slot in ("lunch","dinner") else "साथ / Side"
                items.append(_item(chosen, role_kcal, label))

        elif role == "vegetable":
            chosen = _pick(safe_df,"vegetable",slot,metrics,used_today,used_yesterday,rng,
                           preferred_region=preferred_region,cuisine_hint=cuisine_hint)
            if chosen is not None:
                items.append(_item(chosen, role_kcal, "सब्जी / Sabzi"))

        elif role == "accompaniment":
            chosen = _pick(safe_df,"accompaniment",slot,metrics,used_today,used_yesterday,rng,
                           preferred_region=preferred_region,cuisine_hint=cuisine_hint,
                           kw_boost=pairing.get("acc_kw") or None)
            if chosen is not None:
                items.append(_item(chosen, role_kcal, "साइड / Side"))

        elif role == "beverage":
            chosen = _pick(safe_df,"beverage",slot,metrics,used_today,used_yesterday,rng,
                           kw_boost=pairing.get("bev_kw") or None)
            if chosen is not None:
                items.append(_item(chosen, role_kcal, "पेय / Drink"))

        elif role in ("fruit","snack"):
            chosen = _pick(safe_df,role,slot,metrics,used_today,used_yesterday,rng,
                           preferred_region=preferred_region)
            if chosen is not None:
                label = "फल / Fruit" if role=="fruit" else "नाश्ता / Snack"
                items.append(_item(chosen, role_kcal, label))

    totals = {k: round(sum(i[k] for i in items),1)
              for k in ["calories","protein_g","carbs_g","fat_g","fiber_g","sodium_mg"]}

    # Natural-language description
    parts = []
    for it in items:
        if it["serving_unit"] != "gram":
            parts.append(f"{it['qty_display']} {it['food_name']}")
        else:
            parts.append(f"{it['food_name']} ({it['qty_display']})")
    description = " + ".join(parts)

    return {
        "slot_label":       slot.replace("_"," ").title(),
        "target_kcal":      round(target_kcal,0),
        "actual_kcal":      totals["calories"],
        "meal_description": description,
        "foods":            items,
        "totals":           totals,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  BUILD DAILY / WEEKLY PLAN
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
#  FESTIVE / SEASONAL MODE
# ─────────────────────────────────────────────────────────────────────────────

import datetime as _dt

FESTIVE_BOOST_FOODS = {
    # keyword fragments → boost score
    "diwali":    ["kheer","halwa","besan ladoo","kaju katli","mathri","chakli",
                  "gulab jamun","barfi","gujiya","puri","paneer"],
    "holi":      ["gujiya","thandai","malpua","puran poli","dahi vada","namak pare"],
    "eid":       ["biryani","haleem","sheer khurma","sewai","kebab","korma","nihari"],
    "navratri":  ["kuttu","singhara","sabudana","rajgira","samak rice","sendha namak",
                  "makhana","arbi","sweet potato","lauki"],
    "onam":      ["avial","olan","erissery","payasam","kaalan","pachadi","rice"],
    "pongal":    ["pongal","sakkarai pongal","chakkara","rice","sesame"],
    "durga_puja":["hilsa","kosha mangsho","cholar dal","luchi","mishti doi","payesh",
                  "begun bhaja","aloo posto","sandesh","rosogolla"],
    "christmas": ["plum cake","mince pie","roast","mulled","gingerbread","chicken"],
    "ganesh":    ["modak","ukadiche modak","puran poli","panchamrit","coconut"],
}

SEASONAL_FOODS = {
    "winter": ["sarson ka saag","makki ki roti","gajar halwa","til","peanut",
               "peas","methi","spinach","amla","mustard","bajra","jaggery"],
    "summer": ["mango","watermelon","kokum","aam panna","lassi","curd","sattu",
               "cucumber","mint","coconut water","thandai","bel sharbat"],
    "monsoon":["corn","pakora","bhutta","chai","hot soup","dal","kadhi","ginger",
               "turmeric","samosa","vada"],
    "autumn": ["kaddu","kathal","arbi","sweet potato","chestnut","pomegranate",
               "dates","fig","almond"],
}

def _get_season():
    month = _dt.datetime.now().month
    if month in (12,1,2):   return "winter"
    if month in (3,4,5):    return "summer"
    if month in (6,7,8,9):  return "monsoon"
    return "autumn"

def apply_festive_seasonal_boost(df, festive_mode=None):
    """Boost disease_score for festive or seasonal foods."""
    df = df.copy()
    season = _get_season()
    seasonal_kws = SEASONAL_FOODS.get(season, [])
    if seasonal_kws:
        mask = df["food_name"].str.lower().apply(
            lambda n: any(k.lower() in n for k in seasonal_kws)
        )
        df.loc[mask, "disease_score"] = (df.loc[mask, "disease_score"] + 15).clip(upper=100)

    if festive_mode and festive_mode.lower() in FESTIVE_BOOST_FOODS:
        fest_kws = FESTIVE_BOOST_FOODS[festive_mode.lower()]
        fest_mask = df["food_name"].str.lower().apply(
            lambda n: any(k.lower() in n for k in fest_kws)
        )
        df.loc[fest_mask, "disease_score"] = (df.loc[fest_mask, "disease_score"] + 30).clip(upper=100)
    return df


def build_daily_plan(safe_df, metrics, day_num, used_yesterday=None, seed=42, preferred_region=None, festive_mode=None, diet_pref=None):
    rng            = random.Random(seed + day_num * 997)
    used_today     = {}
    used_yesterday = used_yesterday or set()
    meals          = {}
    day_totals     = {k:0 for k in ["calories","protein_g","carbs_g","fat_g","fiber_g","sodium_mg"]}

    # Apply festive/seasonal boost to food scores
    boosted_df = apply_festive_seasonal_boost(safe_df, festive_mode=festive_mode)

    for slot, target_kcal in metrics.meal_calories.items():
        meal = _build_slot(boosted_df, slot, target_kcal, metrics,
                           used_today, used_yesterday, rng, preferred_region,
                           diet_pref=diet_pref)
        meals[slot] = meal
        for k in day_totals:
            day_totals[k] += meal["totals"].get(k,0)

    return {
        "day":day_num,"meals":meals,
        "totals":{k:round(v,1) for k,v in day_totals.items()},
        "targets":{
            "calories":metrics.target_calories,"protein_g":metrics.protein_g,
            "carbs_g":metrics.carbs_g,"fat_g":metrics.fat_g,
            "fiber_g":metrics.fiber_g,"sodium_mg":metrics.sodium_mg,
        },
    }


def build_weekly_plan(safe_df, metrics, seed=42, preferred_region=None, festive_mode=None, diet_pref=None):
    DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    weekly         = []
    used_yesterday = set()
    for i, day in enumerate(DAYS):
        day_seed = seed + i * 1009 + (hash(day) % 997)
        plan = build_daily_plan(safe_df, metrics, day_num=i+1,
                                used_yesterday=used_yesterday, seed=day_seed,
                                preferred_region=preferred_region, festive_mode=festive_mode,
                                diet_pref=diet_pref)
        plan["day_name"] = day
        used_yesterday = {f["food_id"] for m in plan["meals"].values() for f in m["foods"]}
        weekly.append(plan)
    return weekly


def check_nutritional_gaps(daily_plan, metrics):
    t, tg = daily_plan["totals"], daily_plan["targets"]
    checks = [
        ("Calories","calories",  tg["calories"],  80, "kcal"),
        ("Protein", "protein_g", tg["protein_g"], 12, "g"),
        ("Carbs",   "carbs_g",   tg["carbs_g"],   20, "g"),
        ("Fat",     "fat_g",     tg["fat_g"],       8, "g"),
        ("Fiber",   "fiber_g",   tg["fiber_g"],     6, "g"),
        ("Sodium",  "sodium_mg", tg["sodium_mg"],  350,"mg"),
    ]
    warnings = []
    for name, key, target, tol, unit in checks:
        if target <= 0: continue
        actual = t.get(key,0)
        diff   = actual - target
        if abs(diff) > tol:
            direction = "above" if diff > 0 else "below"
            warnings.append(f"{name}: {actual:.0f}{unit} ({direction} target {target:.0f}{unit} by {abs(diff):.0f}{unit})")
    return warnings


def filter_by_region(safe_df, region_zone):
    if not region_zone or region_zone in ("any",""):
        return safe_df
    zone_key = region_zone.lower().strip()
    cuisines = ZONE_CUISINES.get(zone_key, [])
    excludes = ZONE_EXCLUDE.get(zone_key, [])
    if not cuisines:
        return safe_df
    df = safe_df.copy()
    zone_mask    = df.get("region_zone", pd.Series(dtype=str)) == zone_key
    cuisine_mask = df["cuisine_type"].isin(cuisines)
    regional     = zone_mask | cuisine_mask
    # Hard-exclude cuisines that definitely don't belong to this zone
    # BUT keep pan-Indian/generic foods so we always have enough variety
    exclude_mask = df["cuisine_type"].isin(excludes)
    generic_mask = df["cuisine_type"].isin(
        ["Indian","Pan-Indian","Continental","Western","Asian","Chinese","Italian","Fusion"]
    )
    # Drop hard-excluded non-generic foods entirely from the regional pool
    # Only remove if there are enough regional foods remaining
    strict_exclude = exclude_mask & ~generic_mask
    regional_count = regional.sum()
    if regional_count >= 40:
        df = df[~strict_exclude].copy()
        # Recompute masks after drop
        zone_mask    = df.get("region_zone", pd.Series(dtype=str)) == zone_key
        cuisine_mask = df["cuisine_type"].isin(cuisines)
        regional     = zone_mask | cuisine_mask
        generic_mask = df["cuisine_type"].isin(
            ["Indian","Pan-Indian","Continental","Western","Asian","Chinese","Italian","Fusion"]
        )
    # Boost regional foods strongly
    df.loc[regional, "disease_score"] = (df.loc[regional, "disease_score"] + 40).clip(upper=100)
    # Slightly downrank generic foods (still available as fallback)
    generic_only = generic_mask & ~regional
    df.loc[generic_only, "disease_score"] = (df.loc[generic_only, "disease_score"] - 5).clip(lower=1)
    return df
