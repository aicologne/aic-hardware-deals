"""Unit tests for ebay_search.py — realm detection, item parsing, filters, CSV.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_ebay_search.py
"""
import csv
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import ebay_search  # noqa: E402
import queries  # noqa: E402


class TestDetectRealm(unittest.TestCase):
    def test_sandbox_markers(self):
        self.assertEqual(ebay_search.detect_realm("client-SBX-1", "secret"), "sandbox")
        self.assertEqual(ebay_search.detect_realm("client", "SBX-secret"), "sandbox")
        self.assertEqual(ebay_search.detect_realm("client", "sbx-secret"), "sandbox",
                         "secret check is case-insensitive")

    def test_production_default(self):
        self.assertEqual(ebay_search.detect_realm("client", "secret"), "production")
        self.assertEqual(ebay_search.detect_realm(None, None), "production")
        self.assertEqual(ebay_search.detect_realm("", ""), "production")


class TestParseItem(unittest.TestCase):
    def test_condition_as_object(self):
        it = {
            "title": "  EVGA GeForce RTX 3090 FTW3  ",
            "price": {"value": "649.00", "currency": "EUR"},
            "condition": {"conditionGroup": "USED", "conditionDescription": "Used"},
            "seller": {"username": "demo-seller-1"},
            "itemWebUrl": "https://www.ebay.de/itm/1",
        }
        row = ebay_search.parse_item(it, "RTX 3090", "EBAY_DE", 450, 750)
        self.assertEqual(row["query"], "RTX 3090")
        self.assertEqual(row["title"], "EVGA GeForce RTX 3090 FTW3", "title stripped")
        self.assertEqual(row["price"], "649.00")
        self.assertEqual(row["currency"], "EUR")
        self.assertEqual(row["condition"], "USED", "conditionGroup wins over description")
        self.assertEqual(row["seller"], "demo-seller-1")
        self.assertEqual(row["url"], "https://www.ebay.de/itm/1")
        self.assertEqual(row["marketplace"], "EBAY_DE")
        self.assertEqual(row["win_min"], 450)
        self.assertEqual(row["win_max"], 750)

    def test_condition_as_plain_string(self):
        it = {
            "title": "HP EliteDesk", "price": {"value": "159.50", "currency": "EUR"},
            "condition": "Used", "seller": {"username": "s2"}, "itemWebUrl": "u2",
        }
        row = ebay_search.parse_item(it, "HP EliteDesk 800 G4 Mini", "EBAY_DE")
        self.assertEqual(row["condition"], "Used")
        self.assertEqual(row["win_min"], "", "no window -> empty CSV cell")
        self.assertEqual(row["win_max"], "")

    def test_minimal_item_missing_fields(self):
        it = {"title": "Samsung 32GB DDR4 RDIMM",
              "price": {"value": "89.99", "currency": "EUR"},
              "itemWebUrl": "https://www.ebay.de/itm/demo3"}
        row = ebay_search.parse_item(it, "RAM", "EBAY_DE")
        self.assertEqual(row["condition"], "")
        self.assertEqual(row["seller"], "")
        self.assertEqual(row["price"], "89.99")

    def test_missing_price_object(self):
        it = {"title": "broken", "price": None, "itemWebUrl": "u"}
        row = ebay_search.parse_item(it, "Q", "EBAY_DE")
        self.assertEqual(row["price"], "")
        self.assertEqual(row["currency"], "")


