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

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SANDBOX_TOKEN_URL = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
SANDBOX_SEARCH_URL = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"

DEFAULT_QUERIES = [
    # --- GPUs >= 16 GB VRAM (category 27386 = Grafik-/Videokarten) ---
    {"name": "RTX 3090",          "q": "RTX 3090",         "min": 450,  "max": 750,  "cond": "USED", "category": 27386},
    {"name": "RTX 3090 Ti",       "q": "RTX 3090 Ti",      "min": 550,  "max": 850,  "cond": "USED", "category": 27386},
    {"name": "RTX 4070 Ti Super", "q": "RTX 4070 Ti Super", "min": 600, "max": 850,  "cond": "USED", "category": 27386},
    {"name": "RTX 4080 Super",    "q": "RTX 4080 Super",   "min": 650,  "max": 900,  "cond": "USED", "category": 27386},
    {"name": "Tesla P40",         "q": "Tesla P40",        "min": 100,  "max": 200,  "cond": "USED", "category": 27386},
    # Quadro RTX (Turing pro cards): RTX 5000 16GB €450–500, RTX 6000 24GB €799–840 (live 2026-08).
    # 24GB cheaper than a used 3090 — strong AI value pick.
    {"name": "Nvidia Quadro RTX", "q": "Quadro RTX",       "min": 400,  "max": 1000, "cond": "USED", "category": 27386},
    # --- Mini PCs (category 171957 = Desktops & All-in-One-PCs) ---
    {"name": "EliteDesk 800 G4 Mini", "q": "EliteDesk 800 G4 Mini", "min": 80,  "max": 180, "cond": "USED", "category": 171957},
    {"name": "EliteDesk 800 G5 Mini", "q": "EliteDesk 800 G5 Mini", "min": 100, "max": 200, "cond": "USED", "category": 171957},
    {"name": "OptiPlex 3070 Micro",   "q": "OptiPlex 3070 Micro",   "min": 80,  "max": 180, "cond": "USED", "category": 171957},
    {"name": "ThinkCentre M720q",     "q": "ThinkCentre M720q",     "min": 80,  "max": 180, "cond": "USED", "category": 171957},
    {"name": "ThinkCentre M920q",     "q": "ThinkCentre M920q",     "min": 100, "max": 200, "cond": "USED", "category": 171957},
    # --- RAM (11210 = Server-Speicher RAM for RDIMM; 170083 = Arbeitsspeicher RAM) ---
    {"name": "DDR4 RDIMM 32GB", "q": "DDR4 RDIMM 32GB", "min": 40,  "max": 120, "cond": "USED", "category": 11210},
    {"name": "DDR4 RDIMM 64GB", "q": "DDR4 RDIMM 64GB", "min": 80,  "max": 200, "cond": "USED", "category": 11210},
    {"name": "DDR5 32GB",       "q": "DDR5 32GB",       "min": 60,  "max": 150, "cond": "USED", "category": 170083},
    # --- AI hardware (new-wave products, probed live on eBay.de 2026-08) ---
    # DGX Spark: no used market yet — no condition filter so new listings are caught too.
    {"name": "Nvidia DGX Spark", "q": "DGX Spark", "min": 1800, "max": 3200, "cond": "", "category": 171957},
    # Strix Halo (Ryzen AI Max 395): NEW anchor = BOSGAME M5 128GB ≈ €1581–1700
    # (EU promo €1581; US $1699). Used listings on eBay.de at €2340–4625 are mostly
    # ABOVE new — only premium brands (HP Z2/ZBook, ASUS ROG Flow Z13) justify that.
    # Window set to catch anything priced below the new anchor (real used deals).
    {"name": "AMD Ryzen AI Max 395 (Strix Halo)", "q": "Ryzen AI Max 395", "min": 900, "max": 2000,
     "cond": "USED", "category": None},
    # Resold BOSGAME M5 units specifically — deal only if well below the €1581 new price.
    {"name": "BOSGAME M5 (Strix Halo)", "q": "BOSGAME M5", "min": 700, "max": 1500,
     "cond": "USED", "category": 171957},
    # --- Whole gaming PCs (value flips: the GPU alone is worth most of the price) ---
    {"name": "Gaming PC mit RTX 3090", "q": "Gaming PC RTX 3090", "min": 1200, "max": 2200, "cond": "USED", "category": 171957},
    {"name": "Gaming PC mit RTX 3080", "q": "Gaming PC RTX 3080", "min": 600,  "max": 1100, "cond": "USED", "category": 171957},
    # --- Build parts for the 2x RTX 3090 AI tower (X99 platform) ---
    {"name": "X99 Mainboard",   "q": "X99 Mainboard",   "min": 30, "max": 120, "cond": "USED", "category": 1244},
    {"name": "Xeon E5-2690v4",  "q": "Xeon E5-2690v4",  "min": 10, "max": 50,  "cond": "USED", "category": 164},
]


