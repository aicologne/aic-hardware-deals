#!/usr/bin/env python3
"""
Facebook Marketplace — country/city-aware search-link generator.

Facebook has NO public Marketplace API (see SKILL.md "Limitations"), so this
tool does not fetch listings. What it does: build the exact deep links
Marketplace understands (same pattern as the verified URL
https://www.facebook.com/marketplace/cologne/search/?query=rtx%205070&exact=false&radius=65)
for any country / city / keyword / price window, so a human (or agent) can
open each market in one click. It is fully offline — no credentials, no
network, no ToS issues. Scraping Facebook is a separate matter we do not do.

Examples:
  # the URL the user pasted, rebuilt with a price window:
  python fb_marketplace.py --country DE --city cologne --query "RTX 5070" \
      --exact --radius 65 --min 500 --max 900

  # every registered city in Germany:
  python fb_marketplace.py --country DE --city all --query "RTX 3090" --max 1100

  # default city of several countries at once (EU scan):
  python fb_marketplace.py --countries DE,AT,CH --query "EliteDesk 800 G4" --max 200

  # no location at all -> Marketplace uses the account's saved location:
  python fb_marketplace.py --query "RTX 5070" --radius 100 --no-location

  # open every link in the default browser:
  python fb_marketplace.py --country DE --city all --query "DDR4 RDIMM 32GB" --open

  # write a markdown report:
  python fb_marketplace.py --countries DE,AT,CH --query "RTX 5070" \
      --report fb_marketplace_links.md

  # list the supported countries / cities:
  python fb_marketplace.py --list

  # glean info from an existing Marketplace link (offline, no page fetch):
  python fb_marketplace.py --parse "https://www.facebook.com/marketplace/cologne/search/?query=rtx%205070&exact=false&radius=65&minPrice=500&maxPrice=900"
  python fb_marketplace.py --parse "https://www.facebook.com/marketplace/item/1234567890/"

  # watchlist: turn links you pasted from your OWN browsing into a deduped,
  # first/last-seen watchlist (offline parsing only — no automated FB access):
  python fb_marketplace.py --collect collected_links.txt \
      --state watchlist_state.json --out watchlist.csv --report watchlist.md
"""

import argparse
import csv
import io
import json
import os
import sys
import webbrowser
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse

from cities import (
    ORDER,
    cities_for,
    country,
    currency_for,
    default_city,
    name_for,
)

SORT_CHOICES = {
    "ranking": "overall_search_ranking",   # default relevance
    "newest": "newest_listing",
    "price-asc": "price_ascend",
    "price-desc": "price_descend",
}
DELIVERY_CHOICES = {
    "local": "local_shipping",
    "meetup": "meetup",
    "pickup": "pickup",
}

BASE = "https://www.facebook.com/marketplace"


def slugify(location):
    """Normalize a location to the single-token slug convention.

    'New York' -> 'newyork', 'München' -> 'munchen', 'Düsseldorf' ->
    'duesseldorf'. NOTE: the registry already ships the slug Facebook actually
    resolves ('cologne', 'munich', 'vienna', ...); this is only a fallback for
    ad-hoc --city values, so the printed URL is still clickable even if the
    slug differs from the registry.
    """
    s = location.lower().strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return "".join(ch for ch in s if ch.isalnum())


def build_url(
    query,
    location=None,
    exact=None,
    radius=None,
    min_price=None,
    max_price=None,
    sort_by=None,
    days=None,
    delivery=None,
):
    """Build one Facebook Marketplace search deep link.

    `location` is the city slug (or None for the location-less URL that uses
    the account's saved location). All other parameters map 1:1 to the query
    string Marketplace understands; unknown/renamed params are simply ignored
    by Facebook, so a stale slug or param degrades gracefully to a working
    search page.
    """
    if location:
        url = f"{BASE}/{slugify(location)}/search/"
    else:
        url = f"{BASE}/search/"
    params = {"query": query}
    if exact is not None:
        params["exact"] = "true" if exact else "false"
    if radius:
        params["radius"] = str(int(radius))
    if min_price:
        params["minPrice"] = str(int(min_price))
    if max_price:
        params["maxPrice"] = str(int(max_price))
    if sort_by:
        params["sortBy"] = SORT_CHOICES[sort_by]
    if days:
        params["daysSinceListed"] = str(int(days))
    if delivery:
        params["deliveryMethod"] = DELIVERY_CHOICES[delivery]
    return url + "?" + urlencode(params)


