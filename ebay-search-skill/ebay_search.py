#!/usr/bin/env python3
"""
eBay Browse API — used-hardware deal scanner (companion to SKILL.md).

Scans eBay for active used listings by keyword + price range, sorted by price,
prints hits and writes ebay_deals.csv.

REALM HANDLING (sandbox vs production):
  - AUTO-DETECTED from the credentials: if EBAY_CLIENT_ID contains "-SBX-" or
    EBAY_CLIENT_SECRET starts with "SBX-", the script uses the SANDBOX endpoints
    (https://api.sandbox.ebay.com) and prints a warning that results are test
    data. Otherwise it uses PRODUCTION (https://api.ebay.com).
  - Override explicitly with --sandbox / --production (mutually exclusive).
  - Never expect real listings from the sandbox.

Setup:
  EBAY_CLIENT_ID=xxx EBAY_CLIENT_SECRET=yyy python ebay_search.py
  (or place an ebay.env next to the script / in the working directory; it is
  auto-loaded if present and the variables are not already set)

CLI overrides:
  python ebay_search.py --keyword "RTX 3090" --min 450 --max 750 \
      --condition USED --marketplace EBAY_DE --limit 50 --out deals.csv
  python ebay_search.py --sandbox --keyword "laptop" --max 200   # smoke test only
  python ebay_search.py --production                             # force live endpoints
"""

import argparse
import csv
import os
import sys
import time

import requests

from queries import DEFAULT_QUERIES

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
SANDBOX_SEARCH_URL = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

# Default currency per marketplace (used in multi-marketplace mode; the deal
# windows in queries.py are then interpreted in that currency — adjust the
# windows if you scan high-value non-EUR marketplaces).
MARKETPLACE_CURRENCY = {
    "EBAY_DE": "EUR", "EBAY_AT": "EUR", "EBAY_CH": "EUR", "EBAY_NL": "EUR",
    "EBAY_FR": "EUR", "EBAY_IT": "EUR", "EBAY_ES": "EUR", "EBAY_GB": "GBP",
    "EBAY_US": "USD", "EBAY_AU": "AUD", "EBAY_CA": "CAD",
}


def load_env_file(
    paths=(
        "ebay.env",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ebay.env"),
    )
):
    """Load KEY=VALUE lines from an env file without overriding existing vars."""
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    if key and key not in os.environ:
                        os.environ[key] = value.strip()
        except FileNotFoundError:
            continue


def detect_realm(client_id, client_secret):
    """Sandbox credentials are marked with SBX; everything else is production."""
    if client_id and "-SBX-" in client_id:
        return "sandbox"
    if client_secret and client_secret.upper().startswith("SBX-"):
        return "sandbox"
    return "production"


DEMO_ITEMS = [
    # production-style: condition as plain string
    {
        "title": "EVGA GeForce RTX 3090 FTW3 ULTRA 24GB",
        "price": {"value": "649.00", "currency": "EUR"},
        "condition": "Used",
        "seller": {"username": "demo-seller-1"},
        "itemWebUrl": "https://www.ebay.de/itm/demo1",
    },
    # sandbox-style: condition as object
    {
        "title": "HP EliteDesk 800 G4 Mini i5-8500T 16GB 512GB",
        "price": {"value": "159.50", "currency": "EUR"},
        "condition": {"conditionGroup": "USED", "conditionDescription": "Used"},
        "seller": {"username": "demo-seller-2"},
        "itemWebUrl": "https://www.ebay.de/itm/demo2",
    },
    # minimal item: missing fields must not crash
    {
        "title": "Samsung 32GB DDR4 RDIMM",
        "price": {"value": "89.99", "currency": "EUR"},
        "itemWebUrl": "https://www.ebay.de/itm/demo3",
    },
]


