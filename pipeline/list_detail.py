"""Lists the detailed (sub-category) names in the BEA and Statistics Canada tables.

Run from the spending-dashboard folder:
    export BEA_API_KEY=your_key
    python3 -m pipeline.list_detail

It writes data/detail_lines.txt. Nothing else in the project changes.
"""
import os
from pathlib import Path

from .common import statcan_table
from .fetch_bea import TABLE, line_descriptions
from .fetch_statcan import PRODUCT_ID, pick_columns


def main():
    out = []
    key = os.environ.get("BEA_API_KEY")
    if key:
        out.append(f"== BEA {TABLE}: line code | description ==")
        descs = line_descriptions(key)
        for code in sorted(descs, key=int):
            out.append(f"{code} | {descs[code]}")
    else:
        out.append("BEA_API_KEY not set, skipped BEA")

    out.append("")
    out.append(f"== StatCan {PRODUCT_ID}: category labels ==")
    dims, rows = statcan_table(PRODUCT_ID)
    out.append(f"columns: {dims}")
    cat_col, _others = pick_columns(dims)
    seen = []
    for r in rows:
        label = r.get(cat_col, "").strip()
        if label and label not in seen:
            seen.append(label)
    out.extend(seen)

    path = Path("data/detail_lines.txt")
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(out) + "\n")
    print(f"Wrote {path} ({len(out)} lines). Open it and paste its contents to Claude.")


if __name__ == "__main__":
    main()