# Query params we recognize, mapped to friendly names (both spellings of the
# keyword param occur in the wild). Anything else is passed through verbatim.
KNOWN_PARAMS = {
    "query": "keyword",
    "search_query": "keyword",
    "exact": "exact",
    "radius": "radius_km",
    "minPrice": "min_price",
    "maxPrice": "max_price",
    "sortBy": "sort_by",
    "daysSinceListed": "days_since_listed",
    "deliveryMethod": "delivery_method",
    "category_id": "category_id",
    "latitude": "latitude",
    "longitude": "longitude",
}


def parse_url(url):
    """Extract every piece of info that is *in the link itself* (offline).

    Works on search links (.../marketplace/{location}/search/?query=...),
    category links (.../marketplace/{location}/category/{id}/) and single-item
    links (.../marketplace/item/{id}/). Pure URL parsing — no network, no page
    fetch, no ToS issues.

    What is deliberately NOT here: listing titles/prices/sellers — that data
    only exists on Facebook's page, and fetching it is scraping (see
    SKILL.md §7). The URL tells you *what the search is configured to find*,
    not *what it found*.
    """
    p = urlparse(url)
    segments = [s for s in p.path.split("/") if s]
    info = {"domain": p.netloc, "path": p.path}
    if len(segments) >= 2 and segments[0] == "marketplace":
        rest = segments[1:]
        if "item" in rest:
            info["type"] = "item"
            info["item_id"] = rest[rest.index("item") + 1]
        elif "search" in rest:
            info["type"] = "search"
            location = rest[: rest.index("search")]
            info["location"] = "/".join(location) if location else None
        elif "category" in rest:
            info["type"] = "category"
            info["category_id"] = rest[rest.index("category") + 1]
            location = rest[: rest.index("category")]
            info["location"] = "/".join(location) if location else None
        else:
            info["type"] = "marketplace"
    qs = parse_qs(p.query)
    for key, values in qs.items():
        name = KNOWN_PARAMS.get(key, key)
        info[name] = values[0] if len(values) == 1 else values
    return info


def print_parsed(url):
    """Pretty-print the structured info gleaned from one Marketplace URL."""
    info = parse_url(url)
    print(f"URL: {url}")
    for key, value in info.items():
        print(f"  {key:<18} {value}")


# --- watchlist ("bring your own browsing") -----------------------------------
# The user browses Marketplace in their own browser (normal use), then pastes
# the links they found into a file the repo commits. The collector only parses
# those URLs offline and tracks first/last-seen — no automated request to
# facebook.com ever happens (see SKILL.md §7).

WATCHLIST_FIELDS = [
    "first_seen", "last_seen", "type", "item_id", "location", "keyword",
    "min_price", "max_price", "radius_km", "url", "note",
]

SEARCH_CSV_FIELDS = [
    "query", "country", "country_name", "currency", "city", "url",
]


def read_collected_links(path):
    """Read a user-maintained list of Marketplace links.

    Two formats:
      .csv -> header `url` plus optional `note` (one row per link)
      else -> one URL per line; blank lines, '#' comments and inline
              ' #...' comments are ignored; a leading BOM is stripped
    """
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    entries = []
    if path.lower().endswith(".csv"):
        for row in csv.DictReader(io.StringIO(text)):
            url = (row.get("url") or "").strip()
            if url:
                entries.append((url, (row.get("note") or "").strip()))
    else:
        for line in text.splitlines():
            line = line.split(" #")[0].strip()  # inline comments: ' #...'
            if not line or line.startswith("#"):
                continue
            entries.append((line, ""))
    return entries


