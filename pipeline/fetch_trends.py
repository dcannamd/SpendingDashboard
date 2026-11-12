"""Google Trends step: search interest for daily-living aids (Canada and US).

Run from the spending-dashboard folder:

    pip3 install -r requirements-trends.txt        (once)
    python3 -m pipeline.fetch_trends               (about 20-30 minutes)
    python3 -m pipeline.fetch_trends --quick       (trend lines only, about 3 minutes)
    python3 -m pipeline.fetch_trends --refresh     (ignore saved results)

Writes web/data/trends.json (read by the dashboard) and data/trends_report.txt.

Notes you should know:
  * Google has no official free API. This uses the community "pytrends"
    library, which is unmaintained (last release 2023) and can stop working.
    If it does, the rest of the dashboard is unaffected; the card just stays empty.
  * Google rate-limits. The run pauses between requests and backs off when asked
    to slow down. Every result is saved as it arrives (data/trends_cache.json),
    so if the run is blocked, run it again later and it carries on.
  * Google Trends gives RELATIVE interest (0-100), not search counts or sales.
"""
import json
import logging
import random
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from . import trends_terms as T
from .regions import CA_NAME_TO_CODE, US_NAME_TO_CODE

log = logging.getLogger("pipeline")

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "trends_cache.json"
OUT = ROOT / "web" / "data" / "trends.json"
REPORT = ROOT / "data" / "trends_report.txt"

CACHE_DAYS = 14             # saved results younger than this are reused
BATCH = 4                   # terms per request, plus the anchor (Google's limit is 5)
MIN_BASE = 3.0              # growth is only reported when the earlier level is at least this
LOW_LEVEL = 5.0             # below this on Google's own 0-100 scale = "low volume"
WAITS = (0, 60, 150, 300)   # seconds waited before each retry when rate-limited


class RateLimited(Exception):
    """Google asked us to slow down."""


# --------------------------------------------------------------------------
# The only code that talks to Google. Everything else works on plain lists.
# --------------------------------------------------------------------------
class PytrendsClient:
    def __init__(self):
        try:
            from pytrends.request import TrendReq
        except ImportError:
            raise SystemExit("pytrends is not installed. Run:  pip3 install -r requirements-trends.txt")
        self.pt = TrendReq(hl="en-US", tz=480, timeout=(10, 40))

    @staticmethod
    def _guard(fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            text = f"{type(e).__name__} {e}"
            if "429" in text or "TooManyRequests" in text:
                raise RateLimited(text) from e
            raise

    def levels(self, terms, geo):
        """Weekly interest for up to 5 terms, all on one 0-100 scale."""
        def go():
            self.pt.build_payload(list(terms), cat=0, timeframe=T.TIMEFRAME, geo=geo)
            df = self.pt.interest_over_time()
            if df is None or df.empty:
                return None
            partial = [bool(x) for x in df["isPartial"]] if "isPartial" in df else [False] * len(df)
            return {"terms": list(terms),
                    "dates": [d.strftime("%Y-%m-%d") for d in df.index],
                    "partial": partial,
                    "series": {t: [float(v) for v in df[t]] for t in terms if t in df}}
        return self._guard(go)

    def detail(self, term, geo):
        """Interest by state/province, plus related searches, for one term."""
        def go():
            self.pt.build_payload([term], cat=0, timeframe=T.TIMEFRAME, geo=geo)
            reg = self.pt.interest_by_region(resolution="REGION", inc_low_vol=True)
            regions = {} if reg is None or reg.empty else {str(n): float(v) for n, v in reg[term].items()}
            rel = self.pt.related_queries().get(term) or {}

            def rows(df):
                if df is None or len(df) == 0:
                    return []
                out = []
                for q, v in zip(df["query"], df["value"]):
                    try:
                        v = int(float(v))
                    except (TypeError, ValueError):
                        pass
                    out.append([str(q), v])
                return out
            return {"regions": regions, "top": rows(rel.get("top")), "rising": rows(rel.get("rising"))}
        return self._guard(go)


# --------------------------------------------------------------------------
# Saved results and polite retrying
# --------------------------------------------------------------------------
def load_cache():
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return {}


def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, separators=(",", ":")))


