"""Shared helpers: common category set, HTTP, StatCan table download."""
import csv
import io
import json
import logging
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date

log = logging.getLogger("pipeline")

# The common category set every source is mapped onto. BEA (US) is the coarsest
# source, so this is deliberately coarse. Finer product detail (pets, hobbies,
# baby gear, ...) needs other signals; see README "Next steps".
CATEGORIES = [
    ("housing", "Housing & utilities"),
    ("food", "Food & groceries"),
    ("clothing", "Clothing & footwear"),
    ("furnishings", "Furnishings & household equipment"),
    ("transport", "Transportation"),
    ("health", "Health care"),
    ("recreation", "Recreation"),
    ("other", "Other goods & services"),
]
CATEGORY_IDS = [c for c, _ in CATEGORIES]

# How many years of history to keep.
START_YEAR = date.today().year - 15

# Years where the source changed its methodology/classification, so a jump
# between that year and the previous one may be artificial. Shown as dashed
# lines on trend charts. Fill in after checking each agency's release notes.
BREAK_YEARS = {"US": [], "CA": []}

USER_AGENT = "spending-dashboard/0.1"


def http_get(url, params=None, retries=3, timeout=60):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    # Log the URL without its query string so API keys never reach the logs.
    raise RuntimeError(f"GET failed: {url.split('?')[0]}: {last}")


def get_json(url, params=None, **kw):
    return json.loads(http_get(url, params, **kw))


def post_json(url, payload, retries=3, timeout=60):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"POST failed: {url.split('?')[0]}: {last}")


STATCAN_STD_COLS = {
    "REF_DATE", "GEO", "DGUID", "UOM", "UOM_ID", "SCALAR_FACTOR", "SCALAR_ID",
    "VECTOR", "COORDINATE", "VALUE", "STATUS", "SYMBOL", "TERMINATED", "DECIMALS",
}


def statcan_table(product_id):
    """Download a full Statistics Canada table. Returns (dimension_cols, rows)."""
    meta = get_json(
        f"https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{product_id}/en")
    blob = http_get(meta["object"], timeout=180)
    z = zipfile.ZipFile(io.BytesIO(blob))
    name = next(n for n in z.namelist()
                if n.lower().endswith(".csv") and "metadata" not in n.lower())
    text = z.read(name).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    dims = [c for c in reader.fieldnames if c not in STATCAN_STD_COLS]
    return dims, list(reader)