def watchlist_key(info, url):
    """Stable dedupe key: item links key on the item ID, searches on
    location+keyword, categories on location+category id."""
    if info.get("type") == "item":
        return f"item:{info.get('item_id') or url}"
    if info.get("type") == "category":
        return f"category:{info.get('location') or ''}:{info.get('category_id') or ''}"
    if info.get("type") == "search":
        return f"search:{info.get('location') or ''}:{info.get('keyword') or ''}"
    return f"url:{url}"


def collect_links(input_path, state_path, out_csv, out_md=None, today=None):
    """Turn user-pasted Marketplace links into a deduped watchlist.

    State (JSON) persists across runs so `first_seen` is preserved while
    `last_seen` advances; the CSV/report contain only the ACTIVE watchlist
    (links present in the current input).
    """
    today = today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = read_collected_links(input_path)
    print(f"collected {len(entries)} link(s) from {input_path}")
    state = {}
    if state_path and os.path.exists(state_path):
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            print(f"WARNING: could not read {state_path} — starting fresh")
            state = {}
    kept, skipped, new_count = [], [], 0
    seen_keys = set()
    for url, note in entries:
        info = parse_url(url)
        domain = info.get("domain", "").lower()
        if domain not in ("www.facebook.com", "facebook.com", "m.facebook.com") \
                or "marketplace" not in info.get("path", ""):
            skipped.append(url)
            continue
        key = watchlist_key(info, url)
        if key in seen_keys:
            continue  # duplicate within this input — already collected
        seen_keys.add(key)
        rec = dict(state.get(key) or {})
        if not rec.get("first_seen"):
            rec["first_seen"] = today
            new_count += 1
        rec["last_seen"] = today
        rec["url"] = url
        if note:
            rec["note"] = note
        for field in ("type", "item_id", "location", "keyword",
                      "min_price", "max_price", "radius_km"):
            v = info.get(field)
            if v not in (None, ""):
                rec[field] = v
        state[key] = rec
        kept.append(rec)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    kept.sort(key=lambda r: r.get("first_seen", ""), reverse=True)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=WATCHLIST_FIELDS, extrasaction="ignore")
        w.writeheader()
        for rec in kept:
            w.writerow({k: rec.get(k, "") for k in WATCHLIST_FIELDS})
    print(f"saved {len(kept)} active watchlist row(s) to {out_csv} ({new_count} new today)")
    if skipped:
        print(f"WARNING: skipped {len(skipped)} non-Marketplace URL(s):")
        for u in skipped[:5]:
            print(f"  {u}")
    if out_md:
        write_watchlist_md(kept, out_md)
        print(f"saved watchlist report to {out_md}")


def write_watchlist_md(rows, out_md):
    """Small markdown watchlist report for the site (deep links only)."""
    lines = ["# Facebook Marketplace — watchlist", ""]
    lines.append(
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · links "
        "pasted from your own browsing · deep links only — no scraping._"
    )
    lines.append("")
    if not rows:
        lines.append("_Empty watchlist — paste links into `collected_links.txt`._")
    items = [r for r in rows if r.get("type") == "item"]
    searches = [r for r in rows if r.get("type") != "item"]
    if items:
        lines.append("## Items you're following")
        lines.append("")
        for r in items:
            note = f" — {r['note']}" if r.get("note") else ""
            seen = f"seen {r.get('first_seen')} → {r.get('last_seen')}"
            label = r.get("item_id") or r.get("url")
            lines.append(f"- [{label}]({r.get('url')}){note} · {seen}")
        lines.append("")
    if searches:
        lines.append("## Searches you're tracking")
        lines.append("")
        for r in searches:
            loc = r.get("location") or "(saved location)"
            kw = r.get("keyword") or ""
            note = f" — {r['note']}" if r.get("note") else ""
            lines.append(f"- **{kw}** @ {loc} — [{r.get('url')}]({r.get('url')}){note}")
        lines.append("")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def append_search_csv(path, query, code, city, url):
    """Append one (query, country, city, url) row to the combined searches CSV.

    The header is written only when the file does not exist yet, so the nightly
    workflow can call this once per link sheet and end up with ONE file
    containing every sheet. Fully offline.
    """
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SEARCH_CSV_FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({
            "query": query,
            "country": code,
            "country_name": name_for(code),
            "currency": currency_for(code),
            "city": city or "(saved location)",
            "url": url,
        })


