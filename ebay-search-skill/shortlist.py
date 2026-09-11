#!/usr/bin/env python3
"""Rank the scan into a shortlist by expected margin, risk-adjusted by churn.

Why this exists
---------------
The 🔥 flag marks any listing within 15 % of an adaptive buy-low target. On the
2026-09-11 scan that was 85 of 603 listings (14 %) spread over 20 of 25
categories — a "shortlist" that contains a fifth of the market cannot be one.
Worse, a low asking price is not a profit:

    net = est_resale * (1 - fee_rate) - asking

`est_resale` comes from the sold-price anchors (site/data/sold_anchors.csv,
opt-in via EBAY_SOLD_ANCHORS=1) when they exist, and from the category's asking
median otherwise. The fallback is always labelled `asking median`, never
presented as if it were money in hand.

The ranking multiplies that margin by **market churn** measured from this
repo's own listing history: among listings already tracked for at least
MIN_AGE_SCANS scans, which share *left the market*? Measured on the 2026-09 data
(918 aged listings): 41 % of at-market listings disappeared within ~5 scans,
70 % of those 10–25 % under the median, 83 % of those more than 25 % under.
Monotonic in the discount — which is what makes it a liquidity signal rather
than noise, and what separates a €90 margin on something that never moves from
the same margin on something that turns over.

Caveat, stated plainly: a listing that "left the scan" is **sold or withdrawn**
and this tool cannot tell those apart, so churn is a rate, not a probability. It
is also the reason every margin here is a ceiling: 41 % of even at-market
listings vanish within ~5 scans, so a median asking price is a moving benchmark,
not a sell price.

Rules
-----
* Categories with fewer than `min_listings` listings are skipped: their medians
  are noise (n=2 Strix Halo once swung the whole market index by 17 %).
* At most `max_per_category` items per category, so one seller listing ten
  identical mini PCs cannot fill the list.
* **A category must have its own churn measurement to be ranked.** Categories
  without one (too few tracked listings) go into `unproven`, unranked: on the
  2026-09-11 scan the top raw margin belonged to Mac Studio Ultra (n=6, one aged
  listing) — a 27 %-swinging median that must not headline the report.
* Only positive expected margins are listed — a negative-EV "deal" is not one.
* Pure functions, stdlib only, no filesystem access except `load_listing_rows`.

The site mirrors this in `site/csv.js` (same constants, same arithmetic order);
`tests/stats.test.mjs` and `tests/test_render_report.py` pin both sides.
"""

import csv
import os
import statistics

DEFAULT_MARKETPLACE = "EBAY_DE"
DEFAULT_FEE_RATE = 0.13

MIN_LISTINGS = 5        # below this a category median is noise, not a market
MIN_AGE_SCANS = 5       # a listing must be observable this long to count as aged
MIN_AGED = 8            # below this a category's own rate is replaced by the global one
DEFAULT_LIMIT = 10
MAX_PER_CATEGORY = 2
UNPROVEN_LIMIT = 3      # how many "liquidity unknown" items to surface, unranked


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def marketplace_of(row):
    return ((row or {}).get("marketplace") or "").strip() or DEFAULT_MARKETPLACE


def key_for(row):
    """Composite key "MARKETPLACE · query" — same as history.csv and the report."""
    return f"{marketplace_of(row)} · {(row or {}).get('query') or ''}"


def load_listing_rows(path):
    """listing_history.csv -> list of rows ([] when the file is absent)."""
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r.get("url")]


def scan_dates_from(listing_rows):
    """Sorted unique scan dates seen in the listing history."""
    dates = set()
    for r in listing_rows or []:
        for field in ("first_seen", "last_seen"):
            value = (r.get(field) or "").strip()
            if value:
                dates.add(value)
    return sorted(dates)


def market_churn(listing_rows, scan_dates=None, min_age_scans=MIN_AGE_SCANS):
    """How often tracked listings leave the market — overall and per category.

    -> {"overall": {"aged", "gone", "rate"}, "by_key": {key: {...}}}

    `rate` = gone/aged (0..1), or None when nothing was aged enough to judge.
    Higher = the market clears listings faster. "Gone" is sold *or* withdrawn —
    see the module docstring for why the rate is still used as a liquidity
    weight (and why it is a rate, not a probability).
    """
    dates = scan_dates if scan_dates is not None else scan_dates_from(listing_rows)
    index = {d: i for i, d in enumerate(dates)}
    newest_i = len(dates) - 1
    overall = {"aged": 0, "gone": 0, "rate": None}
    by_key = {}

    for r in listing_rows or []:
        first = (r.get("first_seen") or "").strip()
        last = (r.get("last_seen") or "").strip()
        if first not in index or not last:
            continue
        # An entry whose last_seen is not a known scan date cannot be judged.
        if newest_i - index[first] < min_age_scans:
            continue
        newest = dates[newest_i]
        bucket = by_key.setdefault(key_for(r), {"aged": 0, "gone": 0, "rate": None})
        for target in (bucket, overall):
            target["aged"] += 1
            if last != newest:
                target["gone"] += 1

    for bucket in list(by_key.values()) + [overall]:
        if bucket["aged"]:
            bucket["rate"] = bucket["gone"] / bucket["aged"]
    return {"overall": overall, "by_key": by_key}


