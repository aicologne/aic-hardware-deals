#!/usr/bin/env python3
"""Append today's per-category medians to site/data/history.csv (price history).

One row per (marketplace, query) per scan date, idempotent: re-running with
the same date replaces that date's rows instead of duplicating them. The
history powers the 30-day median trendline on the site (sparkline) and the
trend + movers sections in LATEST.md.

Usage:
    python render_history.py [ebay_deals.csv] [site/data/history.csv] [--date YYYY-MM-DD]
"""
import argparse
import csv
import datetime
import os
import statistics
import sys

DEFAULT_MARKETPLACE = "EBAY_DE"
MAX_DAYS = 180  # keep at most this many days of history (the site renders a 30-day trend)


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

    # Composite key: marketplace · query (single-marketplace scans read as EBAY_DE).
    groups = {}
    for r in rows:
        mp = (r.get("marketplace") or DEFAULT_MARKETPLACE).strip()
        key = f"{mp} · {r['query']}"
        groups.setdefault(key, []).append(r)

    new_rows = []
    for key in sorted(groups):
        qrows = groups[key]
        mp, _, query = key.partition(" · ")
        prices = [r["_price"] for r in qrows]
        cheapest = min(prices)
        at_target = sum(
            1 for r in qrows
            if r["_win_min"] is not None and r["_price"] <= r["_win_min"] * 1.15
        )
        new_rows.append({
            "date": date,
            "marketplace": mp,
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

    merged = sorted(existing + new_rows, key=lambda r: (r["date"], r["marketplace"], r["query"]))

    # Bound the file: drop anything older than MAX_DAYS so the CSV (and the
    # site's trend data) stays small forever instead of growing one row per
    # (marketplace, category) per day.
    try:
        cutoff = (
            datetime.date.fromisoformat(date) - datetime.timedelta(days=MAX_DAYS)
        ).isoformat()
    except ValueError:
        cutoff = "1970-01-01"
    merged = [r for r in merged if r.get("date", "") >= cutoff]
    pruned_days = len(existing + new_rows) - len(merged)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["date", "marketplace", "query", "median", "cheapest", "count", "at_target"]
        )
        writer.writeheader()
        writer.writerows(merged)

    print(f"wrote {args.out} with {len(merged)} rows ({len(new_rows)} for {date}, {pruned_days} older than {MAX_DAYS} days dropped)")


if __name__ == "__main__":
    main()