def describe_filters(args):
    """Human-readable description of the active filters (for the report)."""
    bits = [f"query={args.query!r}"]
    if args.exact:
        bits.append("exact phrase")
    if args.radius:
        bits.append(f"radius {args.radius} km")
    if args.min:
        bits.append(f"min {args.min}")
    if args.max:
        bits.append(f"max {args.max}")
    if args.sort:
        bits.append(f"sort {args.sort}")
    if args.days:
        bits.append(f"listed within {args.days} days")
    if args.delivery:
        bits.append(f"delivery {args.delivery}")
    return ", ".join(bits)


def resolve_targets(args):
    """Return [(country_code, city_slug_or_None), ...] to generate links for.

    --city all  -> every registered city of the country/countries
    --city X    -> X for each country (when used with --countries)
    --no-location -> one location-less link per country (uses saved location)
    default     -> each country's default city
    """
    codes = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    targets = []
    for code in codes:
        if not country(code):
            print(f"WARNING: unknown country code '{code}' — skipped (see --list)")
            continue
        if args.no_location:
            targets.append((code, None))
        elif args.city and args.city.lower() != "all":
            targets.append((code, args.city))
        elif args.city and args.city.lower() == "all":
            for city in cities_for(code):
                targets.append((code, city))
        else:
            targets.append((code, default_city(code)))
    return targets


