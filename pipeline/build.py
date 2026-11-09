"""Pipeline entry point.

    python -m pipeline.build

1. Runs each source fetcher (a failing source is logged and skipped, so one
   outage never wipes the dashboard).
2. Upserts the results into data/history.csv (first run = backfill, later runs
   = new releases added, revisions overwritten).
3. Derives budget shares + inflation-adjusted values and writes
   web/data/spending.json for the dashboard.
"""
import csv
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import fetch_bea, fetch_cpi, fetch_statcan
from .common import BREAK_YEARS, CATEGORIES, CATEGORY_IDS
from .regions import all_regions

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.csv"
CPI_CACHE = ROOT / "data" / "cpi.json"
OUTPUT = ROOT / "web" / "data" / "spending.json"
FIELDS = ["region", "country", "category", "year", "value", "basis", "currency", "source"]

FETCHERS = [("BEA (US)", fetch_bea.fetch), ("Statistics Canada", fetch_statcan.fetch)]

log = logging.getLogger("pipeline")


def load_history():
    if not HISTORY.exists():
        return []
    with HISTORY.open(newline="") as f:
        return list(csv.DictReader(f))


def save_history(rows):
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["region"], int(r["year"]), r["category"]))
    with HISTORY.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def upsert(old, new):
    merged = {(r["region"], r["category"], str(r["year"]), r["source"]): r for r in old}
    for r in new:
        merged[(r["region"], r["category"], str(r["year"]), r["source"])] = {
            k: r[k] for k in FIELDS}
    return list(merged.values())


def derive(rows, cpi, synthetic=False):
    """Turn raw long-format rows into the dashboard's compact JSON."""
    by = defaultdict(dict)
    for r in rows:
        by[(r["region"], int(r["year"]))][r["category"]] = float(r["value"])

    # Constant-dollar base year per country: latest year present in both data and CPI.
    data_years = defaultdict(set)
    for (region, year) in by:
        data_years[region[:2]].add(year)
    base = {}
    for country, ys in data_years.items():
        common = ys & set(cpi.get(country, {}))
        if common:
            base[country] = max(common)

    out, dropped = [], 0
    for (region, year), cats in sorted(by.items()):
        if any(c not in cats for c in CATEGORY_IDS):
            dropped += 1          # incomplete budget would distort the shares
            continue
        country = region[:2]
        total = sum(cats[c] for c in CATEGORY_IDS)
        cp = cpi.get(country, {})
        b = base.get(country)
        for c in CATEGORY_IDS:
            v = cats[c]
            real = v * cp[b] / cp[year] if b and year in cp else None
            out.append([region, c, year, round(v / total * 100, 3), round(v, 1),
                        None if real is None else round(real, 1)])
    if dropped:
        log.warning("Dropped %d region-years with missing categories", dropped)

    present = {r[0] for r in out}
    return {
        "meta": {
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "synthetic": synthetic,
            "sources": sorted({r["source"] for r in rows}),
            "base_year": base,
            "break_years": BREAK_YEARS,
            "covid_years": [2020, 2021],
        },
        "units": {
            "US": {"basis": "per person", "currency": "USD"},
            "CA": {"basis": "per household", "currency": "CAD"},
        },
        "categories": [{"id": i, "label": l} for i, l in CATEGORIES],
        "regions": [r for r in all_regions()],
        "present": sorted(present),
        "fields": ["region", "cat", "year", "share", "nominal", "real"],
        "rows": out,
    }


def write_output(payload):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")))


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    history = load_history()
    new, failures = [], []
    for name, fn in FETCHERS:
        try:
            rows = fn()
            log.info("%s: %d rows", name, len(rows))
            new += rows
        except Exception as e:  # noqa: BLE001
            log.error("%s failed: %s", name, e)
            failures.append(name)
    history = upsert(history, new)
    if not history:
        log.error("No data at all; not writing output.")
        return 1
    save_history(history)

    try:
        cpi = fetch_cpi.fetch()
        CPI_CACHE.write_text(json.dumps(cpi))
    except Exception as e:  # noqa: BLE001
        log.error("CPI fetch failed (%s); using cached CPI if any", e)
        cpi = json.loads(CPI_CACHE.read_text()) if CPI_CACHE.exists() else {}
        failures.append("CPI")
    cpi = {c: {int(y): v for y, v in d.items()} for c, d in cpi.items()}

    write_output(derive(history, cpi))
    log.info("Wrote %s", OUTPUT)
    return 1 if failures and not new else 0


if __name__ == "__main__":
    sys.exit(main())
