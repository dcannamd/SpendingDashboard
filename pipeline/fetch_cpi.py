"""Annual CPI for inflation adjustment: US (BLS, all-items CPI-U) and Canada (StatCan).

BLS works without a key (limited daily queries); set BLS_API_KEY for more.
"""
import os
from collections import defaultdict

from .common import START_YEAR, post_json, statcan_table
from datetime import date

BLS_SERIES = "CUUR0000SA0"      # CPI-U, US city average, all items, not seasonally adjusted
STATCAN_CPI_PRODUCT = "18100005"  # CPI, annual average, by geography and product group


def us_cpi():
    key = os.environ.get("BLS_API_KEY")
    url = f"https://api.bls.gov/publicAPI/{'v2' if key else 'v1'}/timeseries/data/"
    end = date.today().year
    months = defaultdict(dict)
    annual = {}
    for s in range(START_YEAR - 1, end + 1, 10):
        payload = {"seriesid": [BLS_SERIES], "startyear": str(s),
                   "endyear": str(min(s + 9, end))}
        if key:
            payload.update(registrationkey=key, annualaverage=True)
        res = post_json(url, payload)
        if res.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS: {res.get('message')}")
        for d in res["Results"]["series"][0]["data"]:
            y, p = int(d["year"]), d["period"]
            try:
                v = float(d["value"])
            except ValueError:
                continue
            if p == "M13":
                annual[y] = v
            elif p.startswith("M"):
                months[y][p] = v
    for y, m in months.items():
        # Accept 11 months: BLS never published October 2025 (government shutdown).
        if y not in annual and len(m) >= 11:
            annual[y] = sum(m.values()) / len(m)
    return annual


def ca_cpi():
    dims, rows = statcan_table(STATCAN_CPI_PRODUCT)
    prod_col = next((c for c in dims if "product" in c.lower()), dims[-1])
    months = defaultdict(list)
    for r in rows:
        if r["GEO"].strip() != "Canada" or not r["VALUE"]:
            continue
        if not r[prod_col].strip().lower().startswith("all-items"):
            continue
        months[int(r["REF_DATE"][:4])].append(float(r["VALUE"]))
    return {y: sum(v) / len(v) for y, v in months.items() if v}


def fetch():
    return {"US": us_cpi(), "CA": ca_cpi()}
