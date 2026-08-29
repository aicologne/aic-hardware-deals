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
        # not drift from the single source of truth.
        import re
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(repo, "site", "csv.js")
        with open(path, encoding="utf-8") as f:
            js = f.read()
        pairs = re.findall(r"'([^']+)':\s*(\d+)", js.split("export const CAPACITY_GB")[1].split("};")[0])
        js_map = {k: int(v) for k, v in pairs}
        for name, gb in js_map.items():
            self.assertEqual(queries.capacity_map().get(name), gb,
                             f"csv.js fallback {name}={gb} disagrees with queries.py")


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
