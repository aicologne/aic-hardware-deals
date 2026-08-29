"""Unit tests for render_report.py — LATEST.md report helpers.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_render_report.py
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import render_report  # noqa: E402


class TestNumEuro(unittest.TestCase):
    def test_num(self):
        self.assertEqual(render_report.num("42"), 42.0)
        self.assertIsNone(render_report.num("abc"))
        self.assertIsNone(render_report.num(None))

    def test_euro_german_format(self):
        self.assertEqual(render_report.euro(42), "€42,00")
        self.assertEqual(render_report.euro(1750.5), "€1.750,50")
        self.assertEqual(render_report.euro(None), "—")


class TestNetEuro(unittest.TestCase):
    def test_fee_rate_applied(self):
        with mock.patch.object(render_report, "FEE_RATE", 0.13):
            self.assertEqual(render_report.net_euro(100), "€87,00")
            self.assertEqual(render_report.net_euro(1750), "€1.522,50")

    def test_none_price(self):
        with mock.patch.object(render_report, "FEE_RATE", 0.13):
            self.assertEqual(render_report.net_euro(None), "—")

    def test_zero_fee_hides_column(self):
        with mock.patch.object(render_report, "FEE_RATE", 0.0):
            self.assertEqual(render_report.net_euro(100), "—")


class TestPct(unittest.TestCase):
    def test_formatting(self):
        self.assertEqual(render_report.pct(12.5), "+12,5 %")
        self.assertEqual(render_report.pct(-3), "-3,0 %")
        self.assertEqual(render_report.pct(0), "0,0 %", "zero has no plus sign")
        self.assertEqual(render_report.pct(None), "—")


class TestFlagFor(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(
            render_report.flag_for({"_price": 40, "_win_min": 40, "_win_max": 120}),
            "🔥 at/near buy-low target",
        )
        # exactly 1.15x -> still flagged
        self.assertEqual(
            render_report.flag_for({"_price": 46, "_win_min": 40, "_win_max": 120}),
            "🔥 at/near buy-low target",
        )
        self.assertEqual(
            render_report.flag_for({"_price": 46.01, "_win_min": 40, "_win_max": 120}),
            "ok",
        )
        self.assertEqual(
            render_report.flag_for({"_price": 130, "_win_min": 40, "_win_max": 120}),
            "⚠️ above scan window",
        )
        self.assertEqual(render_report.flag_for({"_price": 5}), "ok")


class TestCapacity(unittest.TestCase):
    def test_capacity_gb_map(self):
        self.assertEqual(render_report.capacity_gb("RTX 3090"), 24)
        self.assertEqual(render_report.capacity_gb("DDR4 RDIMM 32GB"), 32)
        self.assertIsNone(render_report.capacity_gb("Nvidia Quadro RTX"))

    def test_euro_per_gb(self):
        self.assertAlmostEqual(render_report.euro_per_gb(88, "DDR4 RDIMM 32GB"), 2.75)
        self.assertAlmostEqual(render_report.euro_per_gb(1000, "RTX 3090"), 1000 / 24)
        self.assertIsNone(render_report.euro_per_gb(None, "RTX 3090"))
        self.assertIsNone(render_report.euro_per_gb(500, "Nvidia Quadro RTX"))

    def test_euro_per_gb_str(self):
        self.assertEqual(render_report.euro_per_gb_str(88, "DDR4 RDIMM 32GB"), "2,75/GB")
        self.assertEqual(render_report.euro_per_gb_str(1000, "RTX 3090"), "41,67/GB")
        self.assertEqual(render_report.euro_per_gb_str(500, "Nvidia Quadro RTX"), "—")


class TestLoadHistory(unittest.TestCase):
    def test_reads_groups_and_sorts(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(
                    "date,marketplace,query,median,cheapest,count,at_target\n"
                    "2026-08-15,EBAY_DE,DDR4 RDIMM 32GB,95.00,60.00,42,2\n"
                    "2026-08-14,EBAY_DE,DDR4 RDIMM 32GB,85.00,40.00,46,2\n"
                    "2026-08-15,EBAY_AT,DDR4 RDIMM 32GB,88.00,50.00,9,0\n"
                    "2026-08-15,EBAY_DE,BAD,n/a,0,0,0\n"
                )
            out = render_report.load_history(path)
            self.assertEqual(
                out["EBAY_DE · DDR4 RDIMM 32GB"],
                [("2026-08-14", 85.0), ("2026-08-15", 95.0)],
            )
            self.assertEqual(out["EBAY_AT · DDR4 RDIMM 32GB"], [("2026-08-15", 88.0)])
            self.assertNotIn("EBAY_DE · BAD", out)

    def test_missing_path(self):
        self.assertEqual(render_report.load_history(None), {})
        self.assertEqual(render_report.load_history("does-not-exist.csv"), {})


class TestTrendStr(unittest.TestCase):
    def test_two_points(self):
        history = {"EBAY_DE · RTX 3090": [("2026-08-14", 85.0), ("2026-08-18", 95.0)]}
        self.assertEqual(
            render_report.trend_str(history, "EBAY_DE · RTX 3090"),
            "€85,00→€95,00 (2d)",
        )

    def test_thin_or_missing_history(self):
        self.assertIsNone(render_report.trend_str({}, "EBAY_DE · X"))
        self.assertIsNone(
            render_report.trend_str({"EBAY_DE · X": [("2026-08-18", 95.0)]}, "EBAY_DE · X")
        )


class TestMovers(unittest.TestCase):
    def _mk(self):
        return {
            "EBAY_DE · DDR4 RDIMM 32GB": [
                ("2026-08-11", 80.0), ("2026-08-14", 85.0), ("2026-08-18", 95.0),
            ],
            "EBAY_DE · Nvidia Quadro RTX": [
                ("2026-08-10", 600.0), ("2026-08-17", 620.0), ("2026-08-18", 580.0),
            ],
            "EBAY_DE · OptiPlex 3070 Micro": [
                ("2026-08-17", 140.0), ("2026-08-18", 140.0),
            ],
            "EBAY_DE · Single": [("2026-08-18", 100.0)],
        }

    def test_movers_math(self):
        mv = render_report.movers(self._mk())
        self.assertGreaterEqual(len(mv), 2, "flat/single excluded, risers/fallers included")
        by_key = {m[0]: m for m in mv}
        ram = by_key["EBAY_DE · DDR4 RDIMM 32GB"]
        self.assertEqual(ram[1], 95.0)                 # latest
        self.assertEqual(ram[2], 80.0)                 # ref
        self.assertEqual(ram[3], "2026-08-11")         # ref_date
        self.assertAlmostEqual(ram[4], (95 - 80) / 80 * 100)
        gpu = by_key["EBAY_DE · Nvidia Quadro RTX"]
        self.assertEqual(gpu[2], 620.0, "ref is the earliest point at-or-after 7 days back")
        flat = by_key.get("EBAY_DE · OptiPlex 3070 Micro")
        self.assertEqual(flat[4], 0.0, "flat series is a mover with delta 0")
        self.assertNotIn("EBAY_DE · Single", by_key, "single-point series is not a mover")

    def test_sorted_by_abs_delta(self):
        mv = render_report.movers(self._mk())
        deltas = [abs(m[4]) for m in mv]
        self.assertEqual(deltas, sorted(deltas, reverse=True))

    def test_empty_history(self):
        self.assertEqual(render_report.movers({}), [])

    def test_falls_back_to_previous_point(self):
        # no point within 7 days -> previous scan is the reference
        history = {"EBAY_DE · Old": [("2026-08-01", 100.0), ("2026-08-18", 120.0)]}
        mv = render_report.movers(history)
        self.assertEqual(len(mv), 1)
        self.assertEqual(mv[0][2], 100.0)
        self.assertEqual(mv[0][3], "2026-08-01")
        self.assertAlmostEqual(mv[0][4], 20.0)


class TestLoadSoldAnchors(unittest.TestCase):
    def test_reads(self):
        with temp_dir() as d:
            path = os.path.join(d, "sold_anchors.csv")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(
                    "query,marketplace,median_sold,cheapest_sold,sample_size,fetched_at\n"
                    "RTX 3090,EBAY_DE,1200.00,900.00,12,2026-08-26\n"
                    "RAM,EBAY_DE,,,2,2026-08-26\n"  # no median -> skipped
                )
            out = render_report.load_sold_anchors(path)
            self.assertEqual(out["RTX 3090"], {"median_sold": 1200.0, "sample_size": 12})
            self.assertNotIn("RAM", out)

    def test_missing_path(self):
        self.assertEqual(render_report.load_sold_anchors(None), {})
        self.assertEqual(render_report.load_sold_anchors("does-not-exist.csv"), {})


class TestRepricedNote(unittest.TestCase):
    def test_repriced(self):
        lh = {
            "https://x/1": {
                "first_price": "42.00", "last_price": "50.00", "first_seen": "2026-08-14",
            }
        }
        self.assertEqual(
            render_report.repriced_note({"url": "https://x/1"}, lh),
            "was €42,00 on 2026-08-14",
        )

    def test_not_repriced_or_unknown(self):
        self.assertEqual(render_report.repriced_note({"url": "https://y"}, {}), "")
        lh = {
            "https://x/1": {
                "first_price": "42.00", "last_price": "42.00", "first_seen": "2026-08-14",
            }
        }
        self.assertEqual(render_report.repriced_note({"url": "https://x/1"}, lh), "")


class TestLoadListingHistory(unittest.TestCase):
    def test_reads(self):
        with temp_dir() as d:
            path = os.path.join(d, "listing_history.csv")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(
                    "url,query,marketplace,first_seen,first_price,last_seen,last_price\n"
                    "https://x/1,DDR4 RDIMM 32GB,EBAY_DE,2026-08-14,42.00,2026-08-18,50.00\n"
                )
            out = render_report.load_listing_history(path)
            self.assertEqual(out["https://x/1"]["first_price"], "42.00")

    def test_missing_path(self):
        self.assertEqual(render_report.load_listing_history("does-not-exist.csv"), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
