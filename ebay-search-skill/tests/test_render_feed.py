"""Unit tests for render_feed.py — RSS feed helpers.

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_render_feed.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import render_feed  # noqa: E402


class TestNumEuro(unittest.TestCase):
    def test_num(self):
        self.assertEqual(render_feed.num("42"), 42.0)
        self.assertIsNone(render_feed.num("abc"))
        self.assertIsNone(render_feed.num(None))

    def test_euro_german_format(self):
        self.assertEqual(render_feed.euro(42), "€42,00")
        self.assertEqual(render_feed.euro(1750.5), "€1.750,50")
        self.assertEqual(render_feed.euro(None), "—")


class TestXmlesc(unittest.TestCase):
    def test_escapes(self):
        self.assertEqual(render_feed.xmlesc("<b>&\"'"), "&lt;b&gt;&amp;&quot;&#x27;")
        self.assertEqual(render_feed.xmlesc("plain text"), "plain text")

    def test_none_becomes_empty(self):
        self.assertEqual(render_feed.xmlesc(None), "")
        self.assertEqual(render_feed.xmlesc(""), "")


class TestRepricedNote(unittest.TestCase):
    def test_repriced(self):
        lh = {
            "https://x/1": {
                "first_price": "42.00", "last_price": "50.00", "first_seen": "2026-08-14",
            }
        }
        self.assertEqual(
            render_feed.repriced_note({"url": "https://x/1"}, lh),
            "was €42,00 on 2026-08-14",
        )

    def test_not_repriced_or_unknown(self):
        self.assertEqual(render_feed.repriced_note({"url": "https://y"}, {}), "")
        lh = {
            "https://x/1": {
                "first_price": "42.00", "last_price": "42.00", "first_seen": "2026-08-14",
            }
        }
        self.assertEqual(render_feed.repriced_note({"url": "https://x/1"}, lh), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
