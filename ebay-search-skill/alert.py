#!/usr/bin/env python3
"""Send a plain alert to the configured channels (Telegram / Discord).

A dependency-free wrapper around notify.py's senders, shared by the pipeline
guards so a broken pipeline says so out loud instead of going quiet:

  * check_freshness.py             -> the scan data is older than N hours
  * .github/workflows/ebay-scan.yml -> the nightly scan itself failed

Channels (enable whichever you use; both work together):
  Telegram  -> env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  Discord   -> env DISCORD_WEBHOOK_URL

It exits 0 even when no channel is configured (it prints a warning instead):
a missing notification channel must never turn into a second failure.

Usage:
    python alert.py "nightly scan failed"
    python alert.py --dry-run "nightly scan failed"     # print, send nothing
"""

import argparse
import os
import sys

import notify

# Console-safe output (Windows consoles default to cp1252; never crash on emoji).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def channels(env=None):
    """Names of the channels configured in `env` (default: os.environ)."""
    env = os.environ if env is None else env
    out = []
    if env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID"):
        out.append("telegram")
    webhook = env.get("DISCORD_WEBHOOK_URL") or ""
    if webhook.strip().startswith("http"):
        out.append("discord")
    return out


def send(text, env=None, dry_run=False, post=None):
    """Send `text` to every configured channel; return the channels used.

    `post(url, payload, headers=None)` is injectable so unit tests never touch
    the network. Never raises for a missing channel.
    """
    env = os.environ if env is None else env
    used = channels(env)
    if dry_run:
        print("[dry-run] would alert via "
              + (", ".join(used) if used else "no channel (none configured)"))
        return used
    if not used:
        print(
            "WARNING: no alert channel configured (set TELEGRAM_BOT_TOKEN + "
            "TELEGRAM_CHAT_ID or DISCORD_WEBHOOK_URL); nothing sent"
        )
        return []
    for name in used:
        if name == "telegram":
            notify.send_telegram(
                env["TELEGRAM_BOT_TOKEN"], env["TELEGRAM_CHAT_ID"], text, post
            )
        else:
            notify.send_discord(env["DISCORD_WEBHOOK_URL"], text, post)
    print("alert sent via " + ", ".join(used))
    return used


def main(argv=None):
    ap = argparse.ArgumentParser(description="Send an alert to Telegram/Discord")
    ap.add_argument("message", help="the message text to send")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the message instead of sending it")
    args = ap.parse_args(argv)
    print(args.message)
    send(args.message, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
