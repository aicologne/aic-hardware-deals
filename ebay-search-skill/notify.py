#!/usr/bin/env python3
"""Send buy-low alerts (Telegram / Discord) for NEW flagged deals.

Compares the flagged listings (price <= win_min * 1.15 — same rule as the
report's 🔥 section) of the current scan against a persisted state file and
notifies only about deals it has not reported before, so the nightly run does
not spam the same items.

Channels (enable whichever you use; both work together):
  Telegram  -> env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  Discord   -> env DISCORD_WEBHOOK_URL

The state file lives under site/data/ so the workflow commits it (dedupe
survives restarts). Re-running with the same scan is safe: already-notified
listings are skipped.

Usage:
    python notify.py ebay_deals.csv [--state site/data/notified.json] [--dry-run]
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
        lines.append(f"{i}. [{r.get('query')}] {euro(num(r.get('price')))} — {r.get('title') or '(no title)'}")
        lines.append(f"   {r.get('url') or ''}")
        lines.append(
            f"   target {euro(num(r.get('win_min')))} · seller {r.get('seller') or '?'} · {r.get('condition') or '?'}"
        )
        lines.append("")
    if len(items) > MAX_ITEMS:
        lines.append(f"…and {len(items) - MAX_ITEMS} more — see the full report.")
    return "\n".join(lines)


def http_post(url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status


def send_telegram(token, chat_id, text):
    if len(text) > 4000:
        text = text[:3900] + "\n…(truncated)"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return http_post(url, {"chat_id": chat_id, "text": text, "disable_web_page_preview": True})


def send_discord(webhook, text):
    if len(text) > 1900:
        text = text[:1850] + "\n…(truncated)"
    return http_post(webhook, {"content": text})


def main():
    ap = argparse.ArgumentParser(description="Buy-low alert notifier (Telegram/Discord)")
    ap.add_argument("csv", help="path to ebay_deals.csv")
    ap.add_argument("--state", default="notified.json", help="state file with already-notified URLs")
    ap.add_argument("--dry-run", action="store_true", help="print the message instead of sending")
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

    if not new_items:
        print(f"no new flagged deals (state has {len(state)} entries, {len(flagged)} currently flagged)")
        return 0

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    text = build_message(new_items, date)
    print(text)

    if args.dry_run:
        print(f"[dry-run] would send {len(new_items)} deal(s); state not updated")
        return 0

    sent = False
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        send_telegram(token, chat_id, text)
        sent = True
        print("sent via Telegram")
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if webhook:
        send_discord(webhook, text)
        sent = True
        print("sent via Discord")

    if not sent:
        print("WARNING: no channel configured (set TELEGRAM_BOT_TOKEN+TELEGRAM_CHAT_ID or DISCORD_WEBHOOK_URL); nothing sent")
        return 1

    # Remember every currently-flagged URL (new + already known) so the next
    # run only reports deals that appear for the first time; drop stale ones.
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    next_state = {}
    for r in flagged:
        url = r.get("url")
        url = url.strip() if isinstance(url, str) else None
        if url and url.startswith("http"):
            next_state[url] = state.get(url, now)
    save_state(args.state, next_state)
    print(f"state updated ({len(next_state)} tracked urls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
