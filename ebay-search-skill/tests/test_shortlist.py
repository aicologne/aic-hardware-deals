"""Unit tests for shortlist.py — the expected-margin ranking.

The ranking is the report's headline number, so its arithmetic (fee, churn
weight, per-category cap, thin-category cutoff, ranked-vs-unproven split) is
pinned here; the site mirrors the same maths in site/csv.js and
tests/stats.test.mjs pins that copy.

Run from the skill directory:
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import shortlist  # noqa: E402

DATES = [f"2026-09-{d:02d}" for d in range(1, 12)]  # 11 consecutive scan dates
NEWEST = DATES[-1]


def deal(query, price, title="listing", url=None, mp="EBAY_DE"):
    return {
        "query": query, "price": str(price), "title": title,
        "url": url or f"https://example.test/{query}/{price}",
        "marketplace": mp, "seller": "seller", "condition": "Gebraucht",
    }


def tracked(query, first, last, url):
    return {"url": url, "query": query, "marketplace": "EBAY_DE",
            "first_seen": first, "last_seen": last,
            "first_price": "100.00", "last_price": "100.00"}


def hist(query, aged, gone, prefix="h"):
    """`aged` listings first seen on day 1; the first `gone` of them left."""
    out = []
    for i in range(aged):
        out.append(tracked(query, DATES[0], DATES[1] if i < gone else NEWEST,
                           f"{prefix}{i}"))
    return out


def priced(query, *prices):
    return [deal(query, p) for p in prices]


class TestHelpers(unittest.TestCase):
    def test_num(self):
        self.assertEqual(shortlist.num("42.5"), 42.5)
        self.assertIsNone(shortlist.num("n/a"))
        self.assertIsNone(shortlist.num(None))

    def test_key_defaults_to_the_default_marketplace(self):
        self.assertEqual(shortlist.key_for({"query": "RTX 3090"}),
                         "EBAY_DE · RTX 3090")
        self.assertEqual(shortlist.key_for({"query": "RTX 3090", "marketplace": "EBAY_AT"}),
                         "EBAY_AT · RTX 3090")

    def test_load_listing_rows_missing_file(self):
        self.assertEqual(shortlist.load_listing_rows("does-not-exist.csv"), [])

    def test_load_listing_rows_reads_and_skips_empty_urls(self):
        with temp_dir() as d:
            path = os.path.join(d, "listing_history.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write("url,query,marketplace,first_seen,first_price,last_seen,last_price\n"
                        "u1,RAM,EBAY_DE,2026-09-01,80.00,2026-09-02,80.00\n"
                        ",RAM,EBAY_DE,2026-09-01,80.00,2026-09-02,80.00\n")
            rows = shortlist.load_listing_rows(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["url"], "u1")

    def test_scan_dates_are_sorted_and_unique(self):
        rows = [tracked("RAM", "2026-09-05", "2026-09-07", "a"),
                tracked("RAM", "2026-09-01", "2026-09-07", "b")]
        self.assertEqual(shortlist.scan_dates_from(rows),
                         ["2026-09-01", "2026-09-05", "2026-09-07"])


class TestMarketChurn(unittest.TestCase):
    def test_counts_aged_listings_and_those_that_left(self):
        rows = [
            tracked("RAM", "2026-09-01", NEWEST, "a"),        # aged 10, still listed
            tracked("RAM", "2026-09-01", "2026-09-04", "b"),  # aged 10, gone
            tracked("RAM", "2026-09-09", NEWEST, "c"),        # aged 2 -> ignored
        ]
        out = shortlist.market_churn(rows, DATES)
        self.assertEqual(out["overall"]["aged"], 2)
        self.assertEqual(out["overall"]["gone"], 1)
        self.assertEqual(out["overall"]["rate"], 0.5)
        self.assertEqual(out["by_key"]["EBAY_DE · RAM"]["aged"], 2)

    def test_unknown_scan_dates_are_ignored(self):
        outs = shortlist.market_churn([tracked("RAM", "2020-01-01", NEWEST, "a")], DATES)
        self.assertEqual(outs["overall"]["aged"], 0)
        self.assertIsNone(outs["overall"]["rate"])

    def test_no_history_at_all_has_no_rate(self):
        self.assertIsNone(shortlist.market_churn([], DATES)["overall"]["rate"])

    def test_high_churn_means_listings_leave(self):
        out = shortlist.market_churn(hist("RAM", 10, 9), DATES)
        self.assertAlmostEqual(out["overall"]["rate"], 0.9)
        self.assertAlmostEqual(out["by_key"]["EBAY_DE · RAM"]["rate"], 0.9)


class TestEstimateResale(unittest.TestCase):
    def test_sold_anchor_wins(self):
        anchors = {"RTX 3090": {"median_sold": 1500.0, "sample_size": 12}}
        self.assertEqual(shortlist.estimate_resale("RTX 3090", anchors, 1200.0),
                         (1500.0, "sold median", 12))

    def test_thin_or_missing_anchor_falls_back_to_the_asking_median(self):
        anchors = {"RTX 3090": {"median_sold": 1500.0, "sample_size": 0}}
        self.assertEqual(shortlist.estimate_resale("RTX 3090", anchors, 1200.0),
                         (1200.0, "asking median", 0))
        self.assertEqual(shortlist.estimate_resale("RTX 3090", {}, 1200.0),
                         (1200.0, "asking median", 0))

    def test_no_price_at_all(self):
        self.assertEqual(shortlist.estimate_resale("X", {}, None), (None, None, 0))


class TestBuildShortlist(unittest.TestCase):
    def test_thin_categories_are_skipped(self):
        rows = priced("Thin", 10, 10, 10, 10) + priced("Fat", 10, 100, 100, 100, 100)
        out = shortlist.build_shortlist(rows, listing_rows=hist("Fat", 10, 5),
                                        scan_dates=DATES, limit=10)
        self.assertEqual([i["query"] for i in out["items"]], ["Fat"])
        self.assertEqual(out["skipped"]["thin_categories"], ["EBAY_DE · Thin"])

    def test_negative_margins_are_never_listed(self):
        # est = asking median = 100, fee 13 % -> net = 87 - buy; buy 90 -> negative
        rows = priced("Fat", 100, 100, 100, 100, 90)
        out = shortlist.build_shortlist(rows, listing_rows=hist("Fat", 10, 5),
                                        scan_dates=DATES, limit=10)
        self.assertEqual([i["price"] for i in out["items"]], [])
        self.assertEqual(out["skipped"]["negative_margin"], 5)

    def test_net_applies_the_fee_to_the_estimate(self):
        rows = priced("Fat", 100, 200, 300, 400, 50)
        out = shortlist.build_shortlist(rows, listing_rows=hist("Fat", 10, 5),
                                        scan_dates=DATES, fee_rate=0.13, limit=1)
        item = out["items"][0]
        self.assertEqual(item["est_resale"], 200.0)         # median of 50..400
        self.assertEqual(item["price"], 50.0)
        self.assertAlmostEqual(item["net"], 200.0 * 0.87 - 50.0)

    def test_ranking_is_risk_adjusted_not_just_margin(self):
        # Wide margin on a dead category vs a smaller margin on one that turns
        # over: the churn weight must be able to flip the order.
        rows = priced("Dead", 10, 100, 100, 100, 100) + \
               priced("Alive", 80, 100, 100, 100, 100)
        history = hist("Dead", 10, 0, "d") + hist("Alive", 10, 9, "a")
        out = shortlist.build_shortlist(rows, listing_rows=history, scan_dates=DATES,
                                        limit=2)
        by_query = {i["query"]: i for i in out["items"]}
        # churn = share of aged listings that left the market
        self.assertAlmostEqual(by_query["Dead"]["churn"], 0.0)
        self.assertAlmostEqual(by_query["Alive"]["churn"], 0.9)
        # Dead has the bigger raw margin (87 - 10 = 77) but nothing ever leaves,
        # Alive's is smaller (87 - 80 = 7) yet its stock actually moves.
        self.assertGreater(by_query["Dead"]["net"], by_query["Alive"]["net"])
        self.assertEqual([i["query"] for i in out["items"]], ["Alive", "Dead"])
        self.assertEqual(out["items"][0]["rank"], 1)

    def test_categories_without_their_own_churn_are_unproven_not_ranked(self):
        # The Mac Studio case: a real margin, but the category has too few
        # tracked listings to measure liquidity. It must not headline the list.
        rows = priced("Fat", 10, 100, 100, 100, 100)
        history = hist("Fat", 10, 0) + hist("Other", 1, 1, "o")
        out = shortlist.build_shortlist(rows, listing_rows=history, scan_dates=DATES,
                                        min_aged=11, limit=5)
        self.assertEqual(out["items"], [])                       # not ranked
        self.assertEqual([u["query"] for u in out["unproven"]], ["Fat"])
        self.assertEqual(out["unproven"][0]["churn_source"], "global")

        # with enough of its own history it is ranked, using its own rate
        out2 = shortlist.build_shortlist(rows, listing_rows=history, scan_dates=DATES,
                                         min_aged=5, limit=5)
        self.assertEqual([i["query"] for i in out2["items"]], ["Fat"])
        self.assertEqual(out2["items"][0]["churn_source"], "category")
        self.assertAlmostEqual(out2["items"][0]["churn"], 0.0)

    def test_unproven_list_is_capped_and_no_history_is_safe(self):
        rows = priced("A", 10, 100, 100, 100, 100)
        for name in ("B", "C", "D"):
            rows += priced(name, 10, 100, 100, 100, 100)
        out = shortlist.build_shortlist(rows, listing_rows=[], scan_dates=DATES, limit=5)
        self.assertEqual(out["items"], [], "no tracked history -> nothing is ranked")
        self.assertEqual(len(out["unproven"]), shortlist.UNPROVEN_LIMIT)
        for u in out["unproven"]:
            self.assertNotIn("rank", u)

    def test_at_most_two_items_per_category(self):
        rows = priced("Fat", 10, 20, 30, 100, 100, 100)
        out = shortlist.build_shortlist(rows, listing_rows=hist("Fat", 10, 5),
                                        scan_dates=DATES, limit=10)
        self.assertEqual(len(out["items"]), 2)
        self.assertEqual([i["price"] for i in out["items"]], [10.0, 20.0])

    def test_limit_is_respected_and_items_are_ranked(self):
        rows = []
        history = []
        for name in ("A", "B", "C"):
            rows += priced(name, 10, 100, 100, 100, 100)
            history += hist(name, 10, 5, name)
        out = shortlist.build_shortlist(rows, listing_rows=history, scan_dates=DATES,
                                        limit=2)
        self.assertEqual(len(out["items"]), 2)
        self.assertEqual([i["rank"] for i in out["items"]], [1, 2])

    def test_estimates_are_labelled_by_source(self):
        rows = priced("Fat", 10, 100, 100, 100, 100)
        history = hist("Fat", 10, 5)
        anchors = {"Fat": {"median_sold": 150.0, "sample_size": 7}}
        out = shortlist.build_shortlist(rows, sold_anchors=anchors,
                                        listing_rows=history, scan_dates=DATES, limit=1)
        self.assertEqual(out["items"][0]["est_source"], "sold median")
        self.assertEqual(out["estimated_from"]["sold median"], 1)
        out2 = shortlist.build_shortlist(rows, sold_anchors={}, listing_rows=history,
                                         scan_dates=DATES, limit=1)
        self.assertEqual(out2["items"][0]["est_source"], "asking median")
        self.assertEqual(out2["estimated_from"]["asking median"], 1)

    def test_thin_category_never_reaches_the_ranking(self):
        # 4 listings: below min_listings even with perfect churn history
        rows = priced("Thin", 10, 10, 10, 10)
        out = shortlist.build_shortlist(rows, listing_rows=hist("Thin", 20, 20),
                                        scan_dates=DATES, limit=5)
        self.assertEqual(out["items"], [])
        self.assertEqual(out["unproven"], [])

    def test_empty_input_is_safe(self):
        out = shortlist.build_shortlist([], limit=10)
        self.assertEqual(out["items"], [])
        self.assertEqual(out["unproven"], [])
        self.assertEqual(out["skipped"]["negative_margin"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
