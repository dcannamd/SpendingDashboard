"""Canada: Statistics Canada Survey of Household Spending (annual, by province).

No API key needed. Table 11-10-0222-01 (product id 11100222): household
spending by category, Canada and provinces, average dollars per household.

The table is a hierarchy (top-level categories plus hundreds of detailed
lines). Only the top-level categories are mapped, so detail lines are never
double counted. A built-in check compares the mapped categories with the
survey's own "total current consumption" and drops any region-year that
doesn't add up (for example because a category was renamed).
"""
import re
from collections import defaultdict

from .common import START_YEAR, log, statcan_table
from .regions import CA_NAME_TO_CODE

PRODUCT_ID = "11100222"

CATEGORY_MAP = {
    "shelter": "housing",
    "food expenditures": "food",
    "clothing and accessories": "clothing",
    "household furnishings and equipment": "furnishings",
    "transportation": "transport",
    "health care": "health",
    "recreation": "recreation",
    "household operations": "other",
    "personal care": "other",
    "education": "other",
    "reading materials and other printed matter": "other",
    "tobacco products and alcoholic beverages": "other",
    "games of chance": "other",
    "miscellaneous expenditures": "other",
}
# Renamed categories (newer survey years) are matched by prefix.
PREFIX_MAP = {
    "tobacco products, alcoholic beverages": "other",
}
# Totals and non-consumption items are deliberately excluded from the budget.
IGNORED_PREFIXES = ("total", "income taxes", "personal insurance", "gifts of money")
TOTAL_LABEL = "total current consumption"
TOLERANCE = 0.02   # mapped categories must be within 2% of the survey's total


def norm(label):
    label = re.sub(r"\s*\d+$", "", label.strip())      # trailing footnote number
    label = re.sub(r"\s*\[.*?\]", "", label)           # [1] style footnotes
    return label.strip().lower()


def category_for(label):
    cat = CATEGORY_MAP.get(label)
    if cat:
        return cat
    for prefix, c in PREFIX_MAP.items():
        if label.startswith(prefix):
            return c
    return None


def pick_columns(dims):
    # The table has a 'Statistic' column too, so find the category column by name.
    cat_col = next((c for c in dims if "categor" in c.lower()), None)
    if cat_col is None:
        raise RuntimeError(f"StatCan: no category column among {dims}")
    return cat_col, [c for c in dims if c != cat_col]


def keep_row(r, others):
    # Keep only "average expenditure per household" rows, all-household totals.
    for c in others:
        v = norm(r[c])
        if c.lower() == "statistic":
            if not v.startswith("average expenditure per household") or "reporting" in v:
                return False
        elif not v.startswith(("total", "all")):
            return False
    return True


def build(dims, rows):
    """Turn raw table rows into records. Returns (records, info).

    info: labels (label -> [category, first year, last year]), n_unmapped,
    totals_found, mismatches (list of (region, year, mapped, total)).
    """
    cat_col, others = pick_columns(dims)
    acc = defaultdict(float)
    totals = {}
    labels = {}
    unmapped = set()
    kept = 0
    for r in rows:
        if r.get("UOM", "Dollars") != "Dollars" or not r["VALUE"]:
            continue
        if not keep_row(r, others):
            continue
        region = CA_NAME_TO_CODE.get(r["GEO"].strip())
        if not region:
            continue
        year = int(r["REF_DATE"][:4])
        if year < START_YEAR:
            continue
        kept += 1
        label = norm(r[cat_col])
        value = float(r["VALUE"])
        if label == TOTAL_LABEL:
            totals[(region, year)] = value
            continue
        cat = category_for(label)
        if cat is None:
            if not label.startswith(IGNORED_PREFIXES):
                unmapped.add(label)
            continue
        acc[(region, year, cat)] += value
        lo, hi = labels.setdefault(label, [cat, year, year])[1:]
        labels[label][1], labels[label][2] = min(lo, year), max(hi, year)

    sums = defaultdict(float)
    for (region, year, _cat), v in acc.items():
        sums[(region, year)] += v
    mismatches = []
    for key, s in sums.items():
        t = totals.get(key)
        if t and abs(s - t) / t > TOLERANCE:
            mismatches.append((key[0], key[1], round(s), round(t)))
    bad = {(m[0], m[1]) for m in mismatches}

    records = [{
        "region": region, "country": "CA", "category": cat, "year": year,
        "value": round(v, 2), "basis": "per_household", "currency": "CAD",
        "source": "StatCan 11-10-0222-01",
    } for (region, year, cat), v in sorted(acc.items()) if (region, year) not in bad]
    info = {"labels": labels, "n_unmapped": len(unmapped), "rows_kept": kept,
            "totals_found": len(totals), "mismatches": sorted(mismatches)}
    return records, info


def fetch():
    dims, rows = statcan_table(PRODUCT_ID)
    records, info = build(dims, rows)
    if info["mismatches"]:
        log.warning("StatCan: dropped %d region-years where mapped categories don't match "
                    "the survey total (first few: %s). Run check_sources.",
                    len(info["mismatches"]), info["mismatches"][:3])
    if not info["totals_found"]:
        log.warning("StatCan: no 'total current consumption' rows found; sums not verified")
    if not records:
        raise RuntimeError("StatCan: no rows matched; run check_sources")
    return records
