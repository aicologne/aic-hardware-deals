#!/usr/bin/env python3
"""Append today's per-category medians to site/data/history.csv (price history).

One row per query per scan date, idempotent: re-running with the same date
replaces that date's rows instead of duplicating them. The history powers the
30-day median trendline on the site (sparkline) and the trend column in
LATEST.md.

Usage:
    python render_history.py [ebay_deals.csv] [site/data/history.csv] [--date YYYY-MM-DD]
"""
import argparse
import csv
import datetime
import os
import statistics
import sys


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description="Append today's per-category medians to the price history")
    ap.add_argument("csv", nargs="?", default="ebay_deals.csv")
    ap.add_argument("out", nargs="?", default="site/data/history.csv")
    ap.add_argument("--date", default=None, help="scan date YYYY-MM-DD (default: today UTC)")
    args = ap.parse_args()

    date = args.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    rows = []
    with open(args.csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["_price"] = num(r.get("price"))
            r["_win_min"] = num(r.get("win_min"))
            if r["_price"] is not None:
                rows.append(r)

    queries = sorted({r["query"] for r in rows})
    new_rows = []
    for query in queries:
        qrows = [r for r in rows if r["query"] == query]
        prices = [r["_price"] for r in qrows]
        cheapest = min(prices)
        at_target = sum(
            1 for r in qrows
            if r["_win_min"] is not None and r["_price"] <= r["_win_min"] * 1.15
        )
        new_rows.append({
            "date": date,
            "query": query,
            "median": f"{statistics.median(prices):.2f}",
            "cheapest": f"{cheapest:.2f}",
            "count": len(qrows),
            "at_target": at_target,
        })

    # Load existing history and drop today's rows (idempotent re-runs).
    existing = []
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("date") == date:
                    continue
                existing.append(r)

    merged = sorted(existing + new_rows, key=lambda r: (r["date"], r["query"]))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "query", "median", "cheapest", "count", "at_target"])
        writer.writeheader()
        writer.writerows(merged)

    print(f"wrote {args.out} with {len(merged)} rows ({len(new_rows)} for {date})")


if __name__ == "__main__":
    main()