class Runner:
    def __init__(self, client, cache, refresh=False, sleeper=time.sleep):
        self.client, self.cache, self.refresh, self.sleep = client, cache, refresh, sleeper

    def nap(self):
        self.sleep(random.uniform(4, 8))      # be gentle between requests

    def get(self, key, fn):
        """Saved result if recent, else call Google. Raises RateLimited if it keeps refusing."""
        e = self.cache.get(key)
        if e and not self.refresh and time.time() - e["t"] < CACHE_DAYS * 86400:
            return e["v"]
        for wait in WAITS:
            if wait:
                log.info("Google asked us to slow down. Waiting %d seconds...", wait)
                self.sleep(wait)
            try:
                v = fn()
            except RateLimited:
                continue
            except Exception as err:  # noqa: BLE001
                log.warning("Skipped %s: %s", key, err)
                return None                     # not saved, so a later run tries again
            self.cache[key] = {"t": time.time(), "v": v}
            save_cache(self.cache)
            self.nap()
            return v
        raise RateLimited("Google kept refusing requests")


def collect(runner, quick=False):
    """Download (or reuse) everything. Returns (data, abort message or None)."""
    others = [t[0] for t in T.TERMS if t[0] != T.ANCHOR]
    groups = [others[i:i + BATCH] for i in range(0, len(others), BATCH)]
    data = {geo: {"batches": [], "detail": {}} for geo in T.GEOS}
    try:
        for geo in T.GEOS:                       # trend lines for both countries first
            for grp in groups:
                terms = [T.ANCHOR] + grp
                v = runner.get(f"levels|{geo}|{','.join(terms)}",
                               lambda terms=terms, geo=geo: runner.client.levels(terms, geo))
                if v:
                    data[geo]["batches"].append(v)
        if not quick:
            for geo in T.GEOS:                   # then regions and related searches
                for term, _g, _l in T.TERMS:
                    v = runner.get(f"detail|{geo}|{term}",
                                   lambda term=term, geo=geo: runner.client.detail(term, geo))
                    if v:
                        data[geo]["detail"][term] = v
    except RateLimited as e:
        return data, str(e)
    return data, None


# --------------------------------------------------------------------------
# Turning raw results into the dashboard file (plain Python, easy to test)
# --------------------------------------------------------------------------
def slug(term):
    return re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _pct(now, base):
    if now is None or base is None or base < MIN_BASE:
        return None
    return (now / base - 1) * 100


def _r(v, d=1):
    return None if v is None else round(v, d)


