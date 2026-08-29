"""Unit tests for notify.py — buy-low and price-drop alert logic.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_notify.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import notify  # noqa: E402


class TestNum(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(notify.num("42"), 42.0)
        self.assertEqual(notify.num(17), 17.0)
        self.assertIsNone(notify.num("abc"))
        self.assertIsNone(notify.num(None))


class TestEuro(unittest.TestCase):
    def test_german_formatting(self):
        self.assertEqual(notify.euro(42), "€42,00")
        self.assertEqual(notify.euro(1750.5), "€1.750,50")
        self.assertEqual(notify.euro(1234567.891), "€1.234.567,89")
        self.assertEqual(notify.euro(None), "—")

    def test_string_input_raises(self):
        # unlike the JS mirror, the Python euro() formats with :,.2f and
        # requires a number; callers always pass num() first
        with self.assertRaises(ValueError):
            notify.euro("89.99")


class TestFlaggedRows(unittest.TestCase):
    def test_buy_low_rule(self):
        rows = [
            {"url": "u1", "price": "40", "win_min": "40"},
            {"url": "u2", "price": "46", "win_min": "40"},     # exactly 1.15x -> flagged
            {"url": "u3", "price": "46.01", "win_min": "40"},  # over 1.15x -> not flagged
            {"url": "u4", "price": "x", "win_min": "40"},      # unparsable -> not flagged
            {"url": "u5", "price": "40"},                       # no win_min -> not flagged
        ]
        flagged = notify.flagged_rows(rows)
        self.assertEqual([r["url"] for r in flagged], ["u1", "u2"])

    def test_empty_input(self):
        self.assertEqual(notify.flagged_rows([]), [])


class TestStateRoundtrip(unittest.TestCase):
    def test_missing_file(self):
        self.assertEqual(notify.load_state("does-not-exist.json"), {})

    def test_roundtrip(self):
        with temp_dir() as d:
            path = os.path.join(d, "notified.json")
            state = {"https://ebay.de/x": "2026-08-14T00:00:00+00:00"}
            notify.save_state(path, state)
            self.assertEqual(notify.load_state(path), state)

    def test_corrupt_or_non_dict_json(self):
        with temp_dir() as d:
            for content in ("{not json", "[1,2,3]", '"string"', "null"):
                path = os.path.join(d, "notified.json")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.assertEqual(notify.load_state(path), {}, f"content={content!r}")

    def test_save_creates_missing_dirs(self):
        with temp_dir() as d:
            path = os.path.join(d, "nested", "deep", "notified.json")
            notify.save_state(path, {"a": 1})
            self.assertTrue(os.path.exists(path))


class TestBuildMessage(unittest.TestCase):
    def test_message_layout(self):
        items = [
            {
                "query": "RTX 3090", "price": "649.00", "title": "EVGA 3090 FTW3",
                "url": "https://www.ebay.de/itm/1", "win_min": "450",
                "seller": "demo-seller", "condition": "Used",
            }
        ]
        msg = notify.build_message(items, "2026-08-26")
        lines = msg.splitlines()
        self.assertEqual(lines[0], "🔥 1 new buy-low deal(s) — 2026-08-26")
        self.assertEqual(lines[1], "")
        self.assertIn("1. [RTX 3090] €649,00 — EVGA 3090 FTW3", lines[2])
        self.assertIn("https://www.ebay.de/itm/1", lines[3])
        self.assertIn("target €450,00 · seller demo-seller · Used", lines[4])

    def test_missing_fields_fall_back(self):
        msg = notify.build_message([{"query": "Q"}], "2026-08-26")
        self.assertIn("— — (no title)", msg)
        self.assertIn("target — · seller ? · ?", msg)

    def test_max_items_cap(self):
        items = [{"query": "Q", "price": "1", "title": "t", "url": "u",
                  "win_min": "1", "seller": "s", "condition": "c"} for _ in range(25)]
        msg = notify.build_message(items, "2026-08-26")
        self.assertIn("…and 5 more — see the full report.", msg)
        # exactly MAX_ITEMS numbered entries
        self.assertEqual(sum(1 for line in msg.splitlines() if line.startswith(tuple(f"{i}." for i in range(1, 21)))), notify.MAX_ITEMS)


class TestLoadListingHistory(unittest.TestCase):
    def test_reads_csv_keyed_by_url(self):
        with temp_dir() as d:
            path = os.path.join(d, "listing_history.csv")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(
                    "url,query,marketplace,first_seen,first_price,last_seen,last_price\n"
                    "https://x/1,DDR4 RDIMM 32GB,EBAY_DE,2026-08-14,42.00,2026-08-18,50.00\n"
                )
            out = notify.load_listing_history(path)
            self.assertEqual(out["https://x/1"]["first_price"], "42.00")
            self.assertEqual(out["https://x/1"]["last_price"], "50.00")

    def test_missing_file(self):
        self.assertEqual(notify.load_listing_history("does-not-exist.csv"), {})


class TestDropRows(unittest.TestCase):
    ROWS = [
        {"url": "u1", "price": "85"},   # 15% below first -> included
        {"url": "u2", "price": "95"},   # exactly 5% -> included (>= threshold)
        {"url": "u3", "price": "98"},   # 2% -> below threshold
        {"url": "u4", "price": "100"},  # unchanged -> no drop
        {"url": "u5", "price": "90"},   # no history -> skipped
    ]
    HISTORY = {
        "u1": {"first_price": "100", "last_price": "85", "first_seen": "2026-08-14"},
        "u2": {"first_price": "100", "last_price": "95", "first_seen": "2026-08-14"},
        "u3": {"first_price": "100", "last_price": "98", "first_seen": "2026-08-14"},
        "u4": {"first_price": "100", "last_price": "100", "first_seen": "2026-08-14"},
    }

    def test_detects_and_sorts_by_drop_size(self):
        drops = notify.drop_rows(self.ROWS, self.HISTORY)
        urls = [d[0]["url"] for d in drops]
        self.assertEqual(urls, ["u1", "u2"], "only >= 5% drops, biggest first")
        self.assertAlmostEqual(drops[0][4], 15.0)   # pct
        self.assertEqual(drops[0][2], 100.0)        # first
        self.assertEqual(drops[0][1], 85.0)         # last
        self.assertEqual(drops[0][3], "2026-08-14")  # first_seen

    def test_custom_threshold(self):
        drops = notify.drop_rows(self.ROWS, self.HISTORY, threshold=0.10)
        urls = [d[0]["url"] for d in drops]
        self.assertEqual(urls, ["u1"])

    def test_empty_inputs(self):
        self.assertEqual(notify.drop_rows([], {}), [])
        self.assertEqual(notify.drop_rows(self.ROWS, {}), [])


class TestBuildDropMessage(unittest.TestCase):
    def test_layout(self):
        drops = [
            (
                {"url": "https://www.ebay.de/itm/1", "query": "RTX 3090", "price": "85",
                 "title": "3090", "seller": "s", "condition": "Used"},
                85.0, 100.0, "2026-08-14", 15.0,
            )
        ]
        msg = notify.build_drop_message(drops, "2026-08-26")
        lines = msg.splitlines()
        self.assertEqual(lines[0], "📉 1 price drop(s) on watched listings — 2026-08-26")
        self.assertIn("1. [RTX 3090] €85,00 (was €100,00 on 2026-08-14, −15.0 %) — 3090", lines[2])
        self.assertIn("https://www.ebay.de/itm/1", lines[3])

    def test_cap(self):
        drops = [
            ({"url": f"u{i}", "query": "Q", "price": "1", "title": "t",
              "seller": "s", "condition": "c"}, 1.0, 2.0, "2026-08-14", 50.0)
            for i in range(25)
        ]
        msg = notify.build_drop_message(drops, "2026-08-26")
        self.assertIn("…and 5 more drops — see the full report.", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