class TestApplyLocalFilters(unittest.TestCase):
    def test_drops_wrong_currency_price_and_condition(self):
        items = [
            {"price": {"value": "100", "currency": "EUR"},
             "condition": {"conditionGroup": "USED"}},
            {"price": {"value": "50", "currency": "EUR"},      # below pmin
             "condition": {"conditionGroup": "USED"}},
            {"price": {"value": "300", "currency": "EUR"},     # above pmax
             "condition": {"conditionGroup": "USED"}},
            {"price": {"value": "100", "currency": "USD"},     # wrong currency
             "condition": {"conditionGroup": "USED"}},
            {"price": {"value": "100", "currency": "EUR"},     # wrong condition
             "condition": {"conditionGroup": "NEW"}},
        ]
        kept, dropped = ebay_search.apply_local_filters(items, 60, 250, "USED", currency="EUR")
        self.assertEqual(len(kept), 1)
        self.assertEqual(dropped, {"currency": 1, "price": 2, "condition": 1, "title": 0})

    def test_no_condition_filter_keeps_all_conditions(self):
        items = [
            {"price": {"value": "100", "currency": "EUR"}, "condition": "New"},
            {"price": {"value": "100", "currency": "EUR"}, "condition": "Used"},
        ]
        kept, dropped = ebay_search.apply_local_filters(items, 0, 200, None, currency="EUR")
        self.assertEqual(len(kept), 2)
        self.assertEqual(dropped, {"currency": 0, "price": 0, "condition": 0, "title": 0})

    def test_boundaries_inclusive(self):
        items = [{"price": {"value": "60", "currency": "EUR"}},
                 {"price": {"value": "250", "currency": "EUR"}}]
        kept, _ = ebay_search.apply_local_filters(items, 60, 250, None, currency="EUR")
        self.assertEqual(len(kept), 2)

    def test_unparsable_price_dropped_as_price(self):
        items = [{"price": {"value": "abc", "currency": "EUR"}}]
        kept, dropped = ebay_search.apply_local_filters(items, 0, 200, None, currency="EUR")
        self.assertEqual(kept, [])
        self.assertEqual(dropped["price"], 1)

    def test_missing_currency_not_dropped(self):
        items = [{"price": {"value": "100"}}]
        kept, dropped = ebay_search.apply_local_filters(items, 0, 200, None, currency="EUR")
        self.assertEqual(len(kept), 1, "empty currency passes the filter")