def _norm_name(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


_NAMES = {"US": {_norm_name(n): c for n, c in US_NAME_TO_CODE.items()},
          "CA": {_norm_name(n): c for n, c in CA_NAME_TO_CODE.items()}}
_NAMES["CA"]["yukon territory"] = _NAMES["CA"].get("yukon")


def _clean(res):
    """Drop Google's incomplete latest week."""
    keep = [i for i, p in enumerate(res.get("partial") or [False] * len(res["dates"])) if not p]
    dates = [res["dates"][i] for i in keep]
    return dates, {t: [v[i] for i in keep] for t, v in res["series"].items()}


def normalize(batches):
    """Put every batch on one scale using the anchor term they all share.

    Returns (dates, {term: {"raw", "factor", "weak"}}, anchor means per batch).
    """
    cleaned = [_clean(b) for b in batches]
    n = min(len(d) for d, _ in cleaned)
    cleaned = [(d[-n:], {t: v[-n:] for t, v in s.items()}) for d, s in cleaned]
    dates = cleaned[0][0]
    ref = next((_mean(s[T.ANCHOR]) for _, s in cleaned if T.ANCHOR in s), None)
    out, anchors = {}, []
    for _, s in cleaned:
        a = _mean(s.get(T.ANCHOR, []))
        anchors.append(a)
        weak = a is None or a < LOW_LEVEL           # anchor too small: scaling is unreliable
        factor = (ref / a) if (a and ref) else None
        for term, vals in s.items():
            if term == T.ANCHOR and term in out:
                continue
            out[term] = {"raw": vals, "factor": factor, "weak": weak}
    return dates, out, anchors


def monthly(dates, values):
    months = {}
    for d, v in zip(dates, values):
        months.setdefault(d[:7], []).append(v)
    keys = sorted(months)
    return keys, [_mean(months[k]) for k in keys]


def assemble(data):
    """data -> (payload for the dashboard, plain-text report)."""
    terms = [{"id": slug(t), "term": t, "group": g, "label": lab} for t, g, lab in T.TERMS]
    report, geo_out = [], {}
    for geo, g in data.items():
        report.append(f"== {geo} ==")
        if not g["batches"]:
            report.append("No trend data for this country (see messages above).")
            continue
        dates, norm, anchors = normalize(g["batches"])
        report.append("Anchor '%s' average per batch (Google's 0-100 scale): %s"
                      % (T.ANCHOR, ", ".join("none" if a is None else f"{a:.1f}" for a in anchors)))
        if any(a is None or a < LOW_LEVEL for a in anchors):
            report.append("WARNING: the anchor is very small in some batches, so comparisons between "
                          "terms in different batches are unreliable. Consider a different ANCHOR in "
                          "trends_terms.py, then rerun with --refresh.")
        levels = {}
        for t, v in norm.items():
            last = _mean(v["raw"][-52:])
            if last is not None and v["factor"]:
                levels[t] = last * v["factor"]
        top = max(levels.values(), default=0)
        scale = 100 / top if top > 0 else 1
        tdata, unmapped = {}, set()
        for t in terms:
            v = norm.get(t["term"])
            if not v:
                report.append(f"{t['term']:<24} NO DATA")
                continue
            raw = v["raw"]
            last = _mean(raw[-52:])
            prev = _mean(raw[-104:-52]) if len(raw) >= 104 else None
            y3b = _mean(raw[-208:-156]) if len(raw) >= 208 else None
            low = bool(v["weak"] or v["factor"] is None or last is None or last < LOW_LEVEL)
            f = (v["factor"] or 1.0) * scale
            _keys, m = monthly(dates, [x * f for x in raw])
            e = {"level": _r(levels[t["term"]] * scale) if t["term"] in levels else None,
                 "yoy": _r(_pct(last, prev)), "y3": _r(_pct(last, y3b)), "low": low,
                 "m": [_r(x) for x in m]}
            d = g["detail"].get(t["term"])
            if d:
                reg = {}
                for name, val in d["regions"].items():
                    code = _NAMES[geo].get(_norm_name(name))
                    if code:
                        reg[code] = round(val)
                    else:
                        unmapped.add(name)
                e["region"] = reg
                e["top"] = d["top"][:6]
                e["rising"] = d["rising"][:8]
            tdata[t["id"]] = e
            report.append("%-24s level %5s  1yr %6s  3yr %6s  %s%s" % (
                t["term"], e["level"], e["yoy"], e["y3"], "LOW VOLUME " if low else "",
                f"regions={len(e.get('region', {}))}" if d else "no region/related data"))
        if unmapped:
            report.append("Region names not recognised: " + ", ".join(sorted(unmapped)))
        geo_out[geo] = {"start": dates[0][:7], "terms": tdata}
    payload = {"meta": {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "anchor": T.ANCHOR, "timeframe": T.TIMEFRAME},
               "groups": T.GROUPS, "terms": terms, "geo": geo_out}
    return payload, "\n".join(report)


def main(argv=None, client=None, sleeper=time.sleep):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    argv = sys.argv[1:] if argv is None else argv
    runner = Runner(client or PytrendsClient(), load_cache(), "--refresh" in argv, sleeper)
    data, aborted = collect(runner, quick="--quick" in argv)
    payload, report = assemble(data)
    if aborted:
        report = (f"STOPPED EARLY: {aborted}\nProgress is saved. Run the same command again later "
                  f"(an hour or more is safest) and it will carry on.\n\n") + report
        log.warning("Stopped early: %s. Run again later to continue.", aborted)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report + "\n")
    if not payload["geo"]:
        log.error("No Google Trends data was collected. Report: %s", REPORT)
        return 1
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    log.info("Wrote %s (%d countries). Report: %s", OUT, len(payload["geo"]), REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
