"""Unit tests for sold_anchors.py — sold-price anchor parsing.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_sold_anchors.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sold_anchors  # noqa: E402


class TestNum(unittest.TestCase):
    def test_parses(self):
        self.assertEqual(sold_anchors.num("42"), 42.0)
        self.assertIsNone(sold_anchors.num("abc"))
        self.assertIsNone(sold_anchors.num(None))


class TestNormalizePriceText(unittest.TestCase):
    def test_entities_and_whitespace(self):
        self.assertEqual(
            sold_anchors.normalize_price_text("&nbsp;14,27&nbsp;EUR&nbsp;"), "14,27 EUR"
        )
        self.assertEqual(
            sold_anchors.normalize_price_text("&euro;45&nbsp;&amp;&nbsp;up"),
            "€45 & up",
        )

    def test_collapses_whitespace(self):
        self.assertEqual(
            sold_anchors.normalize_price_text("  1.234,56   EUR  "), "1.234,56 EUR"
        )


class TestParsePrice(unittest.TestCase):
    def test_eur_german_format(self):
        self.assertEqual(sold_anchors.parse_price("14,27 EUR", "EUR"), 14.27)
        self.assertEqual(sold_anchors.parse_price("EUR 89,00", "EUR"), 89.0)
        self.assertEqual(sold_anchors.parse_price("1.234,56 EUR", "EUR"), 1234.56)
        self.assertEqual(sold_anchors.parse_price("€ 45", "EUR"), 45.0)
        self.assertEqual(sold_anchors.parse_price("1.234", "EUR"), 1234.0)
        self.assertEqual(sold_anchors.parse_price("42", "EUR"), 42.0)

    def test_usd_and_gbp(self):
        self.assertEqual(sold_anchors.parse_price("$1,699", "USD"), 1699.0)
        self.assertEqual(sold_anchors.parse_price("1,699.00 USD", "USD"), 1699.0)
        self.assertEqual(sold_anchors.parse_price("£1,200", "GBP"), 1200.0)
        self.assertEqual(sold_anchors.parse_price("1,200.50 GBP", "GBP"), 1200.5)
        # USD/GBP treat '.' as decimal: "1.200" is one point two zero zero
        self.assertEqual(sold_anchors.parse_price("£1.200", "GBP"), 1.2)

    def test_foreign_currency_rejected(self):
        # '$' and '£' cells must not pollute a non-US/UK marketplace median
        self.assertIsNone(sold_anchors.parse_price("$1,699", "EUR"))
        self.assertIsNone(sold_anchors.parse_price("£1.200", "EUR"))
        self.assertIsNone(sold_anchors.parse_price("$ 45", "GBP"))
        # note: '€' is NOT treated as a foreign marker — a € cell on a USD
        # marketplace is parsed as a plain number (current behaviour)
        self.assertEqual(sold_anchors.parse_price("€ 45", "USD"), 45.0)

    def test_garbage(self):
        self.assertIsNone(sold_anchors.parse_price("", "EUR"))
        self.assertIsNone(sold_anchors.parse_price("Preis auf Anfrage", "EUR"))
        self.assertIsNone(sold_anchors.parse_price("n/a", "EUR"))
        self.assertIsNone(sold_anchors.parse_price("---", "EUR"))

    def test_keeps_marketplace_currency(self):
        # EUR medians stay EUR even when the text has no marker
        self.assertEqual(sold_anchors.parse_price("1234", "EUR"), 1234.0)
        # 'EUR' marker stripped, then German thousands-dot removed
        self.assertEqual(sold_anchors.parse_price("EUR 1.234,56", "EUR"), 1234.56)


if __name__ == "__main__":
    unittest.main(verbosity=2)
