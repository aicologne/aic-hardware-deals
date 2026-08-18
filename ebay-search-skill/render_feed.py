#!/usr/bin/env python3
"""Render ebay_deals.csv into site/feed.xml — an RSS 2.0 feed of the deal highlights.

The feed mirrors the 🔥 section of LATEST.md: listings at or within 15 % of the
buy-low target, cheapest first. If no listing currently qualifies, the feed
still emits a single item so subscribers know the scan ran.

Usage:
    python render_feed.py [ebay_deals.csv] [site/feed.xml]
"""
import csv
import datetime
import html
import sys
from email.utils import format_datetime

CHANNEL_TITLE = "eBay.de Used Hardware — Daily Deals"
# Point this at your Pages site if you prefer: https://<user>.github.io/<repo>/
CHANNEL_LINK = "https://github.com/aicologne/aic-hardware-deals"
CHANNEL_DESCRIPTION = (
    "Nightly deal highlights from the eBay.de used-hardware price report "
    "(GPUs with >=16 GB VRAM, server RAM, mini PCs): items at or within 15 % of "
    "the buy-low target. Collected via the official eBay Browse API; always "
    "verify condition and price before buying."
)


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def euro(value):
    if value is None:
        return "—"
    return f"€{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def xmlesc(text):
    return html.escape(text or "", quote=True)


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "ebay_deals.csv"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "site/feed.xml"

    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["_price"] = num(r.get("price"))
            r["_win_min"] = num(r.get("win_min"))
            if r["_price"] is not None:
                rows.append(r)

    flagged = [
        r for r in rows
        if r["_win_min"] is not None and r["_price"] <= r["_win_min"] * 1.15
    ]
    flagged.sort(key=lambda r: r["_price"])

    now = datetime.datetime.now(datetime.timezone.utc)
    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<rss version="2.0">')
    L.append("  <channel>")
    L.append(f"    <title>{xmlesc(CHANNEL_TITLE)}</title>")
    L.append(f"    <link>{xmlesc(CHANNEL_LINK)}</link>")
    L.append(f"    <description>{xmlesc(CHANNEL_DESCRIPTION)}</description>")
    L.append(f"    <lastBuildDate>{format_datetime(now)}</lastBuildDate>")
    L.append(f"    <pubDate>{format_datetime(now)}</pubDate>")
    L.append("    <generator>render_feed.py (aic-hardware-deals)</generator>")

    if flagged:
        for i, r in enumerate(flagged, start=1):
            title = f"[{r['query']}] {euro(r['_price'])} — {r.get('title') or '(no title)'} ({r.get('seller') or '? seller'})"
            desc = (
                f"Category: {r.get('query') or ''}. "
                f"Price: {euro(r['_price'])}. "
                f"Buy-low target: {euro(r['_win_min'])}. "
                f"Condition: {r.get('condition') or ''}. "
                f"Seller: {r.get('seller') or ''}."
            )
            url = r.get("url") or CHANNEL_LINK
            L.append("    <item>")
            L.append(f"      <title>{xmlesc(title)}</title>")
            L.append(f"      <link>{xmlesc(url)}</link>")
            L.append(f"      <guid isPermaLink=\"false\">deal-{now:%Y-%m-%d}-{i}</guid>")
            L.append(f"      <description>{xmlesc(desc)}</description>")
            L.append(f"      <pubDate>{format_datetime(now)}</pubDate>")
            L.append("    </item>")
    else:
        title = "No deals at the buy-low targets today"
        desc = (
            "The nightly scan found no listings within 15 % of the buy-low "
            "targets. See the full report for the current medians and windows."
        )
        L.append("    <item>")
        L.append(f"      <title>{xmlesc(title)}</title>")
        L.append(f"      <link>{xmlesc(CHANNEL_LINK)}</link>")
        L.append(f"      <guid isPermaLink=\"false\">no-deals-{now:%Y-%m-%d}</guid>")
        L.append(f"      <description>{xmlesc(desc)}</description>")
        L.append(f"      <pubDate>{format_datetime(now)}</pubDate>")
        L.append("    </item>")

    L.append("  </channel>")
    L.append("</rss>")
    L.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"wrote {out_path} with {len(flagged)} highlighted deal(s)")


if __name__ == "__main__":
    main()
