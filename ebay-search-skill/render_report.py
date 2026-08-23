#!/usr/bin/env python3
"""Render ebay_deals.csv into LATEST.md — the final price report.

The report is the product: it combines the latest scan with the deal windows
(carried in the CSV as win_min/win_max), flags items at/below the buy-low
target, shows per-category medians, a 30-day median trend and recent movers
(from site/data/history.csv), per-listing repricing notes (from
site/data/listing_history.csv), €/GB value metrics, and ends with methodology.

Usage:
    python render_report.py [ebay_deals.csv] [LATEST.md] [site/data/history.csv]
"""
import csv
import datetime
import os
import statistics
import sys

DEFAULT_MARKETPLACE = "EBAY_DE"

# Capacity used for the €/GB column. Only categories with an unambiguous
# capacity get a value; mixed categories (e.g. Quadro RTX 8/16/24 GB) are "—".
CAPACITY_GB = {
    "RTX 3090": 24,
    "RTX 3090 Ti": 24,
    "RTX 4070 Ti Super": 16,
    "RTX 4080 Super": 16,
    "RTX 5070 16GB": 16,
    "RTX 5060": 16,
    "RTX 4060 Ti 16GB": 16,
    "Tesla P40": 24,
    "Tesla T4": 16,
    "Radeon PRO W7800": 32,
    "Radeon PRO W7900": 48,
    "DDR4 RDIMM 32GB": 32,
    "DDR4 RDIMM 64GB": 64,
    "DDR5 32GB": 32,
    "DDR5 RDIMM": 32,
}

# eBay seller fee rate (of the gross price), used for the Net column. Override
# via EBAY_FEE_RATE (e.g. "0.13"); set to "0" to hide the column.
FEE_RATE = float(os.environ.get("EBAY_FEE_RATE", "0.13"))

MARKET_CONTEXT = (
    "**Market context (2026):** the DRAM/GDDR shortage keeps used prices elevated. "
    "Used RTX 3090s ask €1000–1500 on eBay.de; DDR5 German retail is ~4.2–4.5× its "
    "July-2025 level; DDR4 RDIMM shops ask €219–230 for 32 GB while private sellers "
    "still move pre-shortage stock at €60–120. Note the new-price anchors: a BOSGAME M5 "
    "(Strix Halo, 128 GB) costs €1581–1700 new — used Strix Halo above that is not a deal. "
    "Verify everything live — prices move weekly."
)

FOOTNOTES = [
    "Prices are asking prices from active listings (used), collected by the Browse API.",
    "Buy-low targets are the scan windows (static fallback, refined adaptively from the last 30 days of price history); a listing within 15 % of the target is flagged 🔥.",
    "Net = asking price minus the ~13 % eBay seller fee — subtract shipping and your own costs too.",
    "Condition and warranty are the seller's; always verify photos, GPU-Z/memtest results, and seller feedback before paying.",
    "€/GB is price ÷ capacity of the scan category (e.g. 32 GB RDIMM, 24 GB RTX 3090); mixed-capacity categories show —.",
    "Sold median (when present) comes from eBay's public 'Verkauft' search — a best-effort resale anchor, not the Browse API; sample size matters.",
    "In multi-marketplace mode, scan windows are interpreted in each marketplace's currency.",
]


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def euro(value):
    if value is None:
        return "—"
    return f"€{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def net_euro(price):
    """Net asking price after the eBay seller fee (None -> "—")."""
    if price is None or FEE_RATE <= 0:
        return "—"
    return euro(price * (1 - FEE_RATE))


def load_sold_anchors(path):
    """sold_anchors.csv -> {query: {"median_sold": float, "sample_size": int}}."""
    if not path or not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            median = num(r.get("median_sold"))
            if median is None:
                continue
            try:
                n = int(float(r.get("sample_size") or 0))
            except (TypeError, ValueError):
                n = 0
            out[r.get("query")] = {"median_sold": median, "sample_size": n}
    return out


def pct(value):
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:,.1f} %".replace(",", "X").replace(".", ",").replace("X", ".")


def flag_for(row):
    price = row["_price"]
    wmin = row.get("_win_min")
    wmax = row.get("_win_max")
    if wmin is not None and price <= wmin * 1.15:
        return "🔥 at/near buy-low target"
    if wmax is not None and price > wmax:
        return "⚠️ above scan window"
    return "ok"


def capacity_gb(query):
    return CAPACITY_GB.get(query)


def euro_per_gb(price, query):
    cap = capacity_gb(query)
    if price is None or cap is None:
        return None
    return price / cap


def euro_per_gb_str(price, query):
    v = euro_per_gb(price, query)
    if v is None:
        return "—"
    return f"{v:,.2f}/GB".replace(",", "X").replace(".", ",").replace("X", ".")


