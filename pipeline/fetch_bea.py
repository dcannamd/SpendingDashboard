"""US: BEA personal consumption expenditures (PCE) by state and function, annual.

Needs a free key: https://apps.bea.gov/API/signup/  ->  env var BEA_API_KEY

Table SAPCE4 is a hierarchy of 134 lines (total -> household consumption ->
functions such as housing, health, recreation -> detail such as pets). Only the
top-level function lines are mapped, so detail lines are never double counted.
Lines are matched by name, not number, so a renumbering by BEA doesn't silently
shift categories.

If the table reports totals (millions of dollars) rather than per-person
dollars, values are divided by state population (BEA table SAINC1, line 20).
A built-in check compares the mapped lines with BEA's own "household
consumption expenditures" total and drops any state-year that doesn't add up.
"""
import os
import re
from collections import defaultdict

from .common import START_YEAR, get_json, log
from .regions import US_NAME_TO_CODE

BASE = "https://apps.bea.gov/api/data"
TABLE = "SAPCE4"
POP_TABLE = "SAINC1"   # personal income summary; includes state population

# Top-level functions only. Alcohol is split out of the food line so it sits
# in "other", matching Statistics Canada. Tobacco is inside "other goods and
# services", so it is not mapped separately.
LEAF_TO_CATEGORY = {
    "food and nonalcoholic beverages purchased for off-premises consumption": "food",
    "food produced and consumed on farms": "food",
    "food services and accommodations": "food",
    "alcoholic beverages purchased for off-premises consumption": "other",
    "clothing, footwear, and related services": "clothing",
    "housing, utilities, and fuels": "housing",
    "furnishings, household equipment, and routine household maintenance": "furnishings",
    "health": "health",
    "transportation": "transport",
    "recreation": "recreation",
    "communication": "other",
    "education": "other",
    "financial services and insurance": "other",
    "other goods and services": "other",
}
TOTAL_NAME = "household consumption expenditures"
FOREIGN_NAME = "net foreign travel and expenditures abroad by u.s. residents"
TOLERANCE = 0.02   # mapped lines must be within 2% of BEA's total


def norm_desc(desc):
    d = re.sub(r"\[.*?\]", "", desc)       # drop "[SAPCE4]" style tags
    d = d.split(":")[-1]                    # last element of "A: B: C"
    d = re.sub(r"\(.*?\)", "", d)           # drop "(Dollars)" style units
    return d.strip().lower()


def _call(key, _timeout=120, **params):
    p = {"UserID": key, "ResultFormat": "JSON", **params}
    # Context for error messages. The key itself is never included.
    ctx = ", ".join(f"{k}={params[k]}" for k in ("method", "TableName", "LineCode") if k in params)
    res = get_json(BASE, p, timeout=_timeout)["BEAAPI"]
    if "Error" in res or "Error" in res.get("Results", {}):
        raise RuntimeError(f"BEA error [{ctx}]: {res.get('Error') or res['Results']['Error']}")
    return res["Results"]


def _data_by_line(key, table, lines):
    """{line: rows} for the given lines of a Regional table (all states, all years).

    BEA allows only one line per request when asking for every state, so this
    makes one request per line.
    """
    return {line: _call(key, method="GetData", DatasetName="Regional", TableName=table,
                        LineCode=line, GeoFips="STATE", Year="ALL")["Data"]
            for line in lines}


def line_descriptions(key):
    """{line code: description} for this table's lines only."""
    res = _call(key, method="GetParameterValuesFiltered", DatasetName="Regional",
                TargetParameter="LineCode", TableName=TABLE)
    return {str(v["Key"]): v["Desc"] for v in res["ParamValue"]}


def match_lines(descs):
    """(line -> category, names expected but not found)."""
    line_cat = {}
    for line, desc in descs.items():
        n = norm_desc(desc)
        if n in LEAF_TO_CATEGORY:
            line_cat[line] = LEAF_TO_CATEGORY[n]
    missing = sorted(set(LEAF_TO_CATEGORY) - {norm_desc(d) for d in descs.values()})
    return line_cat, missing


def find_line(descs, name):
    return next((l for l, d in descs.items() if norm_desc(d) == name), None)


def _is_total(d):
    unit = (d.get("CL_UNIT") or "").lower()
    return any(w in unit for w in ("million", "thousand", "billion"))


def _region(d):
    return US_NAME_TO_CODE.get(d["GeoName"].replace("*", "").strip())


