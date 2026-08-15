#!/usr/bin/env python3
"""Render ebay_deals.csv into LATEST.md — the final price report.

The report is the product: it combines the latest scan with the deal windows
(carried in the CSV as win_min/win_max), flags items at/below the buy-low
target, shows per-category medians, and ends with methodology + disclaimer.

Usage:
    python render_report.py [ebay_deals.csv] [LATEST.md]
"""
import csv
import datetime
import statistics
import sys

MARKET_CONTEXT = (
    "**Market context (2026):** the DRAM/GDDR shortage keeps used prices elevated. "
    "Used RTX 3090s ask €1000–1500 on eBay.de; DDR5 German retail is ~4.2–4.5× its "
    "July-2025 level; DDR4 RDIMM shops ask €219–230 for 32 GB while private sellers "
    "still move pre-shortage stock at €60–120. Note the new-price anchors: a BOSGAME M5 "
    "(Strix Halo, 128 GB) costs €1581–1700 new — used Strix Halo above that is not a deal. "
    "Verify everything live — prices move weekly."
)

FOOTNOTES = [
    "Prices are asking prices from active eBay.de listings (used, EUR), collected by the Browse API.",
    "Buy-low targets are the scan windows configured in `ebay_search.py`; a listing within 15 % of the target is flagged 🔥.",
    "eBay seller fees (~13 %) and shipping are NOT included — subtract them from any margin estimate.",
    "Condition and warranty are the seller's; always verify photos, GPU-Z/memtest results, and seller feedback before paying.",
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


def flag_for(row):
    price = row["_price"]
    wmin = row.get("_win_min")
    wmax = row.get("_win_max")
    if wmin is not None and price <= wmin * 1.15:
        return "🔥 at/near buy-low target"
    if wmax is not None and price > wmax:
        return "⚠️ above scan window"
    return "ok"


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "ebay_deals.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "LATEST.md"

    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["_price"] = num(r.get("price"))
            r["_win_min"] = num(r.get("win_min"))
            r["_win_max"] = num(r.get("win_max"))
            if r["_price"] is not None:
                rows.append(r)

    queries = sorted({r["query"] for r in rows})
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    L = []  # output lines
    L.append("# 🛒 eBay.de Used Hardware — Price Report")
    L.append("")
    L.append(f"_Generated {now} · {len(rows)} items across {len(queries)} categories · "
             "marketplace eBay.de, used, EUR_")
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
        L.append("| Category | Price | Buy-low target | Title | Seller |")
        L.append("|---|---|---|---|---|")
        for r in flagged:
            target = euro(r["_win_min"])
            title = (r["title"] or "").replace("|", "\\|")
            L.append(f"| {r['query']} | **{euro(r['_price'])}** | {target} | "
                     f"[{title}]({r.get('url') or ''}) | {r['seller']} |")
        L.append("")
    else:
        L.append("No listings currently sit at the buy-low targets. Check back after the "
                 "next nightly scan, or widen the windows in `ebay_search.py`.")
        L.append("")

    # --- per-category reports ---------------------------------------------
    for query in queries:
        qrows = [r for r in rows if r["query"] == query]
        qrows.sort(key=lambda r: r["_price"])
        prices = [r["_price"] for r in qrows]
        median = statistics.median(prices)
        cheapest = qrows[0]
        at_target = sum(1 for r in qrows if flag_for(r) == "🔥 at/near buy-low target")
        wmin = qrows[0].get("_win_min")
        wmax = qrows[0].get("_win_max")
        window = f"€{wmin:,.0f}–{wmax:,.0f}".replace(",", ".") if wmin is not None else "any"
        L.append(f"## {query} ({len(qrows)} items)")
        L.append("")
        L.append(f"_Window {window} · median **{euro(median)}** · cheapest "
                 f"**{euro(cheapest['_price'])}** · {at_target} at/near buy-low_")
        L.append("")
        L.append("| Price | Condition | Title | Seller | Note |")
        L.append("|---|---|---|---|---|")
        for r in qrows:
            title = (r["title"] or "").replace("|", "\\|")
            L.append(f"| **{euro(r['_price'])}** | {r['condition']} | "
                     f"[{title}]({r.get('url') or ''}) | {r['seller']} | {flag_for(r)} |")
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
    print(f"wrote {out_path} with {len(rows)} rows, {len(flagged)} highlighted deals")


if __name__ == "__main__":
    main()