class TestMatchExclude(unittest.TestCase):
    """The local `exclude` feature, driven by the SHIPPED list.

    The fixture is `queries.EXCLUDE_WORKSTATION_ALL` — the real list the three
    workstation products use — so a change there is exercised here instead of
    drifting silently behind a hand-copied list.
    """

    EXCLUDE = queries.EXCLUDE_WORKSTATION_ALL

    def test_matches_case_insensitively(self):
        self.assertEqual(ebay_search.match_exclude("HP Z8 G4 DEFEKT", self.EXCLUDE), "defekt")
        self.assertEqual(ebay_search.match_exclude("Netzteil 1700W", self.EXCLUDE), "netzteil")

    def test_substring_match_catches_glued_titles(self):
        """Longer terms match inside glued words; the FIRST match wins by list order.

        "Z8G4-CTO-Chassis" matches both "cto" (word) and "chassis" (substring),
        and match_exclude documents list order — not title order — so the
        assertion names the earlier term deliberately.
        """
        self.assertEqual(ebay_search.match_exclude("Z8G4-CTO-Chassis", self.EXCLUDE), "cto")
        self.assertEqual(ebay_search.match_exclude("Z8G4Barebone", self.EXCLUDE), "barebone")
        self.assertEqual(ebay_search.match_exclude("Z8G4-Netzteil", self.EXCLUDE), "netzteil")

    def test_returns_none_for_clean_title(self):
        self.assertIsNone(ebay_search.match_exclude(
            "HP Z8 G4 Workstation 2x Xeon Gold 6148 128GB RTX 4000", self.EXCLUDE))

    def test_short_terms_do_not_match_inside_words(self):
        """The MAJOR review finding: 'cto' must not fire on 'Octo'/'vector'."""
        self.assertIsNone(ebay_search.match_exclude("OCTO Core Server", self.EXCLUDE))
        self.assertIsNone(ebay_search.match_exclude(
            "Workstation für Vectorworks", self.EXCLUDE))

    def test_short_terms_still_match_as_whole_words(self):
        self.assertEqual(ebay_search.match_exclude("HP Z8 G4 CTO Chassis", self.EXCLUDE), "cto")
        self.assertEqual(
            ebay_search.match_exclude("HP Z8 G4 (CTO) ohne RAM", self.EXCLUDE), "cto")

    def test_complete_machine_listing_its_cpu_survives(self):
        """The core false-positive guard: a complete system may say 'CPU'."""
        self.assertIsNone(ebay_search.match_exclude(
            "HP Z8 G4 Workstation 2x Xeon Gold 6132 CPU 128GB 1TB", self.EXCLUDE))
        self.assertIsNone(ebay_search.match_exclude(
            "Dell Precision 7920 Tower 2x Xeon Silver 4114 CPU", self.EXCLUDE))

    def test_no_exclude_list_and_missing_title_are_safe(self):
        self.assertIsNone(ebay_search.match_exclude("HP Z8 G4 defekt", None))
        self.assertIsNone(ebay_search.match_exclude("HP Z8 G4 defekt", []))
        self.assertIsNone(ebay_search.match_exclude(None, self.EXCLUDE))
        self.assertIsNone(ebay_search.match_exclude("", self.EXCLUDE))

    def test_a_bare_string_is_treated_as_one_term(self):
        """Iterating a string would make every letter a term ('d' matches all)."""
        self.assertEqual(ebay_search.match_exclude("HP Z8 G4 defekt", "defekt"), "defekt")
        self.assertIsNone(ebay_search.match_exclude("HP Z8 G4 Workstation 128GB", "defekt"))

    def test_blank_and_whitespace_terms_never_match(self):
        self.assertIsNone(ebay_search.match_exclude("HP Z8 G4", ["  ", ""]))

    def test_umlaut_variant_matches_needing_lowercase_config(self):
        # titles often drop the umlaut; the exclude list carries both variants
        self.assertEqual(
            ebay_search.match_exclude("Kühler für Z8 G4", ["kühler", "kuehler"]), "kühler")
        self.assertEqual(
            ebay_search.match_exclude("Kuehler Z8 G4", ["kühler", "kuehler"]), "kuehler")

    def test_filter_drops_excluded_titles_and_counts_them(self):
        items = [
            {"title": "HP Z8 G4 Workstation 2x Xeon 128GB",
             "price": {"value": "2400", "currency": "EUR"},
             "condition": {"conditionGroup": "USED"}},
            {"title": "HP Z8 G4 Netzteil 1700W",
             "price": {"value": "209", "currency": "EUR"},
             "condition": {"conditionGroup": "USED"}},
            {"title": "HP Z8 G4 CTO Chassis ohne CPU",
             "price": {"value": "882", "currency": "EUR"},
             "condition": {"conditionGroup": "USED"}},
        ]
        kept, dropped = ebay_search.apply_local_filters(
            items, 100, 13500, "USED", currency="EUR", exclude=self.EXCLUDE)
        self.assertEqual([i["title"] for i in kept], ["HP Z8 G4 Workstation 2x Xeon 128GB"])
        self.assertEqual(dropped["title"], 2)
        self.assertEqual(dropped["price"], 0, "excludes are counted separately from price")

    def test_filter_without_exclude_list_keeps_parts(self):
        items = [{"title": "HP Z8 G4 Netzteil 1700W",
                  "price": {"value": "209", "currency": "EUR"},
                  "condition": {"conditionGroup": "USED"}}]
        kept, dropped = ebay_search.apply_local_filters(items, 100, 13500, "USED", currency="EUR")
        self.assertEqual(len(kept), 1, "no exclude list configured -> no title filtering")
        self.assertEqual(dropped["title"], 0)


class TestLoadEnvFile(unittest.TestCase):
    def test_loads_and_does_not_override(self):
        with temp_dir() as d:
            path = os.path.join(d, "test.env")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# comment\nEBAY_TEST_A=one\nEBAY_TEST_B=two\n")
            os.environ.pop("EBAY_TEST_A", None)
            os.environ.pop("EBAY_TEST_B", None)
            try:
                os.environ["EBAY_TEST_A"] = "already-set"
                ebay_search.load_env_file((path,))
                self.assertEqual(os.environ["EBAY_TEST_A"], "already-set",
                                 "existing vars are not overridden")
                self.assertEqual(os.environ["EBAY_TEST_B"], "two")
            finally:
                os.environ.pop("EBAY_TEST_A", None)
                os.environ.pop("EBAY_TEST_B", None)

    def test_missing_file_is_ignored(self):
        ebay_search.load_env_file(("does-not-exist.env",))  # must not raise


