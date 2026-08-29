"""Unit tests for split_deals.py — per-category CSV splitting.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_split_deals.py
"""
import csv
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import split_deals  # noqa: E402

HEADER = ["query", "title", "price", "currency", "condition",
          "seller", "url", "marketplace", "win_min", "win_max"]


def write_scan(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow(r)


class TestSplitDeals(unittest.TestCase):
    def test_groups_by_query_and_writes_manifest(self):
        with temp_dir() as d:
            scan = os.path.join(d, "ebay_deals.csv")
            out = os.path.join(d, "deals")
            write_scan(scan, [
                {"query": "RTX 3090", "title": "a", "price": "649.00",
                 "marketplace": "EBAY_DE", "win_min": "450", "win_max": "750"},
                {"query": "RTX 3090", "title": "b", "price": "700.00",
                 "marketplace": "EBAY_DE", "win_min": "450", "win_max": "750"},
                {"query": "DDR4 RDIMM 32GB", "title": "c", "price": "88.00",
                 "marketplace": "EBAY_DE", "win_min": "40", "win_max": "120"},
            ])
            manifest = split_deals.split_deals(scan, out)
            self.assertEqual(len(manifest), 2)
            by_query = {m["query"]: m for m in manifest}
            self.assertEqual(by_query["RTX 3090"]["rows"], 2)
            self.assertEqual(by_query["DDR4 RDIMM 32GB"]["rows"], 1)
            # chunk files exist and carry the right rows
            rtx = os.path.join(out, "RTX-3090.csv")
            self.assertTrue(os.path.exists(rtx))
            with open(rtx, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["title"], "a")
            # index.json matches the manifest
            with open(os.path.join(out, "index.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f), manifest)

    def test_empty_rows_skipped(self):
        with temp_dir() as d:
            scan = os.path.join(d, "ebay_deals.csv")
            out = os.path.join(d, "deals")
            write_scan(scan, [
                {"query": "RTX 3090", "title": "a", "price": "", "win_min": ""},
                {"query": "", "title": "b", "price": "10", "win_min": ""},
                {"query": "RTX 3090", "title": "c", "price": "649.00",
                 "marketplace": "EBAY_DE", "win_min": "450", "win_max": "750"},
            ])
            manifest = split_deals.split_deals(scan, out)
            self.assertEqual(len(manifest), 1)
            self.assertEqual(manifest[0]["rows"], 1)

    def test_slugify(self):
        self.assertEqual(split_deals.slugify("RTX 3090"), "RTX-3090")
        self.assertEqual(split_deals.slugify("DDR4 RDIMM 32GB"), "DDR4-RDIMM-32GB")
        self.assertEqual(split_deals.slugify("  "), "misc")
        self.assertEqual(split_deals.slugify("DDR5 RDIMM"), "DDR5-RDIMM")

    def test_written_rows_total_matches_input(self):
        with temp_dir() as d:
            scan = os.path.join(d, "ebay_deals.csv")
            out = os.path.join(d, "deals")
            rows = [
                {"query": f"Q{i % 3}", "title": f"t{i}", "price": f"{100 + i}.00",
                 "marketplace": "EBAY_DE", "win_min": "1", "win_max": "999"}
                for i in range(9)
            ]
            write_scan(scan, rows)
            manifest = split_deals.split_deals(scan, out)
            self.assertEqual(sum(m["rows"] for m in manifest), 9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