def load_history(path):
    """history.csv -> {composite_key: [(date, median), ...]} sorted by date (last 30 days)."""
    if not path or not os.path.exists(path):
        return {}
    by_key = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            median = num(r.get("median"))
            if median is None:
                continue
            mp = (r.get("marketplace") or DEFAULT_MARKETPLACE).strip()
            key = f"{mp} · {r['query']}"
            by_key.setdefault(key, []).append((r.get("date"), median))
    out = {}
    for key, points in by_key.items():
        points.sort(key=lambda p: p[0])
        out[key] = points[-30:]
    return out


def trend_str(history, key):
    """'€85→€120 (14 days)' for the last-30-day median series, or None."""
    points = history.get(key) or []
    if len(points) < 2:
        return None
    return f"{euro(points[0][1])}→{euro(points[-1][1])} ({len(points)}d)"


def movers(history):
    """Recent median movers: [(key, latest, ref, ref_date, delta_pct)] sorted by |delta| desc.

    Reference = the earliest scan at-or-after 7 days before the latest scan
    (falls back to the previous scan for fresh history).
    """
    out = []
    today = datetime.date.today()
    for key, points in history.items():
        if len(points) < 2:
            continue
        latest_date_str, latest = points[-1]
        try:
            latest_date = datetime.date.fromisoformat(latest_date_str)
        except ValueError:
            latest_date = today
        threshold = latest_date - datetime.timedelta(days=7)
        ref, ref_date = None, None
        for d, m in points[:-1]:
            try:
                dd = datetime.date.fromisoformat(d)
            except ValueError:
                continue
            if dd >= threshold:  # earliest point at-or-after 7 days ago
                ref, ref_date = m, d
                break
        if ref is None:  # fall back to the previous point
            ref, ref_date = points[-2][1], points[-2][0]
        if ref <= 0:
            continue
        delta = (latest - ref) / ref * 100.0
        out.append((key, latest, ref, ref_date, delta))
    out.sort(key=lambda t: abs(t[4]), reverse=True)
    return out


def load_listing_history(path):
    """listing_history.csv -> {url: row} for repricing notes."""
    if not path or not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[r.get("url")] = r
    return out