def get_token(client_id, client_secret, token_url):
    r = requests.post(
        token_url,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials", "scope": SCOPE},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def search(
    token,
    keyword,
    pmin,
    pmax,
    cond,
    category,
    marketplace,
    currency,
    limit,
    search_url,
    retries=3,
    debug=False,
):
    # NOTE: per the Browse API spec, the marketplace is set via the
    # X-EBAY-C-MARKETPLACE-ID HEADER (there is no marketplace_ids query param;
    # an unknown param is silently ignored and the API falls back to EBAY_US).
    # The price filter REQUIRES priceCurrency (error 12012) and condition
    # values take {BRACES} (e.g. conditions:{USED}).
    filters = [f"price:[{pmin}..{pmax}]", f"priceCurrency:{currency}"]
    if cond:
        filters.append(f"conditions:{{{cond}}}")
    params = {
        "q": keyword,
        "limit": limit,
        "filter": ",".join(filters),
        "sort": "price",
    }
    if category:
        params["category_ids"] = category  # kills keyword noise (e.g. iPhone "A3090")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": marketplace,
    }
    for attempt in range(retries):
        prepared = requests.Request(
            "GET", search_url, params=params, headers=headers
        ).prepare()
        if debug:
            print(f"  DEBUG request: {prepared.method} {prepared.url}")
        r = requests.Session().send(prepared, timeout=30)
        if r.status_code == 429:
            wait = 30 * (attempt + 1)
            print(f"  rate-limited, waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        data = r.json()
        if debug:
            print(
                f"  DEBUG response: total={data.get('total')} items={len(data.get('itemSummaries', []))}"
            )
            for d in (
                (data.get("refinement") or {}).get("itemCountDistributions") or []
            )[:8]:
                print(f"    distribution: {d.get('itemCount')}x {d.get('name')}")
        return data.get("itemSummaries", [])
    return []


def parse_item(it, query_name, marketplace, win_min=None, win_max=None):
    """Normalize one Browse API item summary.

    Field types vary between sandbox and production (and between item
    categories): `condition` may be an object ({conditionGroup,
    conditionDescription}) or a plain string ("New", "Gebraucht"...);
    `price` and `seller` are objects but guard them too. `win_min`/`win_max`
    carry the query's deal window into the CSV so the report can flag deals;
    `marketplace` records where the listing was found (multi-marketplace scans).
    """
    price = it.get("price")
    if not isinstance(price, dict):
        price = {}
    cond_obj = it.get("condition")
    if isinstance(cond_obj, dict):
        cond = (
            cond_obj.get("conditionGroup") or cond_obj.get("conditionDescription") or ""
        )
    else:
        cond = str(cond_obj or "")
    seller_obj = it.get("seller")
    seller = (
        seller_obj.get("username", "")
        if isinstance(seller_obj, dict)
        else str(seller_obj or "")
    )
    return {
        "query": query_name,
        "title": str(it.get("title") or "").strip(),
        "price": price.get("value", ""),
        "currency": price.get("currency", ""),
        "condition": cond,
        "seller": seller,
        "url": it.get("itemWebUrl", ""),
        "marketplace": marketplace,
        "win_min": "" if win_min is None else win_min,
        "win_max": "" if win_max is None else win_max,
    }


USED_CONDITIONS = {"USED", "Used", "Gebraucht", "Open box", "For parts or not working"}


def apply_local_filters(items, pmin, pmax, cond, currency="EUR"):
    """Belt-and-braces client-side enforcement of the deal window.

    The server-side filters (price/priceCurrency/conditions) are authoritative,
    but eBay has been observed to ignore malformed filters silently — so the
    script double-checks the currency, the price range, and the condition, and
    reports how many items were dropped and why.
    """
    kept = []
    dropped = {"currency": 0, "price": 0, "condition": 0}
    for it in items:
        price = it.get("price")
        if not isinstance(price, dict):
            price = {}
        item_currency = price.get("currency", "")
        if item_currency and item_currency != currency:
            dropped["currency"] += 1
            continue
        try:
            value = float(price.get("value", "nan"))
        except (TypeError, ValueError):
            value = float("nan")
        if not (pmin <= value <= pmax):
            dropped["price"] += 1
            continue
        cond_obj = it.get("condition")
        if isinstance(cond_obj, dict):
            group = cond_obj.get("conditionGroup", "")
            desc = cond_obj.get("conditionDescription", "")
        else:
            group, desc = "", str(cond_obj or "")
        if cond and group != cond and desc not in USED_CONDITIONS:
            dropped["condition"] += 1
            continue
        kept.append(it)
    return kept, dropped


def relay_search(
    relay, keyword, pmin, pmax, cond, category, marketplace, currency, limit, debug=False
):
    """Search through the local HTTP relay (ebay_relay.py) instead of direct HTTPS.

    The DSH sandbox blocks outbound HTTPS but allows loopback HTTP, so the relay
    (running in a normal terminal on the user's machine) performs the eBay calls
    and returns the raw response over plain HTTP.
    """
    params = {
        "keyword": keyword,
        "min": pmin,
        "max": pmax,
        "marketplace": marketplace,
        "currency": currency,
        "limit": limit,
    }
    if cond:
        params["condition"] = cond
    if category:
        params["category"] = category
    url = relay.rstrip("/") + "/search"
    r = requests.get(url, params=params, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"relay {relay} returned {r.status_code}: {r.text[:300]}")
    data = r.json()
    if debug:
        print(
            f"  DEBUG relay {relay}: total={data.get('total')} items={len(data.get('itemSummaries', []))}"
        )
    return data


CSV_FIELDS = [
    "query",
    "title",
    "price",
    "currency",
    "condition",
    "seller",
    "url",
    "marketplace",
    "win_min",
    "win_max",
]


def scan_marketplace(
    queries,
    client_id,
    client_secret,
    marketplace,
    currency,
    realm,
    demo=False,
    debug=False,
    relay=None,
):
    """Scan all queries on ONE marketplace; returns CSV row dicts."""
    print("=" * 70)
    if relay:
        print(f"REALM: RELAY — live listings via local relay {relay}")
        token_url = search_url = None
    elif realm == "sandbox":
        token_url, search_url = SANDBOX_TOKEN_URL, SANDBOX_SEARCH_URL
        print("REALM: SANDBOX (test data only — NOT real listings)")
    else:
        token_url, search_url = TOKEN_URL, SEARCH_URL
        print("REALM: PRODUCTION (live eBay listings)")
    print("=" * 70)
    if not relay and realm == "sandbox":
        print("WARNING: sandbox results are fabricated test items. Use this only to")
        print(
            "validate credentials/plumbing. Switch to production keys for real deals.\n"
        )
    if demo:
        token = None
        print("DEMO MODE — no API calls; sample items exercise parsing/CSV only.\n")
    elif relay:
        token = None
        print(f"Token: via relay — scanning {len(queries)} queries on {marketplace} ({currency})\n")
    else:
        token = get_token(client_id, client_secret, token_url)
        print(f"Token OK — scanning {len(queries)} queries on {marketplace} ({currency})\n")
    rows = []
    for q in queries:
        label = f"{q['name']}  ({q['min']}–{q['max']} {currency}, {q.get('cond', 'ANY')})"
        print(f"=== {label} ===")
        if demo:
            items = DEMO_ITEMS
        else:
            try:
                if relay:
                    data = relay_search(
                        relay,
                        q["q"],
                        q["min"],
                        q["max"],
                        q.get("cond"),
                        q.get("category"),
                        marketplace,
                        currency,
                        50,
                        debug=debug,
                    )
                    items = data.get("itemSummaries", [])
                else:
                    items = search(
                        token,
                        q["q"],
                        q["min"],
                        q["max"],
                        q.get("cond"),
                        q.get("category"),
                        marketplace,
                        currency,
                        50,
                        search_url,
                        debug=debug,
                    )
            except Exception as e:  # noqa: BLE001 - surface and continue
                print(f"  ERROR: {e}")
                continue
        items, dropped = apply_local_filters(
            items, q["min"], q["max"], q.get("cond"), currency=currency
        )
        if any(dropped.values()):
            print(
                f"  (local filter dropped {dropped['currency']} wrong-currency, "
                f"{dropped['price']} out-of-range, {dropped['condition']} wrong condition)"
            )
        for it in items:
            row = parse_item(it, q["name"], marketplace, q["min"], q["max"])
            rows.append(row)
            print(
                f"  {row['price']:>8} {row['currency']}  [{row['condition'][:11]:11}] {row['title'][:70]}"
            )
            print(f"           {row['url']}")
        time.sleep(1)
    return rows


def write_csv(rows, out_path):
    if rows:
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            w.writeheader()
            w.writerows(rows)
        print(f"\nSaved {len(rows)} results to {out_path}")
    else:
        print("\nNo results — check keywords/ranges or API quota.")


def main():
    # Windows consoles default to cp1252 and crash on emoji in item titles —
    # force UTF-8 with replacement so a single exotic title can't kill a scan.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="eBay Browse API deal scanner")
    parser.add_argument(
        "--keyword", help="single keyword search (skips default QUERIES)"
    )
    parser.add_argument("--min", type=float, help="min price")
    parser.add_argument("--max", type=float, help="max price")
    parser.add_argument("--condition", default="USED", help="NEW|USED|REFURBISHED")
    parser.add_argument(
        "--category",
        type=int,
        default=None,
        help="eBay category id (e.g. 27386 GPUs, 171957 desktops, 170083 RAM, 11210 server RAM)",
    )
    parser.add_argument("--marketplace", default="EBAY_DE")
    parser.add_argument(
        "--marketplaces",
        default=None,
        help="comma-separated list, e.g. EBAY_DE,EBAY_AT,EBAY_CH (overrides "
        "--marketplace and the EBAY_MARKETPLACES env var; each marketplace is "
        "scanned with its default currency)",
    )
    parser.add_argument(
        "--currency",
        default=None,
        help="price filter currency (default: EUR for EBAY_DE, or the "
        "marketplace's default in multi-marketplace mode)",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", default="ebay_deals.csv")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="run offline with sample items (no API calls; validates parsing/CSV)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print the exact request URL and response totals/refinements",
    )
    parser.add_argument(
        "--relay",
        default=None,
        help="search via local HTTP relay (ebay_relay.py), e.g. http://127.0.0.1:8787",
    )
    realm_group = parser.add_mutually_exclusive_group()
    realm_group.add_argument(
        "--sandbox",
        action="store_true",
        help="force SANDBOX endpoints (test data only)",
    )
    realm_group.add_argument(
        "--production",
        action="store_true",
        help="force PRODUCTION endpoints (live listings)",
    )
    args = parser.parse_args()

    load_env_file()
    client_id = os.environ.get("EBAY_CLIENT_ID", "")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
    if not (client_id and client_secret) and not args.demo and not args.relay:
        sys.exit("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET (env vars or ebay.env).")

    if args.relay:
        realm = "relay"
    elif args.sandbox:
        realm = "sandbox"
    elif args.production:
        realm = "production"
    else:
        realm = detect_realm(client_id, client_secret)
        print(
            f"(auto-detected realm from credentials: {realm.upper()}; "
            f"override with --sandbox/--production if wrong)"
        )

    if args.keyword:
        queries = [
            {
                "name": args.keyword,
                "q": args.keyword,
                "min": args.min if args.min is not None else 0,
                "max": args.max if args.max is not None else 100000,
                "cond": args.condition,
                "category": args.category,
            }
        ]
    else:
        queries = DEFAULT_QUERIES

    # Determine which marketplaces to scan (flag > env > single --marketplace).
    env_mps = os.environ.get("EBAY_MARKETPLACES", "").strip()
    if args.marketplaces:
        marketplaces = [m.strip() for m in args.marketplaces.split(",") if m.strip()]
    elif env_mps:
        marketplaces = [m.strip() for m in env_mps.split(",") if m.strip()]
    else:
        marketplaces = [args.marketplace]

    all_rows = []
    for mp in marketplaces:
        currency = args.currency or MARKETPLACE_CURRENCY.get(mp, "EUR")
        rows = scan_marketplace(
            queries,
            client_id,
            client_secret,
            mp,
            currency,
            realm,
            demo=args.demo,
            debug=args.debug,
            relay=args.relay,
        )
        all_rows.extend(rows)
    write_csv(all_rows, args.out)


if __name__ == "__main__":
    main()