def load_env_file(paths=("ebay.env", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ebay.env"))):
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
    {"title": "EVGA GeForce RTX 3090 FTW3 ULTRA 24GB", "price": {"value": "649.00", "currency": "EUR"},
     "condition": "Used", "seller": {"username": "demo-seller-1"},
     "itemWebUrl": "https://www.ebay.de/itm/demo1"},
    # sandbox-style: condition as object
    {"title": "HP EliteDesk 800 G4 Mini i5-8500T 16GB 512GB", "price": {"value": "159.50", "currency": "EUR"},
     "condition": {"conditionGroup": "USED", "conditionDescription": "Used"}, "seller": {"username": "demo-seller-2"},
     "itemWebUrl": "https://www.ebay.de/itm/demo2"},
    # minimal item: missing fields must not crash
    {"title": "Samsung 32GB DDR4 RDIMM", "price": {"value": "89.99", "currency": "EUR"},
     "itemWebUrl": "https://www.ebay.de/itm/demo3"},
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


def search(token, keyword, pmin, pmax, cond, category, marketplace, limit, search_url, retries=3, debug=False):
    # NOTE: per the Browse API spec, the marketplace is set via the
    # X-EBAY-C-MARKETPLACE-ID HEADER (there is no marketplace_ids query param;
    # an unknown param is silently ignored and the API falls back to EBAY_US).
    # The price filter REQUIRES priceCurrency (error 12012) and condition
    # values take {BRACES} (e.g. conditions:{USED}).
    filters = [f"price:[{pmin}..{pmax}]", "priceCurrency:EUR"]
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
        prepared = requests.Request("GET", search_url, params=params, headers=headers).prepare()
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
            print(f"  DEBUG response: total={data.get('total')} items={len(data.get('itemSummaries', []))}")
            for d in ((data.get("refinement") or {}).get("itemCountDistributions") or [])[:8]:
                print(f"    distribution: {d.get('itemCount')}x {d.get('name')}")
        return data.get("itemSummaries", [])
    return []


def parse_item(it, query_name, win_min=None, win_max=None):
    """Normalize one Browse API item summary.

    Field types vary between sandbox and production (and between item
    categories): `condition` may be an object ({conditionGroup,
    conditionDescription}) or a plain string ("New", "Gebraucht"...);
    `price` and `seller` are objects but guard them too. `win_min`/`win_max`
    carry the query's deal window into the CSV so the report can flag deals.
    """
    price = it.get("price")
    if not isinstance(price, dict):
        price = {}
    cond_obj = it.get("condition")
    if isinstance(cond_obj, dict):
        cond = cond_obj.get("conditionGroup") or cond_obj.get("conditionDescription") or ""
    else:
        cond = str(cond_obj or "")
    seller_obj = it.get("seller")
    seller = seller_obj.get("username", "") if isinstance(seller_obj, dict) else str(seller_obj or "")
    return {
        "query": query_name,
        "title": str(it.get("title") or "").strip(),
        "price": price.get("value", ""),
        "currency": price.get("currency", ""),
        "condition": cond,
        "seller": seller,
        "url": it.get("itemWebUrl", ""),
        "win_min": "" if win_min is None else win_min,
        "win_max": "" if win_max is None else win_max,
    }


USED_CONDITIONS = {"USED", "Used", "Gebraucht", "Open box", "For parts or not working"}


def apply_local_filters(items, pmin, pmax, cond):
    """Belt-and-braces client-side enforcement of the deal window.

    The server-side filters (price/priceCurrency/conditions) are authoritative,
    but eBay has been observed to ignore malformed filters silently — so the
    script double-checks EUR currency, the price range, and the condition, and
    reports how many items were dropped and why.
    """
    kept = []
    dropped = {"currency": 0, "price": 0, "condition": 0}
    for it in items:
        price = it.get("price")
        if not isinstance(price, dict):
            price = {}
        currency = price.get("currency", "")
        if currency and currency != "EUR":
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


def relay_search(relay, keyword, pmin, pmax, cond, category, marketplace, limit, debug=False):
    """Search through the local HTTP relay (ebay_relay.py) instead of direct HTTPS.

    The DSH sandbox blocks outbound HTTPS but allows loopback HTTP, so the relay
    (running in a normal terminal on the user's machine) performs the eBay calls
    and returns the raw response over plain HTTP.
    """
    params = {"keyword": keyword, "min": pmin, "max": pmax, "marketplace": marketplace, "limit": limit}
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
        print(f"  DEBUG relay {relay}: total={data.get('total')} items={len(data.get('itemSummaries', []))}")
    return data


def run_queries(queries, client_id, client_secret, marketplace, out_path, realm, demo=False, debug=False, relay=None):
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
        print("validate credentials/plumbing. Switch to production keys for real deals.\n")
    if demo:
        token = None
        print("DEMO MODE — no API calls; sample items exercise parsing/CSV only.\n")
    elif relay:
        token = None
        print(f"Token: via relay — scanning {len(queries)} queries on {marketplace}\n")
    else:
        token = get_token(client_id, client_secret, token_url)
        print(f"Token OK — scanning {len(queries)} queries on {marketplace}\n")
    rows = []
    for q in queries:
        label = f"{q['name']}  ({q['min']}–{q['max']} €, {q.get('cond', 'ANY')})"
        print(f"=== {label} ===")
        if demo:
            items = DEMO_ITEMS
        else:
            try:
                if relay:
                    data = relay_search(relay, q["q"], q["min"], q["max"], q.get("cond"), q.get("category"),
                                        marketplace, 50, debug=debug)
                    items = data.get("itemSummaries", [])
                else:
                    items = search(token, q["q"], q["min"], q["max"], q.get("cond"), q.get("category"),
                                   marketplace, 50, search_url, debug=debug)
            except Exception as e:  # noqa: BLE001 - surface and continue
                print(f"  ERROR: {e}")
                continue
        items, dropped = apply_local_filters(items, q["min"], q["max"], q.get("cond"))
        if any(dropped.values()):
            print(f"  (local filter dropped {dropped['currency']} non-EUR, "
                  f"{dropped['price']} out-of-range, {dropped['condition']} wrong condition)")
        for it in items:
            row = parse_item(it, q["name"], q["min"], q["max"])
            rows.append(row)
            print(f"  {row['price']:>8} {row['currency']}  [{row['condition'][:11]:11}] {row['title'][:70]}")
            print(f"           {row['url']}")
        time.sleep(1)
    if rows:
        fields = ["query", "title", "price", "currency", "condition", "seller", "url", "win_min", "win_max"]
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
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
    parser.add_argument("--keyword", help="single keyword search (skips default QUERIES)")
    parser.add_argument("--min", type=float, help="min price")
    parser.add_argument("--max", type=float, help="max price")
    parser.add_argument("--condition", default="USED", help="NEW|USED|REFURBISHED")
    parser.add_argument("--category", type=int, default=None,
                        help="eBay category id (e.g. 27386 GPUs, 171957 desktops, 170083 RAM, 11210 server RAM)")
    parser.add_argument("--marketplace", default="EBAY_DE")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", default="ebay_deals.csv")
    parser.add_argument("--demo", action="store_true",
                        help="run offline with sample items (no API calls; validates parsing/CSV)")
    parser.add_argument("--debug", action="store_true",
                        help="print the exact request URL and response totals/refinements")
    parser.add_argument("--relay", default=None,
                        help="search via local HTTP relay (ebay_relay.py), e.g. http://127.0.0.1:8787")
    realm_group = parser.add_mutually_exclusive_group()
    realm_group.add_argument("--sandbox", action="store_true",
                             help="force SANDBOX endpoints (test data only)")
    realm_group.add_argument("--production", action="store_true",
                             help="force PRODUCTION endpoints (live listings)")
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
        print(f"(auto-detected realm from credentials: {realm.upper()}; "
              f"override with --sandbox/--production if wrong)")

    if args.keyword:
        queries = [{"name": args.keyword, "q": args.keyword,
                    "min": args.min if args.min is not None else 0,
                    "max": args.max if args.max is not None else 100000,
                    "cond": args.condition,
                    "category": args.category}]
    else:
        queries = DEFAULT_QUERIES
    run_queries(queries, client_id, client_secret, args.marketplace, args.out, realm,
                demo=args.demo, debug=args.debug, relay=args.relay)


if __name__ == "__main__":
    main()
