#!/usr/bin/env python3
"""Fail loudly when the nightly scan data has gone stale.

Why this exists
---------------
The nightly workflow runs its unit tests *before* the scan. On 2026-08-29 a test
became environment-dependent (`window_for_query(q, None)` silently read
`site/data/history.csv` from the working directory), so from 2026-08-30 to
2026-09-08 every scheduled run failed at that step, the scan never executed,
and the site kept serving ten-day-old prices. Nothing alerted — the outage
was found by a human who happened to look.

This guard turns that silence into a red run plus a ping:

    python check_freshness.py                       # 0 = fresh, 1 = stale
    python check_freshness.py --notify              # also ping Telegram/Discord
    python check_freshness.py --now 2026-09-12T09:00:00Z

The newest scan date comes from the `date` column of site/data/history.csv
(one row per category per scan, written by render_history.py in the same run).
Because that column is a bare date, it is anchored to SCAN_HOUR_UTC — the hour
the cron runs — when the age is computed; otherwise a date-only column would
look up to 24 h fresher than it is.

Exit codes: 0 fresh · 1 stale · 2 no usable data (missing file / no dates).
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

import alert

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

DEFAULT_HISTORY_PATH = "site/data/history.csv"
DEFAULT_MAX_AGE_HOURS = 36.0
# The nightly cron in .github/workflows/ebay-scan.yml runs at 05:00 UTC, so a
# scan date is anchored there when computing the age (see the module docstring).
SCAN_HOUR_UTC = 5
DATE_FORMAT = "%Y-%m-%d"
FALLBACK_RUNS_URL = "https://github.com/aicologne/aic-hardware-deals/actions"


def parse_now(value=None):
    """ISO-8601 -> aware UTC datetime; None -> now. A bare date means 00:00 UTC."""
    if not value:
        return datetime.now(timezone.utc)
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"cannot parse --now {value!r} (expected e.g. 2026-09-12T09:00:00Z)"
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def newest_scan_date(history_path):
    """Newest YYYY-MM-DD in the history file, or None (missing/unusable)."""
    if not history_path or not os.path.exists(history_path):
        return None
    newest = None
    with open(history_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            raw = (row.get("date") or "").strip()
            try:
                parsed = datetime.strptime(raw, DATE_FORMAT).date()
            except ValueError:
                continue  # blank/garbage cells are skipped, not fatal
            if newest is None or parsed > newest:
                newest = parsed
    return newest


def anchor(scan_date):
    """A date-only scan column anchored to the hour the cron runs (UTC)."""
    return datetime(
        scan_date.year, scan_date.month, scan_date.day, SCAN_HOUR_UTC,
        tzinfo=timezone.utc,
    )


def age_hours(newest, now):
    """Hours between the anchored scan date and `now`; None without a date."""
    if newest is None:
        return None
    return (now - anchor(newest)).total_seconds() / 3600.0


def evaluate(history_path=DEFAULT_HISTORY_PATH,
             max_age_hours=DEFAULT_MAX_AGE_HOURS, now=None):
    """-> {status: fresh|stale|error, newest, age_hours, max_age_hours, detail}."""
    now = now or datetime.now(timezone.utc)
    newest = newest_scan_date(history_path)
    age = age_hours(newest, now)
    if newest is None:
        status = "error"
        detail = f"no scan dates found in {history_path}"
    elif age > max_age_hours:
        status = "stale"
        detail = (f"newest scan {newest.isoformat()} is {age:.1f} h old "
                  f"(limit {max_age_hours:g} h)")
    else:
        status = "fresh"
        detail = (f"newest scan {newest.isoformat()} is {age:.1f} h old "
                  f"(limit {max_age_hours:g} h)")
    return {
        "status": status,
        "newest": newest.isoformat() if newest else None,
        "age_hours": age,
        "max_age_hours": max_age_hours,
        "detail": detail,
    }


def runs_url(env=None):
    """Link to the workflow runs, built from the CI env when available."""
    env = os.environ if env is None else env
    server = env.get("GITHUB_SERVER_URL")
    repo = env.get("GITHUB_REPOSITORY")
    if server and repo:
        return f"{server}/{repo}/actions"
    return FALLBACK_RUNS_URL


def build_message(result, history_path=DEFAULT_HISTORY_PATH, env=None):
    """The alert text for a stale/error result."""
    if result["status"] == "error":
        head = "⚠️ scan data check failed: no usable scan dates"
    else:
        head = "⚠️ scan data is STALE"
    lines = [
        head,
        f"• {result['detail']}",
        f"• data file: {history_path}",
        "• the nightly scan has not committed fresh data — check the workflow:",
        f"  {runs_url(env)}",
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Fail when the nightly scan data is older than --max-age-hours"
    )
    ap.add_argument("--history", default=DEFAULT_HISTORY_PATH,
                    help=f"scan history CSV (default: {DEFAULT_HISTORY_PATH})")
    ap.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS,
                    help=f"maximum acceptable data age in hours "
                         f"(default: {DEFAULT_MAX_AGE_HOURS:g})")
    ap.add_argument("--now", default=None,
                    help="evaluate as if it were this time (ISO-8601, e.g. "
                         "2026-09-12T09:00:00Z) — for tests and dry runs")
    ap.add_argument("--notify", action="store_true",
                    help="also send the message to Telegram/Discord")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be sent; sends nothing")
    args = ap.parse_args(argv)

    try:
        now = parse_now(args.now)
    except ValueError as err:
        print(f"ERROR: {err}")
        return 2

    result = evaluate(args.history, args.max_age_hours, now)
    print(f"{result['status'].upper()}  {result['detail']}  [{args.history}]")

    if result["status"] == "fresh":
        return 0

    if args.notify or args.dry_run:
        alert.send(build_message(result, args.history), dry_run=args.dry_run)
    return 1 if result["status"] == "stale" else 2


if __name__ == "__main__":
    sys.exit(main())
