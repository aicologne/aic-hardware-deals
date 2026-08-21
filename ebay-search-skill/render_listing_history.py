#!/usr/bin/env python3
"""Track first-seen vs last-seen price per listing URL (repricing detection).

Reads the current scan (ebay_deals.csv) and updates site/data/listing_history.csv:
one row per listing URL with first_seen/first_price and last_seen/last_price.
The report and site use it to flag listings that were repriced since first
observed ("was €89 on 2026-08-14"). Stale entries (not seen for 60 days) are
pruned to keep the file bounded.

Usage:
    python render_listing_history.py [ebay_deals.csv] [site/data/listing_history.csv] [--date YYYY-MM-DD]
"""
import argparse
import csv
import datetime
import os
import sys

DEFAULT_MARKETPLACE = "EBAY_DE"
PRUNE_AFTER_DAYS = 60


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description="Track per-listing price history (repricing detection)")
    ap.add_argument("csv", nargs="?", default="ebay_deals.csv")
    ap.add_argument("out", nargs="?", default="site/data/listing_history.csv")
    ap.add_argument("--date", default=None, help="scan date YYYY-MM-DD (default: today UTC)")
    args = ap.parse_args()

    date = args.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    state = {}
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                state[r.get("url")] = r

    seen_urls = set()
    with open(args.csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            url = (r.get("url") or "").strip()
            if not url:
                continue
            price = num(r.get("price"))
            if price is None:
                continue
            seen_urls.add(url)
            entry = state.get(url)
            if entry is None:
                state[url] = {
                    "url": url,
                    "query": r.get("query", ""),
                    "marketplace": (r.get("marketplace") or DEFAULT_MARKETPLACE).strip(),
                    "first_seen": date,
                    "first_price": f"{price:.2f}",
                    "last_seen": date,
                    "last_price": f"{price:.2f}",
                }
            else:
                entry["last_seen"] = date
                entry["last_price"] = f"{price:.2f}"

    # Prune listings not seen for PRUNE_AFTER_DAYS (they left the market).
    try:
        today = datetime.date.fromisoformat(date)
    except ValueError:
        today = datetime.date.today()
    pruned = 0
    for url in list(state):
        last = state[url].get("last_seen", "")
        try:
            last_date = datetime.date.fromisoformat(last)
        except ValueError:
            last_date = today
        if (today - last_date).days > PRUNE_AFTER_DAYS and url not in seen_urls:
            del state[url]
            pruned += 1

    rows = sorted(state.values(), key=lambda r: (r.get("marketplace", ""), r.get("query", ""), r.get("url", "")))
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fields = ["url", "query", "marketplace", "first_seen", "first_price", "last_seen", "last_price"]
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    repriced = sum(1 for r in rows if num(r.get("first_price")) != num(r.get("last_price")))
    print(f"wrote {args.out} with {len(rows)} listings ({repriced} repriced, {pruned} pruned)")


if __name__ == "__main__":
    main()
