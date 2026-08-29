"""Unit tests for render_history.py — per-category median history (end-to-end).

Runs main() against temp CSVs to verify median computation, idempotent
re-runs (same date replaces, never duplicates) and the MAX_DAYS prune.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_render_history.py
"""
import csv
import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import render_history  # noqa: E402

SCAN_HEADER = ["query", "title", "price", "currency", "condition",
               "seller", "url", "marketplace", "win_min", "win_max"]


def write_scan(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SCAN_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def run_main(scan, out, date):
    with mock.patch.object(sys, "argv", ["render_history.py", scan, out, "--date", date]), \
         mock.patch("sys.stdout", new=mock.MagicMock()):
        render_history.main()


class TestRenderHistory(unittest.TestCase):
    def test_computes_median_cheapest_count(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "history.csv")
            write_scan(scan, [
                {"query": "RAM", "title": "a", "price": "40", "win_min": "40",
                 "marketplace": "EBAY_DE", "win_max": "120"},
                {"query": "RAM", "title": "b", "price": "60", "win_min": "40",
                 "marketplace": "EBAY_DE", "win_max": "120"},
                {"query": "RAM", "title": "c", "price": "100", "win_min": "40",
                 "marketplace": "EBAY_DE", "win_max": "120"},
                {"query": "GPU", "title": "d", "price": "1200", "win_min": "900",
                 "marketplace": "EBAY_AT", "win_max": "1600"},
            ])
            run_main(scan, out, "2026-08-20")
            rows = read_csv(out)
            self.assertEqual(len(rows), 2)
            by_query = {r["query"]: r for r in rows}
            ram = by_query["RAM"]
            self.assertEqual(ram["date"], "2026-08-20")
            self.assertEqual(ram["marketplace"], "EBAY_DE")
            self.assertEqual(ram["median"], "60.00")
            self.assertEqual(ram["cheapest"], "40.00")
            self.assertEqual(ram["count"], "3")
            self.assertEqual(ram["at_target"], "1", "only 40 <= 40*1.15")
            gpu = by_query["GPU"]
            self.assertEqual(gpu["marketplace"], "EBAY_AT")
            self.assertEqual(gpu["median"], "1200.00")

    def test_same_date_rerun_is_idempotent(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "history.csv")
            write_scan(scan, [{"query": "RAM", "title": "a", "price": "50",
                               "win_min": "40", "marketplace": "EBAY_DE",
                               "win_max": "120"}])
            run_main(scan, out, "2026-08-20")
            run_main(scan, out, "2026-08-20")
            rows = read_csv(out)
            self.assertEqual(len(rows), 1, "re-running the same date replaces, not duplicates")

    def test_different_dates_accumulate(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "history.csv")
            write_scan(scan, [{"query": "RAM", "title": "a", "price": "50",
                               "win_min": "40", "marketplace": "EBAY_DE",
                               "win_max": "120"}])
            run_main(scan, out, "2026-08-19")
            run_main(scan, out, "2026-08-20")
            rows = read_csv(out)
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["date"] for r in rows}, {"2026-08-19", "2026-08-20"})

    def test_prunes_rows_older_than_max_days(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "history.csv")
            old_date = (datetime.date.fromisoformat("2026-08-20")
                        - datetime.timedelta(days=render_history.MAX_DAYS + 10)).isoformat()
            # seed history with an old row plus a recent row from another query
            with open(out, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["date", "marketplace", "query",
                                                  "median", "cheapest", "count", "at_target"])
                w.writeheader()
                w.writerow({"date": old_date, "marketplace": "EBAY_DE", "query": "OLD",
                            "median": "10.00", "cheapest": "10.00", "count": "1", "at_target": "0"})
            write_scan(scan, [{"query": "RAM", "title": "a", "price": "50",
                               "win_min": "40", "marketplace": "EBAY_DE",
                               "win_max": "120"}])
            run_main(scan, out, "2026-08-20")
            rows = read_csv(out)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["query"], "RAM", "old row pruned beyond MAX_DAYS")

    def test_default_marketplace_when_column_missing(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "history.csv")
            write_scan(scan, [{"query": "RAM", "title": "a", "price": "50",
                               "win_min": "40", "win_max": "120"}])  # no marketplace
            run_main(scan, out, "2026-08-20")
            rows = read_csv(out)
            self.assertEqual(rows[0]["marketplace"], "EBAY_DE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
