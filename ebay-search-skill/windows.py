#!/usr/bin/env python3
"""Adaptive deal windows derived from the scan price history.

The static windows in queries.py (e.g. RTX 3090 €450–750) were set when the
market was different. As the DRAM/GDDR shortage moved prices, those windows
started hiding the market: items above the static max are filtered out both
server-side and client-side, so the report showed nothing for whole categories.

Adaptive windows follow the market from site/data/history.csv while keeping
the buy-low target meaningful:

    win_min = max(static_min, FLOOR_FACTOR * p25 of the last-30-day medians)
    win_max = max(static_max, min(CEIL_FACTOR * p75, MAX_CEIL_MULTIPLE * median))

So the buy-low target sits below the cheaper-than-usual days of the recent
market, and the window ceiling widens upward as prices rise — without letting
a single price spike blow the window up. With fewer than 2 history points the
static window is used unchanged (first scan of a new category).

History key is "MARKETPLACE · query" — the same composite key render_history.py
writes and render_report.py reads, so the scanner, report and alerts all agree.
"""

import csv
import os
import statistics

DEFAULT_MARKETPLACE = "EBAY_DE"
DEFAULT_HISTORY_PATH = "site/data/history.csv"
DEFAULT_HISTORY_DAYS = 30

# Buy-low target: 80 % of the lower-quartile day of recent medians.
FLOOR_FACTOR = 0.8
# Window ceiling: 150 % of the upper-quartile day of recent medians.
CEIL_FACTOR = 1.5
# Hard guard: never widen past 2.5× the median (protects against price spikes).
MAX_CEIL_MULTIPLE = 2.5


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile(sorted_values, p):
    """Linear-interpolation percentile of an already-sorted list (0..100)."""
    if not sorted_values:
        return None
    idx = (len(sorted_values) - 1) * p / 100.0
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def load_recent_medians(history_path=None, days=DEFAULT_HISTORY_DAYS):
    """history.csv -> {composite_key: [median, ...]} for the last `days` dates.

    Returns {} when the history file does not exist yet (first runs).
    """
    path = history_path or DEFAULT_HISTORY_PATH
    if not path or not os.path.exists(path):
        return {}
    by_key = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            median = num(r.get("median"))
            if median is None:
                continue
            mp = (r.get("marketplace") or DEFAULT_MARKETPLACE).strip()
            by_key.setdefault(f"{mp} · {r['query']}", []).append((r.get("date"), median))
    out = {}
    for key, points in by_key.items():
        points.sort(key=lambda p: p[0] or "")
        out[key] = [m for _, m in points[-days:]]
    return out


def adaptive_window(static_min, static_max, medians):
    """(win_min, win_max) following the market; static window when history is thin."""
    if static_min is None:
        static_min = 0.0
    if static_max is None:
        static_max = 0.0
    medians = [m for m in (medians or []) if m is not None]
    if len(medians) < 2:
        return static_min, static_max
    p25 = percentile(sorted(medians), 25)
    p75 = percentile(sorted(medians), 75)
    median = statistics.median(medians)
    win_min = max(static_min, FLOOR_FACTOR * p25)
    win_max = max(static_max, min(CEIL_FACTOR * p75, MAX_CEIL_MULTIPLE * median))
    return win_min, win_max


def window_for_query(query, history_by_key=None, marketplace=DEFAULT_MARKETPLACE,
                     history_path=None):
    """Adaptive (win_min, win_max) for one query dict.

    The history key uses the query NAME (the same label render_history.py
    records), so windows refine per category as the history accumulates.
    """
    if history_by_key is None:
        history_by_key = load_recent_medians(history_path)
    medians = history_by_key.get(f"{marketplace} · {query['name']}") or []
    return adaptive_window(query.get("min"), query.get("max"), medians)


if __name__ == "__main__":
    # tiny self-check: medians [80,85,90,95] -> p25=83.75, p75=91.25, median=87.5
    assert adaptive_window(40, 120, [80, 85, 90, 95]) == (
        max(40, 0.8 * 83.75), max(120, min(1.5 * 91.25, 2.5 * 87.5)),
    ), "adaptive_window math changed"
    # static fallback with thin history
    assert adaptive_window(40, 120, [85]) == (40, 120)
    # window widens upward with a rising market
    wmin, wmax = adaptive_window(40, 120, [80, 100, 120, 140])
    assert wmin > 40 and wmax > 120, "rising market must widen the window"
    print("windows.py OK")