def estimate_resale(query, sold_anchors=None, category_median=None, min_sample=1):
    """(estimated resale price, source, sample size) for one category.

    Sold anchors win when they exist and carry enough samples; otherwise the
    category's asking median is used and labelled `asking median`.
    """
    anchor = (sold_anchors or {}).get(query)
    if anchor:
        median_sold = num(anchor.get("median_sold")) if isinstance(anchor, dict) else num(anchor)
        sample = anchor.get("sample_size") if isinstance(anchor, dict) else None
        try:
            sample = int(sample) if sample is not None else 0
        except (TypeError, ValueError):
            sample = 0
        if median_sold is not None and sample >= min_sample:
            return median_sold, "sold median", sample
    if category_median is None:
        return None, None, 0
    return category_median, "asking median", 0


def build_shortlist(rows, sold_anchors=None, listing_rows=None, scan_dates=None,
                    fee_rate=DEFAULT_FEE_RATE, limit=DEFAULT_LIMIT,
                    min_listings=MIN_LISTINGS, min_aged=MIN_AGED,
                    max_per_category=MAX_PER_CATEGORY, unproven_limit=UNPROVEN_LIMIT):
    """Rank listings by net margin * market churn.

    -> {"items": [...] (ranked, own churn measurement),
        "unproven": [...] (positive margin, liquidity not measurable yet),
        "skipped": {...}, "churn": {...},
        "estimated_from": {"sold median": n, "asking median": n}}
    """
    listing_rows = listing_rows or []
    churn = market_churn(listing_rows, scan_dates)
    overall = churn["overall"]

    priced = [r for r in rows or [] if num(r.get("price")) is not None]
    groups = {}
    for r in priced:
        groups.setdefault(key_for(r), []).append(r)

    skipped_thin, skipped_negative = [], 0
    candidates = []
    estimated_from = {"sold median": 0, "asking median": 0}

    for key, group in groups.items():
        prices = sorted(num(r["price"]) for r in group)
        if len(prices) < min_listings:
            skipped_thin.append(key)
            continue
        median = statistics.median(prices)
        query = group[0].get("query") or ""
        est, source, sample = estimate_resale(query, sold_anchors, median)

        bucket = churn["by_key"].get(key) or {}
        if bucket.get("aged", 0) >= min_aged and bucket.get("rate") is not None:
            weight, weight_source = bucket["rate"], "category"
        elif overall["rate"] is not None and overall["aged"] >= min_aged:
            weight, weight_source = overall["rate"], "global"
        else:
            weight, weight_source = 1.0, "unknown"   # no history yet: no discount

        for r in group:
            price = num(r["price"])
            net = est * (1 - fee_rate) - price
            if net <= 0:
                skipped_negative += 1
                continue
            candidates.append({
                "query": query,
                "marketplace": marketplace_of(r),
                "price": price,
                "est_resale": est,
                "est_source": source,
                "est_sample": sample,
                "net": net,
                "churn": weight,
                "churn_source": weight_source,
                "aged": bucket.get("aged", 0),
                "score": net * weight,
                "title": r.get("title") or "",
                "url": r.get("url") or "",
                "seller": r.get("seller") or "",
                "condition": r.get("condition") or "",
            })

    candidates.sort(key=lambda c: (-c["score"], -c["net"], c["price"], c["query"]))

    # Only categories whose own listings have been watched long enough to read a
    # churn rate are ranked. Everything else is real but unproven, and is
    # surfaced separately rather than competing for the #1 slot.
    items, unproven, per_category = [], [], {}
    for c in candidates:
        used = per_category.get(c["query"], 0)
        if used >= max_per_category:
            continue
        if c["churn_source"] != "category":
            if len(unproven) < unproven_limit:
                unproven.append(dict(c))
                per_category[c["query"]] = used + 1
            continue
        if len(items) >= limit:
            continue
        per_category[c["query"]] = used + 1
        if c["est_source"] in estimated_from:
            estimated_from[c["est_source"]] += 1
        item = dict(c)
        item["rank"] = len(items) + 1
        items.append(item)

    return {
        "items": items,
        "unproven": unproven,
        "skipped": {
            "thin_categories": sorted(skipped_thin),
            "negative_margin": skipped_negative,
        },
        "churn": churn,
        "estimated_from": estimated_from,
        "fee_rate": fee_rate,
    }
