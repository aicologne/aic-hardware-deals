"""Unit tests for render_listing_history.py — per-listing price tracking.

Runs main() against temp CSVs to verify first/last-seen tracking, repricing
detection, stale-entry pruning and the MAX_ROWS cap.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_render_listing_history.py
"""
import csv
import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import render_listing_history  # noqa: E402

SCAN_HEADER = ["query", "title", "price", "currency", "condition",
               "seller", "url", "marketplace", "win_min", "win_max"]
FIELDS = ["url", "query", "marketplace", "first_seen", "first_price",
          "last_seen", "last_price"]


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
    with mock.patch.object(sys, "argv", ["render_listing_history.py", scan, out, "--date", date]), \
         mock.patch("sys.stdout", new=mock.MagicMock()):
        render_listing_history.main()


class TestRenderListingHistory(unittest.TestCase):
    def test_tracks_first_and_last_price(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "listing_history.csv")
            write_scan(scan, [{"url": "https://x/1", "query": "RAM", "price": "42.00",
                               "marketplace": "EBAY_DE"}])
            run_main(scan, out, "2026-08-14")
            rows = read_csv(out)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["url"], "https://x/1")
            self.assertEqual(rows[0]["first_seen"], "2026-08-14")
            self.assertEqual(rows[0]["first_price"], "42.00")
            self.assertEqual(rows[0]["last_seen"], "2026-08-14")
            self.assertEqual(rows[0]["last_price"], "42.00")
            # re-scan at a higher price -> last_price updates, first stays
            write_scan(scan, [{"url": "https://x/1", "query": "RAM", "price": "50.00",
                               "marketplace": "EBAY_DE"}])
            run_main(scan, out, "2026-08-18")
            rows = read_csv(out)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["first_price"], "42.00")
            self.assertEqual(rows[0]["last_price"], "50.00")
            self.assertEqual(rows[0]["first_seen"], "2026-08-14")
            self.assertEqual(rows[0]["last_seen"], "2026-08-18")

    def test_repriced_count_in_output_message(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "listing_history.csv")
            write_scan(scan, [{"url": "https://x/1", "query": "RAM", "price": "42.00",
                               "marketplace": "EBAY_DE"}])
            with mock.patch.object(sys, "argv", ["render_listing_history.py", scan, out, "--date", "2026-08-14"]), \
                 mock.patch("sys.stdout", new=mock.MagicMock()) as out_mock:
                render_listing_history.main()
            write_scan(scan, [{"url": "https://x/1", "query": "RAM", "price": "50.00",
                               "marketplace": "EBAY_DE"}])
            with mock.patch.object(sys, "argv", ["render_listing_history.py", scan, out, "--date", "2026-08-18"]), \
                 mock.patch("sys.stdout", new=mock.MagicMock()) as out_mock:
                render_listing_history.main()
                printed = "".join(str(c.args[0]) for c in out_mock.write.call_args_list)
            self.assertIn("1 repriced", printed)

    def test_prunes_stale_entries_not_in_current_scan(self):
        with temp_dir() as d:
            out = os.path.join(d, "listing_history.csv")
            stale_date = (datetime.date.fromisoformat("2026-08-20")
                          - datetime.timedelta(days=render_listing_history.PRUNE_AFTER_DAYS + 1)).isoformat()
            with open(out, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                w.writerow({"url": "https://stale/1", "query": "OLD", "marketplace": "EBAY_DE",
                            "first_seen": stale_date, "first_price": "10.00",
                            "last_seen": stale_date, "last_price": "10.00"})
            scan = os.path.join(d, "scan.csv")
            write_scan(scan, [{"url": "https://live/1", "query": "RAM", "price": "42.00",
                               "marketplace": "EBAY_DE"}])
            run_main(scan, out, "2026-08-20")
            rows = read_csv(out)
            urls = {r["url"] for r in rows}
            self.assertIn("https://live/1", urls)
            self.assertNotIn("https://stale/1", urls, "stale entry pruned")

    def test_stale_but_still_scanned_is_kept(self):
        with temp_dir() as d:
            out = os.path.join(d, "listing_history.csv")
            stale_date = (datetime.date.fromisoformat("2026-08-20")
                          - datetime.timedelta(days=render_listing_history.PRUNE_AFTER_DAYS + 1)).isoformat()
            with open(out, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                w.writerow({"url": "https://x/1", "query": "RAM", "marketplace": "EBAY_DE",
                            "first_seen": stale_date, "first_price": "10.00",
                            "last_seen": stale_date, "last_price": "10.00"})
            scan = os.path.join(d, "scan.csv")
            write_scan(scan, [{"url": "https://x/1", "query": "RAM", "price": "42.00",
                               "marketplace": "EBAY_DE"}])
            run_main(scan, out, "2026-08-20")
            rows = read_csv(out)
            self.assertEqual(len(rows), 1, "seen again -> kept, last_seen refreshed")
            self.assertEqual(rows[0]["last_seen"], "2026-08-20")
            self.assertEqual(rows[0]["last_price"], "42.00")

    def test_max_rows_cap(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "listing_history.csv")
            rows = [{"url": f"https://x/{i}", "query": "RAM", "price": "42.00",
                     "marketplace": "EBAY_DE"} for i in range(5)]
            write_scan(scan, rows)
            with mock.patch.object(render_listing_history, "MAX_ROWS", 3):
                run_main(scan, out, "2026-08-20")
            kept = read_csv(out)
            self.assertEqual(len(kept), 3, "capped at MAX_ROWS")
            self.assertEqual(len({r["url"] for r in kept}), 3)

    def test_missing_urls_are_skipped(self):
        with temp_dir() as d:
            scan = os.path.join(d, "scan.csv")
            out = os.path.join(d, "listing_history.csv")
            write_scan(scan, [{"url": "", "query": "RAM", "price": "42.00",
                               "marketplace": "EBAY_DE"}])
            run_main(scan, out, "2026-08-20")
            self.assertEqual(read_csv(out), [], "no url -> nothing tracked")


if __name__ == "__main__":
    unittest.main(verbosity=2)
