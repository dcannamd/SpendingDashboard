"""Write the related and rising searches for every product to data/related_report.txt.
Run:  python3 -m pipeline.list_related      then:  pbcopy < data/related_report.txt
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(os.path.join(ROOT, "web", "data", "trends.json")))
out = []
for c in ("US", "CA"):
    geo = T["geo"].get(c)
    if not geo: continue
    out.append(f"== {c} ==")
    for t in T["terms"]:
        e = geo["terms"].get(t["id"])
        if not e or e.get("low"): continue
        top = ", ".join(f"{q} ({v})" for q, v in (e.get("top") or [])[:8])
        rise = ", ".join(f"{q} ({'breakout' if v >= 5000 else '+' + str(v) + '%'})" for q, v in (e.get("rising") or [])[:8])
        if not top and not rise: continue
        out.append(f"{t['label']}\n  top: {top or '-'}\n  rising: {rise or '-'}")
path = os.path.join(ROOT, "data", "related_report.txt")
open(path, "w").write("\n".join(out) + "\n")
print("Wrote", path, f"({len(out)} lines)")