def repriced_note(row, listing_history):
    """'was €X on YYYY-MM-DD' when the listing was seen before at a different price."""
    lh = listing_history.get(row.get("url"))
    if not lh:
        return ""
    first_price = num(lh.get("first_price"))
    last_price = num(lh.get("last_price"))
    if first_price is None or last_price is None or first_price == last_price:
        return ""
    return f"was {euro(first_price)} on {lh.get('first_seen')}"


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "ebay_deals.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "LATEST.md"
    history_path = sys.argv[3] if len(sys.argv) > 3 else None
    listing_path = sys.argv[4] if len(sys.argv) > 4 else "site/data/listing_history.csv"
    sold_path = sys.argv[5] if len(sys.argv) > 5 else "sold_anchors.csv"
    history = load_history(history_path)
    listing_history = load_listing_history(listing_path)
    sold_anchors = load_sold_anchors(sold_path)

    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["_price"] = num(r.get("price"))
            r["_win_min"] = num(r.get("win_min"))
            r["_win_max"] = num(r.get("win_max"))
            r["_mp"] = (r.get("marketplace") or DEFAULT_MARKETPLACE).strip()
            if r["_price"] is not None:
                rows.append(r)

    marketplaces = sorted({r["_mp"] for r in rows})
    multi = len(marketplaces) > 1
    currencies = sorted({r.get("currency") for r in rows if r.get("currency")})

    def group_key(r):
        return f"{r['_mp']} · {r['query']}"

    def display_name(key):
        return key if multi else key.partition(" · ")[2]

    groups = {}
    for r in rows:
        groups.setdefault(group_key(r), []).append(r)
    keys = sorted(groups)

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mps_str = "marketplace " + ", ".join(marketplaces) if not multi else "marketplaces " + ", ".join(marketplaces)
    cur_str = ", ".join(currencies) if currencies else "EUR"

    # --- aggregate index: mean of per-key median deltas ----------------------
    mv = movers(history)
    index_pct = None
    if mv:
        index_pct = sum(t[4] for t in mv) / len(mv)

    net_label = f"Net (−{FEE_RATE * 100:.0f} %)" if FEE_RATE > 0 else None

    L = []  # output lines
    L.append("# 🛒 eBay.de Used Hardware — Price Report")
    L.append("")
    index_part = f" · index **{pct(index_pct)}**" if index_pct is not None else ""
    L.append(f"_Generated {now} · {len(rows)} items across {len(keys)} categories · "
             f"{mps_str} · used · {cur_str}{index_part}_")
    L.append("")
    L.append(MARKET_CONTEXT)
    L.append("")

    # --- deal highlights -------------------------------------------------
    L.append("## 🔥 Deal highlights")
    L.append("")
    flagged = [r for r in rows if flag_for(r) == "🔥 at/near buy-low target"]
    if flagged:
        flagged.sort(key=lambda r: r["_price"])
        L.append("Listings currently **at or within 15 % of the buy-low target** — the "
                 "shortlist to inspect first:")
        L.append("")
        headers = ["Category", "Price", "Buy-low target", "Title", "Seller", "Note"]
        if net_label:
            headers.insert(2, net_label)
        if multi:
            headers.insert(0, "Mkt")
        L.append("| " + " | ".join(headers) + " |")
        L.append("|" + "---|" * len(headers))
        for r in flagged:
            target = euro(r["_win_min"])
            title = (r["title"] or "").replace("|", "\\|")
            note = repriced_note(r, listing_history)
            if not note:
                note = "🔥 at/near buy-low target"
            cells = [r["query"], f"**{euro(r['_price'])}**"]
            if net_label:
                cells.append(net_euro(r["_price"]))
            cells += [target, f"[{title}]({r.get('url') or ''})", r["seller"], note]
            if multi:
                cells.insert(0, r["_mp"])
            L.append("| " + " | ".join(cells) + " |")
        L.append("")
    else:
        L.append("No listings currently sit at the buy-low targets. Check back after the "
                 "next nightly scan, or widen the windows in `ebay_search.py`.")
        L.append("")

    # --- median movers + market index ------------------------------------
    if mv:
        L.append("## 📊 Used-market index & movers")
        L.append("")
        L.append(f"**Market index: {pct(index_pct)}** — mean change of {len(mv)} "
                 f"category medians vs. their reference scan (~7 days back). "
                 f"Positive = market heating up (shortage pressure); negative = cooling.")
        L.append("")
        risers = [t for t in mv if t[4] > 0][:5]
        fallers = [t for t in mv if t[4] < 0][:5]
        if risers or fallers:
            for label, items in (("Risers", risers), ("Fallers", fallers)):
                if not items:
                    continue
                L.append(f"**{label}**")
                L.append("")
                L.append("| Category | Latest median | Reference | Change |")
                L.append("|---|---|---|---|")
                for key, latest, ref, ref_date, delta in items:
                    L.append(f"| {display_name(key)} | **{euro(latest)}** | {euro(ref)} "
                             f"({ref_date}) | **{pct(delta)}** |")
                L.append("")
            L.append("")

    # --- per-category reports ---------------------------------------------
    has_capacity = any(capacity_gb(k.partition(" · ")[2]) for k in keys)
    for key in keys:
        qrows = [r for r in groups[key]]
        qrows.sort(key=lambda r: r["_price"])
        prices = [r["_price"] for r in qrows]
        median = statistics.median(prices)
        cheapest = qrows[0]
        at_target = sum(1 for r in qrows if flag_for(r) == "🔥 at/near buy-low target")
        wmin = qrows[0].get("_win_min")
        wmax = qrows[0].get("_win_max")
        window = f"€{wmin:,.0f}–{wmax:,.0f}".replace(",", ".") if wmin is not None else "any"
        base_query = key.partition(" · ")[2]
        L.append(f"## {display_name(key)} ({len(qrows)} items)")
        L.append("")
        trend = trend_str(history, key)
        trend_part = f" · 30d {trend}" if trend else ""
        cap = capacity_gb(base_query)
        gb_part = f" · median {euro(median / cap)}/GB" if cap else ""
        anchor = sold_anchors.get(base_query)
        sold_part = (f" · sold median **{euro(anchor['median_sold'])}** "
                     f"(n={anchor['sample_size']})") if anchor else ""
        L.append(f"_Window {window} · median **{euro(median)}** · cheapest "
                 f"**{euro(cheapest['_price'])}** · {at_target} at/near buy-low"
                 f"{trend_part}{gb_part}{sold_part}_")
        L.append("")
        headers = ["Price", "Condition", "Title", "Seller", "Note"]
        if net_label:
            headers.insert(1, net_label)
        if has_capacity:
            headers.insert(2, "€/GB")
        if multi:
            headers.insert(0, "Mkt")
        L.append("| " + " | ".join(headers) + " |")
        L.append("|" + "---|" * len(headers))
        for r in qrows:
            title = (r["title"] or "").replace("|", "\\|")
            note = flag_for(r)
            repriced = repriced_note(r, listing_history)
            if repriced:
                note = f"{note} · {repriced}"
            cells = [f"**{euro(r['_price'])}**"]
            if net_label:
                cells.append(net_euro(r["_price"]))
            if has_capacity:
                cells.append(euro_per_gb_str(r["_price"], base_query))
            cells += [r["condition"], f"[{title}]({r.get('url') or ''})", r["seller"], note]
            if multi:
                cells.insert(0, r["_mp"])
            L.append("| " + " | ".join(cells) + " |")
        L.append("")

    # --- methodology ------------------------------------------------------
    L.append("## Methodology & notes")
    L.append("")
    for note in FOOTNOTES:
        L.append(f"- {note}")
    L.append("")
    L.append("_" + " · ".join([
        "Tooling: `ebay-search-skill/` (Browse API scanner + local relay)",
        "Categories: 27386 GPUs · 171957 desktops · 170083 RAM · 11210 server RAM",
        "Generated by the nightly GitHub Actions workflow",
    ]) + "_")
    L.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"wrote {out_path} with {len(rows)} rows, {len(flagged)} highlighted deals, {len(mv)} movers")


if __name__ == "__main__":
    main()