def population(key):
    # Find the population line by name; its number differs between BEA tables.
    res = _call(key, method="GetParameterValuesFiltered", DatasetName="Regional",
                TargetParameter="LineCode", TableName=POP_TABLE)
    pop_descs = {str(v["Key"]): v["Desc"] for v in res["ParamValue"]}
    line = next((l for l, d in pop_descs.items() if norm_desc(d).startswith("population")), None)
    if line is None:
        raise RuntimeError(f"BEA: no population line in {POP_TABLE}; lines are "
                           f"{sorted(pop_descs.values())}")
    rows = _data_by_line(key, POP_TABLE, [line])[line]
    pop = {}
    for d in rows:
        region = _region(d)
        try:
            v = float(d["DataValue"].replace(",", "")) * 10 ** int(d.get("UNIT_MULT") or 0)
        except ValueError:
            continue
        if region and v > 0:
            pop[(region, int(d["TimePeriod"]))] = v
    return pop


def load(key):
    """Download everything needed. Returns (descs, line_cat, extras, series, pop)."""
    descs = line_descriptions(key)
    line_cat, missing = match_lines(descs)
    if missing:
        # An incomplete budget would give wrong shares, so stop rather than guess.
        raise RuntimeError(f"BEA: expected lines not found in {TABLE}: {missing}. "
                           "Run check_sources to see the table's actual line names.")
    extras = {"total": find_line(descs, TOTAL_NAME), "foreign": find_line(descs, FOREIGN_NAME)}
    wanted = set(line_cat) | {l for l in extras.values() if l}
    series = _data_by_line(key, TABLE, sorted(wanted, key=int))
    needs_pop = any(_is_total(d) for rows in series.values() for d in rows[:1])
    pop = population(key) if needs_pop else None
    return descs, line_cat, extras, series, pop


def build(line_cat, extras, series, pop):
    """Turn raw BEA rows into per-person records. Returns (records, info)."""
    units = set()

    def values(rows):
        for d in rows:
            region = _region(d)
            if not region:
                continue
            year = int(d["TimePeriod"])
            if year < START_YEAR:
                continue
            try:
                v = float(d["DataValue"].replace(",", ""))
            except ValueError:
                continue  # "(NA)", "(D)" etc.
            v *= 10 ** int(d.get("UNIT_MULT") or 0)
            if _is_total(d):
                p = (pop or {}).get((region, year))
                if not p:
                    continue
                v /= p
            units.add(d.get("CL_UNIT", ""))
            yield region, year, v

    acc = defaultdict(float)
    mapped = defaultdict(float)
    for line, cat in line_cat.items():
        for region, year, v in values(series[line]):
            acc[(region, year, cat)] += v
            mapped[(region, year)] += v
    totals, foreign = {}, defaultdict(float)
    if extras.get("total"):
        totals = {(r, y): v for r, y, v in values(series[extras["total"]])}
    if extras.get("foreign"):
        for r, y, v in values(series[extras["foreign"]]):
            foreign[(r, y)] = v

    mismatches = []
    for key, s in mapped.items():
        t = totals.get(key)
        if t is None:
            continue
        t -= foreign.get(key, 0.0)
        if t and abs(s - t) / t > TOLERANCE:
            mismatches.append((key[0], key[1], round(s), round(t)))
    bad = {(m[0], m[1]) for m in mismatches}

    records = [{
        "region": region, "country": "US", "category": cat, "year": year,
        "value": round(v, 2), "basis": "per_person", "currency": "USD",
        "source": f"BEA {TABLE}",
    } for (region, year, cat), v in sorted(acc.items()) if (region, year) not in bad]
    info = {"units": sorted(units), "mismatches": sorted(mismatches),
            "totals_found": len(totals), "mapped_sums": dict(mapped)}
    return records, info


def fetch():
    key = os.environ.get("BEA_API_KEY")
    if not key:
        raise RuntimeError("BEA_API_KEY is not set")
    _descs, line_cat, extras, series, pop = load(key)
    records, info = build(line_cat, extras, series, pop)
    if info["mismatches"]:
        log.warning("BEA: dropped %d state-years where mapped lines don't match BEA's "
                    "total (first few: %s). Run check_sources.",
                    len(info["mismatches"]), info["mismatches"][:3])
    if not info["totals_found"]:
        log.warning("BEA: no household-consumption total found; sums not verified")
    if not records:
        raise RuntimeError("BEA: no rows matched; run check_sources")
    return records
