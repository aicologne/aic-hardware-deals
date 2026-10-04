"""Unit tests for queries.py — the single source of truth for products.

Every product the pipeline tracks lives in DEFAULT_QUERIES; this suite guards
the derived views (€/GB capacities, Marketplace products) so a new product
cannot silently break the report or the board.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_queries.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import queries  # noqa: E402


class TestDEFAULT_QUERIES(unittest.TestCase):
    def test_every_product_has_required_fields(self):
        for q in queries.DEFAULT_QUERIES:
            for field in ("name", "q", "min", "max", "cond", "category"):
                self.assertIn(field, q, f"{q.get('name')} missing {field}")
            self.assertIsInstance(q["min"], (int, float))
            self.assertIsInstance(q["max"], (int, float))
            self.assertLess(q["min"], q["max"], f"{q['name']}: min < max")

    def test_names_are_unique(self):
        names = [q["name"] for q in queries.DEFAULT_QUERIES]
        self.assertEqual(len(names), len(set(names)), "product names must be unique")


class TestCapacityMap(unittest.TestCase):
    def test_derives_from_queries(self):
        cm = queries.capacity_map()
        self.assertGreaterEqual(len(cm), 10, "most GPUs/RAM have a capacity")
        # spot-check known values
        self.assertEqual(cm.get("RTX 3090"), 24)
        self.assertEqual(cm.get("DDR4 RDIMM 32GB"), 32)
        self.assertEqual(cm.get("DDR4 RDIMM 64GB"), 64)
        self.assertEqual(cm.get("DDR5 32GB"), 32)

    def test_mixed_categories_are_absent(self):
        cm = queries.capacity_map()
        self.assertNotIn("Nvidia Quadro RTX", cm, "mixed-capacity category has no entry")

    def test_consistent_with_csv_js_fallback(self):
        # csv.js keeps a static fallback map for the single-CSV mode; it must
        # not drift from the single source of truth. The check is BIDIRECTIONAL:
        # a key present in queries.py but missing in csv.js silently renders
        # "—" for €/GB whenever the fallback path is used, which a one-way
        # check cannot see.
        import re
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(repo, "site", "csv.js")
        with open(path, encoding="utf-8") as f:
            js = f.read()
        pairs = re.findall(r"'([^']+)':\s*(\d+)", js.split("export const CAPACITY_GB")[1].split("};")[0])
        js_map = {k: int(v) for k, v in pairs}
        cm = queries.capacity_map()
        for name, gb in js_map.items():
            self.assertEqual(cm.get(name), gb,
                             f"csv.js fallback {name}={gb} disagrees with queries.py")
        for name, gb in cm.items():
            self.assertIn(name, js_map,
                          f"queries.py has {name}={gb} but csv.js CAPACITY_GB lacks it "
                          f"(€/GB renders '—' in single-CSV fallback mode)")


class TestDealWindows(unittest.TestCase):
    """Guards that a price window is actually deal-hunting, not just parseable.

    test_every_product_has_required_fields only checks structure (field present,
    min < max, name unique). A window that admits spare parts of a model whose
    barebone chassis alone asks 882 € passes that — and still fills the scan
    with parts. These tests check the *deal* properties.

    Scope note: these are UPPER AND LOWER GUARDS against typos and drift, not a
    market-quality verdict. Freshness and correctness of the windows themselves
    are a human/research concern (see the anchors documented in queries.py).
    """

    # A window must at least span a meaningful band of the market. The narrowest
    # window today is RTX 4080 Super at 650–900 (1.38x) — a real 16 GB GPU band
    # this repo chose deliberately — so the floor sits just below it. Below ~1.3x
    # a window would be a single price point with noise margins, not a market.
    MIN_WINDOW_RATIO = 1.3
    # Widest today: HP Z8 G4 Workstation at 1.000–13.500 (13.5x), because a
    # dual-socket tower genuinely spans a barebone entry config to a 1.5 TB
    # flagship. Past 20x a window spans several product classes and can no
    # longer rank deals — that is a typo, not a decision.
    MAX_WINDOW_RATIO = 20

    def test_products_carrying_a_barebone_floor_are_not_barebone_scanners(self):
        """`min` must sit above the documented barebone/parts price."""
        annotated = {q["name"]: q for q in queries.DEFAULT_QUERIES
                     if q.get("barebone_floor_eur") is not None}
        for name, q in annotated.items():
            floor = q["barebone_floor_eur"]
            self.assertIsInstance(floor, (int, float), f"{name}: floor must be numeric")
            self.assertGreaterEqual(
                q["min"], floor,
                f"{name}: min {q['min']} is at/below the barebone price {floor} — "
                f"the window would scan spare parts")

    def test_the_workstation_entries_keep_their_barebone_floor(self):
        """Losing the annotation would silently drop the deal-quality guarantee."""
        names = {q["name"] for q in queries.DEFAULT_QUERIES if q.get("barebone_floor_eur")}
        for expected in ("HP Z8 G4 Workstation", "Dell Precision 7920 Tower",
                         "Lenovo ThinkStation P920"):
            self.assertIn(expected, names,
                          f"{expected} must keep barebone_floor_eur documented")

    def test_every_window_is_wide_enough_to_hold_a_market(self):
        """A too-narrow window is the failure mode windows.py exists to avoid."""
        for q in queries.DEFAULT_QUERIES:
            self.assertGreaterEqual(
                q["max"] / q["min"], self.MIN_WINDOW_RATIO,
                f"{q['name']}: window {q['min']}–{q['max']} is too narrow to "
                f"contain a market")

    def test_no_window_spans_absurd_segments(self):
        for q in queries.DEFAULT_QUERIES:
            ratio = q["max"] / q["min"]
            self.assertLess(
                ratio, self.MAX_WINDOW_RATIO,
                f"{q['name']}: window {q['min']}–{q['max']} spans {ratio:.1f}x — "
                f"split it into tiers instead")

    def test_exclude_entries_are_lowercase_nonempty_strings(self):
        for q in queries.DEFAULT_QUERIES:
            exclude = q.get("exclude")
            if exclude is None:
                continue
            self.assertIsInstance(exclude, list, f"{q['name']}: exclude must be a list")
            for term in exclude:
                self.assertIsInstance(term, str, f"{q['name']}: exclude terms must be str")
                self.assertTrue(term.strip(), f"{q['name']}: empty exclude term")
                self.assertEqual(term, term.strip(), f"{q['name']}: '{term}' not stripped")
                self.assertEqual(term, term.lower(),
                                 f"{q['name']}: '{term}' must be lowercase to match titles")
                self.assertNotIn(",", term, f"{q['name']}: '{term}' would split a term list")

    def test_exclude_lists_have_no_duplicates(self):
        for q in queries.DEFAULT_QUERIES:
            exclude = q.get("exclude") or []
            self.assertEqual(len(exclude), len(set(exclude)),
                             f"{q['name']}: duplicate exclude term")

    def test_ambiguous_short_terms_never_hit_as_substrings(self):
        """ebay_search matches terms shorter than WORD_MATCH_MIN_LEN as whole
        words only, so a short term cannot kill a complete listing that merely
        contains it ("cpu" inside a CPU spec line, "cto" inside "Octo"). Guard
        the boundary length itself — a 4-character term would silently flip
        back to substring matching."""
        # `ebay_search.WORD_MATCH_MIN_LEN` is the boundary the scanner actually
        # applies; 5 chars separates distinctive part names from ambiguous
        # short ones. A 4-char term would silently flip back to substring
        # matching and start dropping complete listings.
        import ebay_search  # noqa: E402 - same directory, importable at test time
        for name in ("EXCLUDE_WORKSTATION_WORDS", "EXCLUDE_WORKSTATION_PARTS"):
            for term in getattr(queries, name):
                self.assertGreaterEqual(
                    len(term), 3,
                    f"{name}: '{term}' is too short even for whole-word matching")
        for term in queries.EXCLUDE_WORKSTATION_WORDS:
            self.assertLess(
                len(term), ebay_search.WORD_MATCH_MIN_LEN,
                f"'{term}' is in the WORD list but long enough for substring matching — "
                f"it belongs in EXCLUDE_WORKSTATION_PARTS")
        for term in queries.EXCLUDE_WORKSTATION_PARTS:
            self.assertGreaterEqual(
                len(term), ebay_search.WORD_MATCH_MIN_LEN,
                f"'{term}' is in the SUBSTRING list but short enough to need word "
                f"boundaries — it belongs in EXCLUDE_WORKSTATION_WORDS")

    def test_the_shared_list_is_what_the_workstations_use(self):
        """A product must carry a COPY, and the copy must be the full list."""
        for q in queries.DEFAULT_QUERIES:
            if q.get("barebone_floor_eur") is None:
                continue
            exclude = q.get("exclude") or []
            for term in queries.EXCLUDE_WORKSTATION_ALL:
                self.assertIn(term, exclude, f"{q['name']} lost exclude term '{term}'")
            self.assertIsNot(
                exclude, queries.EXCLUDE_WORKSTATION_ALL,
                f"{q['name']} aliases the shared list — a mutation would leak")

    def test_parts_heavy_products_declare_excludes(self):
        """Barebone scanners must carry an `exclude` list to stay useful."""
        annotated = {q["name"]: q for q in queries.DEFAULT_QUERIES
                     if q.get("barebone_floor_eur") is not None}
        for name, q in annotated.items():
            self.assertTrue(
                q.get("exclude"),
                f"{name}: a barebone floor without `exclude` cannot tell a "
                f"complete machine from its spare parts")
        self.assertGreaterEqual(
            len(annotated), 3,
            "the workstation entries are the reference set for this contract")


class TestMarketplaceProducts(unittest.TestCase):
    def test_derives_mp_products(self):
        products = queries.marketplace_products()
        self.assertGreaterEqual(len(products), 4)
        names = [p[0] for p in products]
        self.assertIn("RTX 3090", names)
        self.assertIn("DDR4 RDIMM 32GB", names)

    def test_keyword_defaults_to_name(self):
        products = queries.marketplace_products()
        by_name = {p[0]: p for p in products}
        ddr4 = by_name["DDR4 RDIMM 32GB"]
        self.assertEqual(ddr4[1], "DDR4 RDIMM 32GB", "keyword defaults to name")
        self.assertEqual(ddr4[2].get("max"), 120)

    def test_override_keyword(self):
        products = queries.marketplace_products()
        by_name = {p[0]: p for p in products}
        rtx5070 = by_name["RTX 5070 16GB"]
        self.assertEqual(rtx5070[1], "RTX 5070", "mp.q overrides the product keyword")


if __name__ == "__main__":
    unittest.main(verbosity=2)
