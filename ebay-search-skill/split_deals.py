#!/usr/bin/env python3
"""Split ebay_deals.csv into per-category CSVs + an index manifest.

Why: the site fetches the deal data over HTTP on every visit. One large CSV
means one request that can stall (slow connection, CDN hiccup, proxy) and
block the whole report. Splitting gives the front-end many small parallel
requests with individual timeouts: a stuck category file can no longer
blank the page — everything that arrived still renders.

Usage:
    python split_deals.py ebay_deals.csv site/data/deals [--min-rows 2]

Output (all written with utf-8-sig, matching the scanner):
    site/data/deals/index.json          -> [{"query": "...", "file": "...csv"}, ...]
    site/data/deals/<slug>.csv          -> one file per category
    <slug> is the query, sanitized to a safe filename.
"""

import argparse
import csv
import json
import os
import re
import sys

# Console-safe output (Windows consoles default to cp1252; never crash on emoji).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

FIELDS = ["query", "title", "price", "currency", "condition",
          "seller", "url", "marketplace", "win_min", "win_max"]


def slugify(query):
    """query -> safe filename (keep unicode letters/digits, else '-')."""
    s = re.sub(r"[^\w\u00C0-\uFFFF-]+", "-", query.strip(), flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "misc"


def split_deals(csv_path, out_dir, min_rows=2):
    """Read the scan CSV, group by query, write per-category files + index."""
    os.makedirs(out_dir, exist_ok=True)
    groups = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            q = (r.get("query") or "").strip()
            if not q or r.get("price") is None or r.get("price") == "":
                continue
            groups.setdefault(q, []).append(r)

    manifest = []
    for q in sorted(groups):
        rows = groups[q]
        slug = slugify(q)
        path = os.path.join(out_dir, f"{slug}.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        manifest.append({"query": q, "file": f"{slug}.csv", "rows": len(rows)})

    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    skipped = sum(1 for m in manifest if m["rows"] < min_rows)
    print(f"wrote {len(manifest)} category file(s) to {out_dir} "
          f"({sum(m['rows'] for m in manifest)} rows, {skipped} below {min_rows} rows)")
    return manifest


def main():
    ap = argparse.ArgumentParser(description="Split the scan CSV per category")
    ap.add_argument("csv", nargs="?", default="ebay_deals.csv")
    ap.add_argument("out", nargs="?", default="site/data/deals")
    ap.add_argument("--min-rows", type=int, default=2,
                    help="categories with fewer rows are still written but reported")
    args = ap.parse_args()
    if not os.path.exists(args.csv):
        sys.exit(f"no scan CSV at {args.csv} — run ebay_search.py first")
    split_deals(args.csv, args.out, args.min_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
