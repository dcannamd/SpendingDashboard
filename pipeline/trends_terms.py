"""Search terms for the Google Trends step: daily-living aids.

Edit this file to track other products. Rules that keep results meaningful:
  * Use phrases people really type, and avoid words with other meanings
    ("walker" alone also means a surname and a TV show).
  * Google compares at most 5 terms per request, so one ANCHOR term is added to
    every group of 4. The anchor links the groups so all terms share one scale.
  * Pick an anchor with steady, mid-sized interest. If its numbers come out tiny
    for a country, the report says so; change ANCHOR and rerun with --refresh.
"""

ANCHOR = "grab bars"
GEOS = ["CA", "US"]            # Canada and the United States
TIMEFRAME = "today 5-y"        # weekly data for five years

GROUPS = [
    {"id": "bathroom", "label": "Bathroom"},
    {"id": "dressing", "label": "Dressing and eating"},
    {"id": "kitchen", "label": "Kitchen and home"},
    {"id": "mobility", "label": "Mobility"},
    {"id": "general", "label": "General"},
]

# (search phrase, group, label shown on the dashboard)
TERMS = [
    ("grab bars", "bathroom", "Grab bars"),
    ("shower chair", "bathroom", "Shower chairs"),
    ("shower stool", "bathroom", "Shower stools"),
    ("transfer bench", "bathroom", "Transfer benches"),
    ("raised toilet seat", "bathroom", "Raised toilet seats"),

    ("sock aid", "dressing", "Sock aids"),
    ("button hook", "dressing", "Button hooks"),
    ("adaptive clothing", "dressing", "Adaptive clothing"),
    ("built up handle utensils", "dressing", "Built-up handle utensils"),
    ("rocker knife", "dressing", "Rocker knives"),

    ("jar opener", "kitchen", "Jar openers"),
    ("reacher grabber tool", "kitchen", "Reacher grabber tools"),
    ("pill organizer", "kitchen", "Pill organizers"),
    ("one handed kitchen tools", "kitchen", "One-handed kitchen tools"),
    ("bed rails for seniors", "kitchen", "Bed rails for seniors"),
    ("bed assist rail", "kitchen", "Bed assist rails"),

    ("rollator", "mobility", "Rollators"),
    ("walking cane", "mobility", "Walking canes"),
    ("walker basket", "mobility", "Walker baskets"),
    ("cane with seat", "mobility", "Canes with seats"),
    ("wheelchair cushion", "mobility", "Wheelchair cushions"),

    ("aging in place", "general", "Aging in place (overall)"),
]

assert ANCHOR in [t[0] for t in TERMS], "the anchor must also be a tracked term"
assert len({t[0] for t in TERMS}) == len(TERMS), "duplicate term"
assert {t[1] for t in TERMS} <= {g["id"] for g in GROUPS}, "unknown group"