class TestWriteCSV(unittest.TestCase):
    def test_writes_header_and_rows(self):
        with temp_dir() as d, mock.patch("sys.stdout", new=mock.MagicMock()):
            path = os.path.join(d, "deals.csv")
            rows = [{
                "query": "RTX 3090", "title": "EVGA 3090", "price": "649.00",
                "currency": "EUR", "condition": "Used", "seller": "s1",
                "url": "u1", "marketplace": "EBAY_DE", "win_min": "450", "win_max": "750",
            }]
            ebay_search.write_csv(rows, path)
            with open(path, encoding="utf-8-sig", newline="") as f:
                data = list(csv.DictReader(f))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["query"], "RTX 3090")
            self.assertEqual(list(data[0].keys()), ebay_search.CSV_FIELDS)

    def test_empty_rows_do_not_create_file(self):
        with temp_dir() as d, mock.patch("sys.stdout", new=mock.MagicMock()):
            path = os.path.join(d, "deals.csv")
            ebay_search.write_csv([], path)
            self.assertFalse(os.path.exists(path))


class TestScanMarketplaceDemo(unittest.TestCase):
    def test_demo_mode_parses_all_demo_items(self):
        # wide window + no condition filter so all DEMO_ITEMS survive the
        # client-side filters (their prices are 649/159.50/89.99 EUR)
        q = {"name": "RTX 3090", "q": "RTX 3090", "min": 0, "max": 2000,
             "cond": None, "category": 27386}
        with mock.patch.object(ebay_search.time, "sleep"), \
             mock.patch("sys.stdout", new=mock.MagicMock()):
            rows = ebay_search.scan_marketplace(
                [q], "client", "secret", "EBAY_DE", "EUR", "production", demo=True
            )
        self.assertEqual(len(rows), len(ebay_search.DEMO_ITEMS))
        self.assertEqual(rows[0]["query"], "RTX 3090")
        self.assertEqual(rows[0]["win_min"], 0)
        self.assertEqual(rows[0]["win_max"], 2000)
        # condition object vs string vs missing all parse
        self.assertEqual(rows[0]["condition"], "Used")
        self.assertEqual(rows[1]["condition"], "USED")
        self.assertEqual(rows[2]["condition"], "")

    def test_demo_mode_with_relay_flag_still_uses_demo_items(self):
        q = {"name": "RAM", "q": "RAM", "min": 0, "max": 2000, "cond": None}
        with mock.patch.object(ebay_search.time, "sleep"), \
             mock.patch("sys.stdout", new=mock.MagicMock()):
            rows = ebay_search.scan_marketplace(
                [q], "client", "secret", "EBAY_DE", "EUR", "relay", demo=True
            )
        self.assertEqual(len(rows), len(ebay_search.DEMO_ITEMS))

    def test_scan_applies_the_query_exclude_list(self):
        """End-to-end wiring: a query's `exclude` must actually drop rows.

        Without this, deleting the `exclude=` keyword at the
        scan_marketplace -> apply_local_filters call site would keep the whole
        suite green while parts silently reappear in the report.
        """
        q = {"name": "HP Z8 G4 Workstation", "q": "HP Z8 G4", "min": 1000,
             "max": 13500, "cond": "USED", "category": 171957,
             "exclude": list(queries.EXCLUDE_WORKSTATION_ALL)}
        items = [
            {"title": "HP Z8 G4 Workstation 2x Xeon 128GB",
             "price": {"value": "2400", "currency": "EUR"},
             "condition": {"conditionGroup": "USED"}},
            {"title": "HP Z8 G4 Netzteil 1700W",
             "price": {"value": "1200", "currency": "EUR"},
             "condition": {"conditionGroup": "USED"}},
            {"title": "HP Z8 G4 CTO Chassis ohne CPU",
             "price": {"value": "1100", "currency": "EUR"},
             "condition": {"conditionGroup": "USED"}},
        ]
        with mock.patch.object(ebay_search, "relay_search",
                               return_value={"itemSummaries": items}), \
             mock.patch.object(ebay_search.time, "sleep"), \
             mock.patch("sys.stdout", new=mock.MagicMock()):
            rows = ebay_search.scan_marketplace(
                [q], "client", "secret", "EBAY_DE", "EUR", "relay", relay="http://127.0.0.1:1"
            )
        self.assertEqual(len(rows), 1, "parts and barebones must not reach the CSV")
        self.assertEqual(rows[0]["title"], "HP Z8 G4 Workstation 2x Xeon 128GB")
        self.assertEqual(rows[0]["query"], "HP Z8 G4 Workstation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
