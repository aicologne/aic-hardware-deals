#!/usr/bin/env python3
"""Send buy-low + price-drop alerts (Telegram / Discord).

Two kinds of alerts, both deduped against a persisted state file:

  🔥 buy-low  — NEW flagged listings (price <= win_min * 1.15, same rule as
                the report's 🔥 section), only for deals not reported before.
  📉 price drop — listings seen in an earlier scan at a higher price that are
                currently offered >= DROP_THRESHOLD below their first-seen
                price (from site/data/listing_history.csv), only when the drop
                reaches a new price level.

Channels (enable whichever you use; both work together):
  Telegram  -> env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  Discord   -> env DISCORD_WEBHOOK_URL

The state file lives under site/data/ so the workflow commits it (dedupe
survives restarts). Re-running with the same scan is safe: already-notified
items are skipped.

Usage:
    python notify.py ebay_deals.csv [--state site/data/notified.json] \
        [--listing-history site/data/listing_history.csv] [--drop-threshold 0.05] \
        [--dry-run]
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
import logging

# Console-safe output (Windows consoles default to cp1252; never crash on emoji).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

MAX_ITEMS = 20  # cap message length


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def euro(value):
    if value is None:
        return "—"
    return f"€{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def flagged_rows(rows):
    out = []
    for r in rows:
        price = num(r.get("price"))
        win_min = num(r.get("win_min"))
        if price is not None and win_min is not None and price <= win_min * 1.15:
            out.append(r)
    return out


def load_state(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def save_state(path, state):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def build_message(items, date):
    lines = [f"🔥 {len(items)} new buy-low deal(s) — {date}", ""]
    for i, r in enumerate(items[:MAX_ITEMS], start=1):
        lines.append(
            f"{i}. [{r.get('query')}] {euro(num(r.get('price')))} — {r.get('title') or '(no title)'}"
        )
        lines.append(f"   {r.get('url') or ''}")
        lines.append(
            f"   target {euro(num(r.get('win_min')))} · seller {r.get('seller') or '?'} · {r.get('condition') or '?'}"
        )
        lines.append("")
    if len(items) > MAX_ITEMS:
        lines.append(f"…and {len(items) - MAX_ITEMS} more — see the full report.")
    return "\n".join(lines)


def load_listing_history(path):
    """listing_history.csv -> {url: row} (first_price/last_price/first_seen)."""
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, encoding="utf-8-sig") as f:
        import csv as _csv

        for r in _csv.DictReader(f):
            url = (r.get("url") or "").strip()
            if url:
                out[url] = r
    return out


def drop_rows(rows, listing_history, threshold=0.05):
    """Listings currently offered >= threshold below their first-seen price.

    Returns [(row, last_price, first_price, first_seen, drop_pct), ...]
    sorted by drop size, using the CURRENT scan row (price) vs the history.
    """
    out = []
    for r in rows:
        lh = listing_history.get((r.get("url") or "").strip())
        if not lh:
            continue
        first = num(lh.get("first_price"))
        last = num(lh.get("last_price"))
        if first is None or last is None or last >= first:
            continue
        drop = (first - last) / first
        if drop < threshold:
            continue
        out.append((r, last, first, lh.get("first_seen") or "?", drop * 100))
    out.sort(key=lambda t: t[4], reverse=True)
    return out


def build_drop_message(drops, date):
    lines = [f"📉 {len(drops)} price drop(s) on watched listings — {date}", ""]
    for i, (r, last, first, first_seen, pct) in enumerate(drops[:MAX_ITEMS], start=1):
        lines.append(
            f"{i}. [{r.get('query')}] {euro(num(r.get('price')))} "
            f"(was {euro(first)} on {first_seen}, −{pct:.1f} %) — {r.get('title') or '(no title)'}"
        )
        lines.append(f"   {r.get('url') or ''}")
        lines.append(f"   seller {r.get('seller') or '?'} · {r.get('condition') or '?'}")
        lines.append("")
    if len(drops) > MAX_ITEMS:
        lines.append(f"…and {len(drops) - MAX_ITEMS} more drops — see the full report.")
    return "\n".join(lines)


def http_post(url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status


def send_telegram(token, chat_id, text):
    if len(text) > 4000:
        text = text[:3900] + "\n…(truncated)"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return http_post(
        url, {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    )


def send_discord(webhook, text):
    if len(text) > 1900:
        text = text[:1850] + "\n…(truncated)"
    return http_post(webhook, {"content": text})


def main():
    ap = argparse.ArgumentParser(
        description="Buy-low + price-drop alert notifier (Telegram/Discord)"
    )
    ap.add_argument("csv", help="path to ebay_deals.csv")
    ap.add_argument(
        "--state", default="notified.json", help="state file with already-notified URLs"
    )
    ap.add_argument(
        "--listing-history",
        default="site/data/listing_history.csv",
        help="per-listing price history (first-seen vs last-seen) for drop alerts",
    )
    ap.add_argument(
        "--drop-threshold",
        type=float,
        default=0.05,
        help="minimum relative price drop to alert, e.g. 0.05 = 5 %% (default 0.05)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print the message instead of sending"
    )
    args = ap.parse_args()

    rows = []
    with open(args.csv, encoding="utf-8-sig") as f:
        import csv as _csv

        for r in _csv.DictReader(f):
            if num(r.get("price")) is not None:
                rows.append(r)

    flagged = flagged_rows(rows)
    flagged.sort(key=lambda r: num(r.get("price")))

    state = load_state(args.state)
    new_items = [r for r in flagged if r.get("url") not in state]
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    messages = []
    if new_items:
        messages.append(build_message(new_items, date))
    else:
        print(
            f"no new flagged deals (state has {len(state)} entries, "
            f"{len(flagged)} currently flagged)"
        )

    listing_history = load_listing_history(args.listing_history)
    if not listing_history:
        print(
            f"(no listing history at {args.listing_history} — "
            "price-drop alerts skipped)"
        )
        drops, new_drops = [], []
    else:
        drops = drop_rows(rows, listing_history, args.drop_threshold)
        new_drops = [
            d for d in drops if f"drop:{d[0].get('url')}:{d[1]:.2f}" not in state
        ]
        if new_drops:
            messages.append(build_drop_message(new_drops, date))
        else:
            print(
                f"no new price drops ({len(drops)} drop(s) tracked on watched listings)"
            )

    if not messages:
        return 0

    for text in messages:
        print(text)
        print("-" * 40)

    if args.dry_run:
        print("[dry-run] would send the message(s) above; state not updated")
        return 0

    sent_any = False
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    webhook = webhook.strip() if isinstance(webhook, str) else None
    for text in messages:
        sent = False
        if token and chat_id:
            send_telegram(token, chat_id, text)
            sent = True
            print("sent via Telegram")
        if webhook and webhook.startswith("http"):
            send_discord(webhook, text)
            sent = True
            print("sent via Discord")
        sent_any = sent_any or sent
    if not sent_any:
        print(
            "WARNING: no channel configured (set TELEGRAM_BOT_TOKEN+TELEGRAM_CHAT_ID "
            "or DISCORD_WEBHOOK_URL); nothing sent"
        )

    # Remember every currently-flagged URL (new + already known) so the next
    # run only reports deals that appear for the first time, and every current
    # drop keyed by its price level so a drop is pinged once per new level.
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    next_state = {}
    for r in flagged:
        url = r.get("url")
        url = url.strip() if isinstance(url, str) else None
        if url and url.startswith("http"):
            next_state[url] = state.get(url, now)
    for r, last, first, first_seen, pct in drops:
        key = f"drop:{r.get('url')}:{last:.2f}"
        next_state[key] = state.get(key, now)
    save_state(args.state, next_state)
    print(f"state updated ({len(next_state)} tracked items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
