"""Unit tests for windows.py — adaptive deal windows from price history.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_windows.py
"""
import os
import statistics
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import windows  # noqa: E402


class TestNum(unittest.TestCase):
    def test_parses_numbers(self):
        self.assertEqual(windows.num("42"), 42.0)
        self.assertEqual(windows.num(17), 17.0)
        self.assertEqual(windows.num(17.5), 17.5)
        self.assertIsNone(windows.num("42,5"), "German comma is not accepted")

    def test_rejects_garbage(self):
        self.assertIsNone(windows.num("abc"))
        self.assertIsNone(windows.num(""))
        self.assertIsNone(windows.num(None))


class TestPercentile(unittest.TestCase):
    def test_empty_list(self):
        self.assertIsNone(windows.percentile([], 50))

    def test_linear_interpolation(self):
        # median of sorted [80, 85, 90, 95] quartiles, matching the module's
        # own self-check: p25=83.75, p75=91.25
        self.assertAlmostEqual(windows.percentile([80, 85, 90, 95], 25), 83.75)
        self.assertAlmostEqual(windows.percentile([80, 85, 90, 95], 75), 91.25)
        self.assertAlmostEqual(windows.percentile([80, 85, 90, 95], 50), 87.5)

    def test_endpoints_and_singleton(self):
        self.assertEqual(windows.percentile([5], 50), 5)
        self.assertEqual(windows.percentile([1, 2], 0), 1)
        self.assertEqual(windows.percentile([1, 2], 100), 2)


class TestAdaptiveWindow(unittest.TestCase):
    def test_thin_history_uses_static_window(self):
        for medians in ([], None, [85], [85, None]):
            self.assertEqual(
                windows.adaptive_window(40, 120, medians), (40, 120),
                f"medians={medians}",
            )

    def test_none_static_coerces_to_zero(self):
        self.assertEqual(windows.adaptive_window(None, None, [85]), (0.0, 0.0))

    def test_follows_market_math(self):
        # matches the module's own __main__ self-check exactly
        wmin, wmax = windows.adaptive_window(40, 120, [80, 85, 90, 95])
        self.assertAlmostEqual(wmin, max(40, 0.8 * 83.75))
        self.assertAlmostEqual(wmax, max(120, min(1.5 * 91.25, 2.5 * 87.5)))

    def test_rising_market_widens_window(self):
        wmin, wmax = windows.adaptive_window(40, 120, [80, 100, 120, 140])
        self.assertGreater(wmin, 40)
        self.assertGreater(wmax, 120)

    def test_spike_guard_caps_ceiling(self):
        # one huge spike must not blow the ceiling past 2.5x the median
        medians = [80, 90, 100, 1000]
        _, wmax = windows.adaptive_window(40, 120, medians)
        cap = 2.5 * statistics.median(medians)
        self.assertLessEqual(wmax, cap)
        self.assertGreater(wmax, 120)

    def test_static_floor_respected(self):
        # falling market: floor stays at the static min, ceiling at static max
        wmin, wmax = windows.adaptive_window(40, 120, [10, 12, 14, 16])
        self.assertEqual(wmin, 40)
        self.assertEqual(wmax, 120)

    def test_ignores_none_medians(self):
        wmin, wmax = windows.adaptive_window(40, 120, [None, 80, 85, 90, 95])
        self.assertAlmostEqual(wmin, max(40, 0.8 * 83.75))


class TestLoadRecentMedians(unittest.TestCase):
    def _write(self, path, text):
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(text)

    def test_reads_and_sorts_by_date(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            self._write(
                path,
                "date,marketplace,query,median,cheapest,count,at_target\n"
                "2026-08-15,EBAY_DE,DDR4 RDIMM 32GB,95.00,60.00,42,2\n"
                "2026-08-14,EBAY_DE,DDR4 RDIMM 32GB,85.00,40.00,46,2\n"
                "2026-08-15,EBAY_AT,DDR4 RDIMM 32GB,88.00,50.00,9,0\n",
            )
            out = windows.load_recent_medians(path)
            self.assertEqual(
                out["EBAY_DE · DDR4 RDIMM 32GB"], [85.0, 95.0], "sorted by date"
            )
            self.assertEqual(out["EBAY_AT · DDR4 RDIMM 32GB"], [88.0])

    def test_default_marketplace_when_column_missing(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            self._write(path, "date,query,median\n2026-08-15,RTX 3090,1200.00\n")
            out = windows.load_recent_medians(path)
            self.assertEqual(out["EBAY_DE · RTX 3090"], [1200.0])

    def test_drops_unparsable_medians(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            self._write(
                path,
                "date,marketplace,query,median\n"
                "2026-08-15,EBAY_DE,RTX 3090,n/a\n"
                "2026-08-15,EBAY_DE,RTX 3090,\n",
            )
            self.assertEqual(windows.load_recent_medians(path), {})

    def test_days_limit_keeps_last_n_points(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            self._write(
                path,
                "date,marketplace,query,median\n"
                "2026-08-13,EBAY_DE,RAM,80.00\n"
                "2026-08-14,EBAY_DE,RAM,85.00\n"
                "2026-08-15,EBAY_DE,RAM,90.00\n",
            )
            out = windows.load_recent_medians(path, days=2)
            self.assertEqual(out["EBAY_DE · RAM"], [85.0, 90.0])

    def test_missing_file_returns_empty(self):
        self.assertEqual(windows.load_recent_medians("does-not-exist.csv"), {})


class TestWindowForQuery(unittest.TestCase):
    def test_uses_history_by_key(self):
        hist = {"EBAY_DE · RTX 3090": [80, 85, 90, 95]}
        q = {"name": "RTX 3090", "min": 900, "max": 1600}
        wmin, wmax = windows.window_for_query(q, hist)
        self.assertAlmostEqual(wmin, max(900, 0.8 * 83.75))
        self.assertAlmostEqual(wmax, max(1600, min(1.5 * 91.25, 2.5 * 87.5)))

    def test_no_history_falls_back_to_static(self):
        q = {"name": "RTX 3090", "min": 900, "max": 1600}
        self.assertEqual(windows.window_for_query(q, {}), (900, 1600))
        self.assertEqual(windows.window_for_query(q, None), (900, 1600))

    def test_marketplace_key_variants(self):
        hist = {"EBAY_AT · RTX 3090": [80, 85, 90, 95]}
        q = {"name": "RTX 3090", "min": 900, "max": 1600}
        wmin, wmax = windows.window_for_query(q, hist, marketplace="EBAY_AT")
        self.assertAlmostEqual(wmin, max(900, 0.8 * 83.75))
        # wrong marketplace key -> static window
        self.assertEqual(windows.window_for_query(q, hist, marketplace="EBAY_DE"), (900, 1600))


if __name__ == "__main__":
    unittest.main(verbosity=2)
