"""Generate SYNTHETIC demo data so the dashboard can be previewed offline.

    python -m pipeline.make_demo_data

The numbers are random but plausible-looking. They are NOT real. The output is
flagged meta.synthetic = true and the dashboard shows a banner. Running the real
pipeline (python -m pipeline.build) overwrites it.
"""
import random

from .build import derive, write_output
from .common import CATEGORY_IDS
from .regions import CA, US

BASE_SHARE = {"housing": 31, "food": 14, "clothing": 4, "furnishings": 5,
              "transport": 15, "health": 11, "recreation": 8, "other": 12}
TREND = {"housing": 0.05, "food": -0.04, "clothing": -0.05, "furnishings": 0.0,
         "transport": -0.03, "health": 0.12, "recreation": 0.10, "other": -0.05}
YEARS = range(2011, 2025)


def main():
    rng = random.Random(42)
    rows, cpi = [], {"US": {}, "CA": {}}
    for country, grid, level, growth in (("US", US, 45000, 0.033), ("CA", CA, 68000, 0.028)):
        for y in YEARS:
            cpi[country][y] = 100 * (1.02 ** (y - YEARS[0]))
        for code, _name, _c, _r in grid:
            if country == "CA" and code in ("YT", "NT", "NU"):
                continue  # mimic missing territory data
            # regional differences scale with category size so small categories stay plausible
            offset = {c: rng.gauss(0, BASE_SHARE[c] * 0.12) for c in CATEGORY_IDS}
            wealth = rng.uniform(0.8, 1.25)
            for y in YEARS:
                t = y - YEARS[0]
                shares = {}
                for c in CATEGORY_IDS:
                    s = BASE_SHARE[c] + offset[c] + TREND[c] * t + rng.gauss(0, 0.25)
                    if y in (2020, 2021):
                        s += {"recreation": -1.0, "food": 0.8, "transport": -1.2}.get(c, 0)
                    shares[c] = max(s, 0.5)
                tot = sum(shares.values())
                spend = level * wealth * (1 + growth) ** t
                for c in CATEGORY_IDS:
                    rows.append({
                        "region": f"{country}-{code}", "country": country, "category": c,
                        "year": y, "value": spend * shares[c] / tot,
                        "basis": "per_person" if country == "US" else "per_household",
                        "currency": "USD" if country == "US" else "CAD",
                        "source": "SYNTHETIC DEMO",
                    })
    write_output(derive(rows, cpi, synthetic=True))
    print("Wrote synthetic demo data to web/data/spending.json")


if __name__ == "__main__":
    main()