def render_markdown(targets, args):
    """Render a markdown report with one section per country."""
    lines = []
    lines.append(f"# Facebook Marketplace — {args.query}")
    lines.append("")
    lines.append(f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · "
                 f"filters: {describe_filters(args)} · deep links only — "
                 "open each in a logged-in browser._")
    lines.append("")
    last_code = None
    for code, city in targets:
        if code != last_code:
            lines.append(f"## {name_for(code)} ({code}) — {currency_for(code)}")
            lines.append("")
            last_code = code
        url = build_url(
            args.query,
            location=city,
            exact=args.exact,
            radius=args.radius,
            min_price=args.min,
            max_price=args.max,
            sort_by=args.sort,
            days=args.days,
            delivery=args.delivery,
        )
        label = city or "(saved location)"
        lines.append(f"- **{label}**: [{url}]({url})")
    lines.append("")
    lines.append("_Prices are shown by Marketplace in the local currency "
                 "(see country headers). Radius/sort/delivery params are "
                 "best-effort — Facebook may ignore or rename them._")
    lines.append("")
    return "\n".join(lines)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Facebook Marketplace country/city search-link generator "
                    "(deep links only — no API, no scraping)"
    )
    parser.add_argument("--query", help="search keyword (required unless --list)")
    parser.add_argument(
        "--country", default="DE",
        help="country code for a single-country scan (default DE); "
             "--countries overrides this",
    )
    parser.add_argument(
        "--countries",
        help="comma-separated country codes, e.g. DE,AT,CH (each scanned with "
             "its default city unless --city is given)",
    )
    parser.add_argument(
        "--city", default=None,
        help="city slug (e.g. cologne, london, paris); 'all' = every "
             "registered city; omit = the country's default city",
    )
    parser.add_argument(
        "--no-location", action="store_true",
        help="omit the city slug -> Marketplace uses the account's saved "
             "location (fallback when slugs stop resolving)",
    )
    parser.add_argument("--exact", action="store_true", help="exact phrase match")
    parser.add_argument("--radius", type=int, default=65, help="radius in km (0-500)")
    parser.add_argument("--min", type=int, help="minimum price (local currency)")
    parser.add_argument("--max", type=int, help="maximum price (local currency)")
    parser.add_argument(
        "--sort", choices=list(SORT_CHOICES),
        help="sort order: ranking|newest|price-asc|price-desc",
    )
    parser.add_argument(
        "--days", type=int, choices=[1, 7, 30],
        help="only listings listed within N days",
    )
    parser.add_argument(
        "--delivery", choices=list(DELIVERY_CHOICES),
        help="delivery method: local|meetup|pickup",
    )
    parser.add_argument(
        "--open", action="store_true",
        help="open every generated link in the default browser",
    )
    parser.add_argument(
        "--report", default=None,
        help="write a markdown report to this path (e.g. fb_marketplace_links.md)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="print the supported countries/cities and exit",
    )
    parser.add_argument(
        "--parse", nargs="+", metavar="URL",
        help="parse one or more existing Marketplace URLs into structured "
             "info (keyword, location, radius, prices, sort, days, delivery, "
             "item_id...) — fully offline, no page fetch; then exit",
    )
    parser.add_argument(
        "--collect", metavar="FILE",
        help="build a watchlist from a user-pasted links file (.txt: one URL "
             "per line, '#' comments; .csv: url[,note]) — offline parsing "
             "only; no automated access to facebook.com (see SKILL.md §7)",
    )
    parser.add_argument(
        "--state", default="watchlist_state.json",
        help="watchlist state file (JSON, tracks first/last seen; default "
             "watchlist_state.json)",
    )
    parser.add_argument(
        "--out", default="watchlist.csv",
        help="watchlist CSV output (default watchlist.csv)",
    )
    parser.add_argument(
        "--csv", default=None,
        help="append each generated search link as a row to this CSV "
             "(header written once; used by the nightly workflow to build "
             "site/data/marketplace/searches.csv)",
    )
    args = parser.parse_args()

    if args.list:
        print(f"{'Code':<5}{'Country':<16}{'Currency':<9}Default city  Cities")
        print("-" * 80)
        for code in ORDER:
            entry = country(code)
            print(f"{code:<5}{entry['name']:<16}{entry['currency']:<9}"
                  f"{entry['default_city']:<14}{', '.join(entry['cities'])}")
        return

    if args.collect:
        collect_links(args.collect, args.state, args.out, args.report)
        return

    if args.parse:
        for url in args.parse:
            print_parsed(url)
            print()
        return

    if not args.query:
        parser.error("--query is required (or use --list)")

    # --countries wins over --country; --no-location wins over --city.
    if args.countries:
        codes = args.countries
    else:
        codes = args.country

    targets = resolve_targets(
        argparse.Namespace(
            countries=codes,
            city=args.city,
            no_location=args.no_location,
        )
    )
    if not targets:
        sys.exit("No valid country codes — check --country/--countries (see --list).")

    print(f"Facebook Marketplace — {describe_filters(args)}")
    print("=" * 72)
    last_code = None
    for code, city in targets:
        if code != last_code:
            print(f"\n[{code}] {name_for(code)} ({currency_for(code)})")
            last_code = code
        url = build_url(
            args.query,
            location=city,
            exact=args.exact,
            radius=args.radius,
            min_price=args.min,
            max_price=args.max,
            sort_by=args.sort,
            days=args.days,
            delivery=args.delivery,
        )
        label = city or "(saved location)"
        print(f"  {label:<20} {url}")
        if args.csv:
            append_search_csv(args.csv, args.query, code, city, url)
        if args.open:
            webbrowser.open(url)

    if args.csv:
        print(f"\nAppended {len(targets)} row(s) to {args.csv}")

    if args.report:
        md = render_markdown(targets, args)
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\nSaved {len(targets)} links to {args.report}")


if __name__ == "__main__":
    main()
