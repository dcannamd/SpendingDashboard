"""Builds web/data/detail.json: product-area spending for the US and Canada.

This runs after the main build and is fail-soft: if anything here goes wrong the
main dashboard is untouched and the old detail.json (if any) stays in place.

A plain-text report (data/detail_report.txt) lists, for every area, which lines
were used, the years covered and any problems. Paste it to Claude if an area
looks wrong.
"""
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone

from . import detail_areas as da
from . import fetch_bea as bea
from . import fetch_statcan as sc
from .common import CATEGORY_IDS, START_YEAR, statcan_table

log = logging.getLogger("pipeline")

GROUP_TOLERANCE = 1.02   # an area can't be bigger than its parent category
MIN_POINTS = 20          # areas with fewer region-years than this are dropped
PAUSE = 0.6              # seconds between BEA requests (BEA allows 100 a minute)


def _n(name):
    """Lower-case, straight apostrophes, single spaces."""
    name = name.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", name).strip().lower()


# ------------------------------------------------------------------ downloads
def us_cells(key):
    """({(region, year): {line name: dollars per person}}, names not found)."""
    descs = bea.line_descriptions(key)
    by_name = {}
    for line, desc in descs.items():
        by_name.setdefault(_n(bea.norm_desc(desc)), line)
    needed = [_n(n) for n in da.names_needed("US")]
    missing = sorted(n for n in needed if n not in by_name)
    lines = {by_name[n]: n for n in needed if n in by_name}

    series = {}
    for line in sorted(lines, key=int):
        series.update(bea._data_by_line(key, bea.TABLE, [line]))
        time.sleep(PAUSE)
    needs_pop = any(bea._is_total(d) for rows in series.values() for d in rows[:1])
    pop = bea.population(key) if needs_pop else None

    cells = defaultdict(dict)
    for line, rows in series.items():
        for d in rows:
            region = bea._region(d)
            if not region:
                continue
            year = int(d["TimePeriod"])
            if year < START_YEAR:
                continue
            try:
                v = float(d["DataValue"].replace(",", ""))
            except ValueError:
                continue
            v *= 10 ** int(d.get("UNIT_MULT") or 0)
            if bea._is_total(d):
                p = (pop or {}).get((region, year))
                if not p:
                    continue
                v /= p
            cells[(region, year)][lines[line]] = v
    return cells, missing


def ca_cells():
    """({(region, year): {line label: dollars per household}}, labels not found)."""
    dims, rows = statcan_table(sc.PRODUCT_ID)
    cat_col, others = sc.pick_columns(dims)
    needed = {_n(n) for n in da.names_needed("CA")}
    seen = set()
    cells = defaultdict(dict)
    for r in rows:
        if r.get("UOM", "Dollars") != "Dollars" or not r["VALUE"]:
            continue
        if not sc.keep_row(r, others):
            continue
        region = sc.CA_NAME_TO_CODE.get(r["GEO"].strip())
        if not region:
            continue
        year = int(r["REF_DATE"][:4])
        if year < START_YEAR:
            continue
        label = _n(sc.norm(r[cat_col]))
        if label in needed:
            cells[(region, year)][label] = float(r["VALUE"])
            seen.add(label)
    return cells, sorted(needed - seen)


# ------------------------------------------------------------------ assembly
def _budgets(history):
    """{(region, year): {category: value}} for region-years with all 8 categories."""
    by = defaultdict(dict)
    for r in history:
        by[(r["region"], int(r["year"]))][r["category"]] = float(r["value"])
    return {k: v for k, v in by.items() if all(c in v for c in CATEGORY_IDS)}


def pick_value(area, country, cell):
    """(value, option number) from the first option whose lines are all present."""
    for i, opt in enumerate(area[country.lower()]):
        names = [_n(n) for n in opt]
        if all(n in cell for n in names):
            return sum(cell[n] for n in names), i
    return None, None


def assemble(history, cpi, base_year, cells_by_country):
    """Pure function: raw cells -> (payload, report text). Easy to test."""
    budgets = _budgets(history)
    rows, report = [], []
    kept_areas = {}
    for country, cells in cells_by_country.items():
        cp = cpi.get(country, {})
        base = base_year.get(country)
        report.append(f"== {country} ==")
        for area in da.AREAS:
            if not area[country.lower()]:
                continue
            pts, opts_used, over = [], defaultdict(int), 0
            for (region, year), cell in sorted(cells.items()):
                if not region.startswith(country):
                    continue
                bud = budgets.get((region, year))
                if not bud:
                    continue
                v, opt = pick_value(area, country, cell)
                if v is None:
                    continue
                if v > bud[area["group"]] * GROUP_TOLERANCE:
                    over += 1            # bigger than its own category: wrong lines
                    continue
                total = sum(bud.values())
                real = v * cp[base] / cp[year] if base and year in cp else None
                pts.append([area["id"], region, year, round(v / total * 100, 3),
                            round(v, 1), None if real is None else round(real, 1)])
                opts_used[opt] += 1
            if len(pts) < MIN_POINTS:
                report.append(f"DROPPED {area['id']}: only {len(pts)} region-years"
                              + (f", {over} exceeded their category" if over else ""))
                continue
            rows += pts
            kept_areas.setdefault(area["id"], set()).add(country)
            yrs = [p[2] for p in pts]
            latest = max(yrs)
            last = [p[3] for p in pts if p[2] == latest]
            report.append(
                f"{area['id']:<16} {min(yrs)}-{latest}  regions={len({p[1] for p in pts})}  "
                f"avg share {sum(last)/len(last):.2f}% in {latest}  "
                f"options used={dict(opts_used)}" + (f"  EXCEEDED CATEGORY {over}x" if over else ""))
    areas = [{"id": a["id"], "label": a["label"], "group": a["group"],
              "part_of": a["part_of"] if a["part_of"] in kept_areas else None,
              "note": a["note"], "countries": sorted(kept_areas[a["id"]])}
             for a in da.AREAS if a["id"] in kept_areas]
    # Compact form: area and region are positions in the lists below, not text.
    a_idx = {a["id"]: i for i, a in enumerate(areas)}
    codes = sorted({r[1] for r in rows})
    r_idx = {c: i for i, c in enumerate(codes)}
    rows = [[a_idx[r[0]], r_idx[r[1]], *r[2:]] for r in rows]
    payload = {
        "meta": {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "base_year": base_year},
        "areas": areas,
        "region_codes": codes,
        "fields": ["area_index", "region_index", "year", "share", "nominal", "real"],
        "rows": rows,
    }
    return payload, "\n".join(report)


def build(history, cpi, base_year):
    """Download and assemble. Returns (payload, report) or (None, message)."""
    cells, notes = {}, []
    key = os.environ.get("BEA_API_KEY")
    if key:
        try:
            cells["US"], missing = us_cells(key)
            if missing:
                notes.append(f"US lines not found in BEA table: {missing}")
        except Exception as e:  # noqa: BLE001
            log.error("Detail (US) failed: %s", e)
            notes.append(f"US failed: {e}")
    else:
        notes.append("BEA_API_KEY not set: US detail skipped")
    try:
        cells["CA"], missing = ca_cells()
        if missing:
            notes.append(f"CA labels not found in StatCan table: {missing}")
    except Exception as e:  # noqa: BLE001
        log.error("Detail (CA) failed: %s", e)
        notes.append(f"CA failed: {e}")
    if not cells:
        return None, "\n".join(notes)
    payload, report = assemble(history, cpi, base_year, cells)
    return payload, "\n".join(notes + ["", report])
