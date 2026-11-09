"""First-run diagnostic: python -m pipeline.check_sources

I (Claude) wrote the fetchers without being able to reach the live APIs, so run
this once from a machine with internet access. It confirms each source works
and prints how categories were matched, so mapping problems are visible.
"""
import os

from . import fetch_bea, fetch_cpi, fetch_statcan
from .common import statcan_table


def step(name, fn):
    try:
        out = fn()
        print(f"[ OK ] {name}" + (f": {out}" if out else ""))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name}: {e}")
        return False


def check_statcan():
    dims, rows = statcan_table(fetch_statcan.PRODUCT_ID)
    records, info = fetch_statcan.build(dims, rows)
    print(f"       dimensions: {dims}")
    print(f"       rows kept: {info['rows_kept']}; detail lines ignored: {info['n_unmapped']}")
    print("       mapped categories (category, first year, last year):")
    for label, (cat, y0, y1) in sorted(info["labels"].items(), key=lambda kv: kv[1][0]):
        print(f"         {label[:58]:58s} -> {cat:12s} {y0}-{y1}")
    missing = [k for k in fetch_statcan.CATEGORY_MAP if k not in info["labels"]]
    if missing:
        print(f"       !! never found: {missing}")
    if not info["totals_found"]:
        print("       !! no 'total current consumption' rows: cannot verify sums")
    bad = info["mismatches"]
    print(f"       sum check: {len(bad)} region-years differ from the survey total by >2%")
    for m in bad[:10]:
        print(f"         {m[0]} {m[1]}: mapped {m[2]} vs total {m[3]}")
    return f"{len(records)} records"


def check_bea():
    key = os.environ.get("BEA_API_KEY")
    if not key:
        raise RuntimeError("BEA_API_KEY not set")
    descs = fetch_bea.line_descriptions(key)
    line_cat, missing = fetch_bea.match_lines(descs)
    print(f"       table {fetch_bea.TABLE}: {len(descs)} lines; mapped lines:")
    for line in sorted(line_cat, key=int):
        print(f"         line {line:>3}  {fetch_bea.norm_desc(descs[line])[:62]:62s} -> {line_cat[line]}")
    if missing:
        print(f"       !! expected but not found: {missing}")
        raise RuntimeError(f"{len(missing)} expected lines missing from {fetch_bea.TABLE}")
    _d, line_cat, extras, series, pop = fetch_bea.load(key)
    records, info = fetch_bea.build(line_cat, extras, series, pop)
    print(f"       units reported by BEA: {info['units']}"
          f"{' (divided by state population)' if pop else ' (already per person)'}")
    if not info["totals_found"]:
        print("       !! no household-consumption total found: cannot verify sums")
    bad = info["mismatches"]
    print(f"       sum check: {len(bad)} state-years differ from BEA's total by >2%")
    for m in bad[:10]:
        print(f"         {m[0]} {m[1]}: mapped {m[2]} vs total {m[3]}")
    years = sorted({r["year"] for r in records})
    if years:
        y = years[-1]
        tx = sum(r["value"] for r in records if r["region"] == "US-TX" and r["year"] == y)
        print(f"       years {years[0]}-{y}; sample: Texas {y} total = ${tx:,.0f} per person")
    return f"{len(records)} records"


if __name__ == "__main__":
    step("Statistics Canada table", check_statcan)
    step("BEA line descriptions", check_bea)
    step("US CPI (BLS)", lambda: f"{len(fetch_cpi.us_cpi())} years")
    step("Canada CPI (StatCan)", lambda: f"{len(fetch_cpi.ca_cpi())} years")
