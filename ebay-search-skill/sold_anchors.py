#!/usr/bin/env python3
"""Best-effort sold-price anchors from eBay's public 'Verkauft' search.

The Browse API exposes ACTIVE listings only — no sold history. To estimate
what a category actually resells for, this script fetches eBay's public
completed/sold search pages (the same view the website shows when you filter
'Verkauft' on the left) and parses the sold prices.

It is deliberately best-effort and opt-in:
  * it scrapes a public HTML page — no API key, no contract, and eBay may
    change the markup, block the request or rate-limit you at any time;
  * the workflow only runs it when the repo Variable EBAY_SOLD_ANCHORS=1;
  * medians with fewer than MIN_SAMPLE sold items are written as empty so the
    report does not present a 2-item median as an anchor.

Run it AFTER the scan (it reads which queries were scanned from ebay_deals.csv
and reuses the scan keywords from queries.py):

    python sold_anchors.py ebay_deals.csv sold_anchors.csv [--limit 40] [--dry-run]

Output: sold_anchors.csv (query, marketplace, median_sold, cheapest_sold,
sample_size, fetched_at) — merged into LATEST.md as "sold median €X (n=Y)".
"""

import argparse
import csv
import datetime
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request

# Console-safe output (Windows consoles default to cp1252; never crash on emoji).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from queries import DEFAULT_QUERIES

SOLD_PATH_TMPL = "https://{domain}/sch/i.html"
DOMAINS = {
    "EBAY_DE": "ebay.de", "EBAY_AT": "ebay.at", "EBAY_CH": "ebay.ch",
    "EBAY_NL": "ebay.nl", "EBAY_FR": "ebay.fr", "EBAY_IT": "ebay.it",
    "EBAY_ES": "ebay.es", "EBAY_GB": "ebay.co.uk", "EBAY_US": "ebay.com",
}
DEFAULT_CURRENCY = {"EBAY_GB": "GBP", "EBAY_US": "USD"}  # everything else: EUR

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
MIN_SAMPLE = 5          # below this, the median is not a trustworthy anchor
SLEEP_BETWEEN = 1.5     # seconds between requests — be gentle
PRICE_SPAN_RE = re.compile(r'class="s-item__price"[^>]*>\s*(.*?)\s*</span>',
                           re.S)


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_price_text(text):
    """Strip HTML entities and whitespace from a price cell."""
    text = text.replace("&nbsp;", " ").replace("&euro;", "€").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def parse_price(text, currency):
    """Parse one price cell ('14,27 EUR', 'EUR 89,00', '1.234,56 EUR', '$1,699', …).

    Returns a float in the marketplace currency, or None. Foreign-currency
    cells ('$…' on ebay.de) are rejected so EUR medians stay EUR.
    """
    text = normalize_price_text(text)
    if not text or not re.search(r"\d", text):
        return None
    if "$" in text or "US $" in text or "USD" in text.upper():
        if currency != "USD":
            return None
    elif "£" in text or "GBP" in text.upper():
        if currency != "GBP":
            return None
    # Drop every currency marker ('EUR 89,00' / '89,00 EUR' / '€89' / '$1,699'…),
    # then keep only digits and separators.
    for marker in ("EUR", "euro", "€", "USD", "$", "GBP", "£", "US"):
        text = text.replace(marker, "")
    digits = re.sub(r"[^\d.,]", "", text)
    if not digits:
        return None
    if currency == "EUR":
        # German format: '.' = thousands, ',' = decimal. Both -> strip dots.
        if "," in digits and "." in digits:
            digits = digits.replace(".", "").replace(",", ".")
        elif "," in digits:
            digits = digits.replace(",", ".")
        else:
            digits = digits.replace(".", "")  # '1.234' = 1234
    else:  # USD/GBP: '.' = decimal, ',' = thousands
        digits = digits.replace(",", "")
    try:
        return float(digits)
    except ValueError:
        return None


def fetch_sold_prices(keyword, marketplace="EBAY_DE", limit=40):
    """Parse sold prices from eBay's completed-items search HTML."""
    domain = DOMAINS.get(marketplace, "ebay.de")
    params = {"_nkw": keyword, "LH_Sold": 1, "LH_Complete": 1, "_ipg": limit}
    url = SOLD_PATH_TMPL.format(domain=domain) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    currency = DEFAULT_CURRENCY.get(marketplace, "EUR")
    prices = []
    for m in PRICE_SPAN_RE.finditer(html):
        p = parse_price(m.group(1), currency)
        if p is not None:
            prices.append(p)
    return prices


def main():
    ap = argparse.ArgumentParser(description="Sold-price anchors from eBay 'Verkauft' search")
    ap.add_argument("csv", nargs="?", default="ebay_deals.csv",
                    help="scan output CSV (used to know which queries to anchor)")
    ap.add_argument("out", nargs="?", default="sold_anchors.csv")
    ap.add_argument("--limit", type=int, default=40, help="items per sold-search page")
    ap.add_argument("--marketplace", default="EBAY_DE")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be fetched/written without writing")
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        sys.exit(f"no scan CSV at {args.csv} — run ebay_search.py first")

    # Which queries did the scan actually cover? (name -> keyword)
    scanned = {}
    with open(args.csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            scanned.setdefault(r.get("query"), None)
    keyword_by_name = {q["name"]: q["q"] for q in DEFAULT_QUERIES}
    # For custom single-keyword scans the name IS the keyword.
    targets = {name: keyword_by_name.get(name, name) for name in scanned}

    print(f"fetching sold prices for {len(targets)} queries on {args.marketplace} "
          f"(limit {args.limit}/page, min sample {MIN_SAMPLE})\n")

    rows = []
    fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    for name, keyword in sorted(targets.items()):
        try:
            prices = fetch_sold_prices(keyword, marketplace=args.marketplace,
                                       limit=args.limit)
        except Exception as e:  # noqa: BLE001 - one bad fetch must not kill the run
            print(f"  {name}: ERROR {e}")
            continue
        sample = len(prices)
        if sample:
            median = statistics.median(prices)
            cheapest = min(prices)
        else:
            median = cheapest = None
        if sample < MIN_SAMPLE:
            print(f"  {name}: only {sample} sold item(s) — below MIN_SAMPLE, no anchor")
        else:
            print(f"  {name}: sold median {median:.2f} (n={sample}, cheapest {cheapest:.2f})")
        rows.append({
            "query": name,
            "marketplace": args.marketplace,
            "median_sold": f"{median:.2f}" if median is not None else "",
            "cheapest_sold": f"{cheapest:.2f}" if cheapest is not None else "",
            "sample_size": sample,
            "fetched_at": fetched_at,
        })
        time.sleep(SLEEP_BETWEEN)

    if args.dry_run:
        print(f"\n[dry-run] would write {len(rows)} rows to {args.out}")
        return 0
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["query", "marketplace", "median_sold",
                           "cheapest_sold", "sample_size", "fetched_at"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {args.out} with {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
