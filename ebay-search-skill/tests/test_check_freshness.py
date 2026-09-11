"""Unit tests for check_freshness.py — the "is the data stale?" guard.

The guard exists because a broken unit test froze the dataset for ten
consecutive nights (2026-08-30 -> 2026-09-08) without anyone noticing, so the
threshold arithmetic and the exit codes are worth pinning down.

Run from the skill directory:
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _helpers import temp_dir  # noqa: E402
import check_freshness  # noqa: E402

NOW = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)


def write_history(path, dates, header="date,marketplace,query,median\n"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        for d in dates:
            f.write(f"{d},EBAY_DE,RTX 3090,1200.00\n")


class TestParseNow(unittest.TestCase):
    def test_zulu_and_offset_agree(self):
        self.assertEqual(
            check_freshness.parse_now("2026-09-12T09:00:00Z"),
            check_freshness.parse_now("2026-09-12T11:00:00+02:00"),
        )

    def test_naive_is_utc(self):
        self.assertEqual(
            check_freshness.parse_now("2026-09-12T09:00:00").tzinfo,
            timezone.utc,
        )

    def test_date_only_is_midnight_utc(self):
        self.assertEqual(
            check_freshness.parse_now("2026-09-12"),
            datetime(2026, 9, 12, tzinfo=timezone.utc),
        )

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            check_freshness.parse_now("yesterday-ish")


class TestNewestScanDate(unittest.TestCase):
    def test_picks_the_maximum_not_the_last_row(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["2026-09-10", "2026-09-08", "2026-09-11"])
            self.assertEqual(
                check_freshness.newest_scan_date(path), date(2026, 9, 11)
            )

    def test_skips_blank_and_garbage_dates(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["", "n/a", "2026-09-11"])
            self.assertEqual(
                check_freshness.newest_scan_date(path), date(2026, 9, 11)
            )

    def test_missing_file_is_none(self):
        self.assertIsNone(check_freshness.newest_scan_date("does-not-exist.csv"))
        self.assertIsNone(check_freshness.newest_scan_date(None))


class TestAgeArithmetic(unittest.TestCase):
    def test_scan_date_is_anchored_to_the_cron_hour(self):
        # 2026-09-11 05:00 UTC -> 2026-09-12 09:00 UTC == 28 h, not 33 h
        self.assertEqual(
            check_freshness.age_hours(date(2026, 9, 11), NOW), 28.0
        )

    def test_two_days_of_silence_is_52_hours(self):
        self.assertEqual(
            check_freshness.age_hours(date(2026, 9, 10), NOW), 52.0
        )

    def test_no_date_has_no_age(self):
        self.assertIsNone(check_freshness.age_hours(None, NOW))


class TestEvaluate(unittest.TestCase):
    def test_yesterdays_scan_is_fresh(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["2026-09-10", "2026-09-11"])
            out = check_freshness.evaluate(path, 36.0, NOW)
        self.assertEqual(out["status"], "fresh")
        self.assertEqual(out["newest"], "2026-09-11")
        self.assertAlmostEqual(out["age_hours"], 28.0)

    def test_one_missed_night_is_stale(self):
        # The exact 2026-08-30..09-08 failure mode: the previous night's run
        # died, so the newest row is two days old when the guard runs.
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["2026-09-10"])
            out = check_freshness.evaluate(path, 36.0, NOW)
        self.assertEqual(out["status"], "stale")
        self.assertAlmostEqual(out["age_hours"], 52.0)

    def test_boundary_is_exclusive(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["2026-09-11"])
            # exactly at the limit -> still fresh; a minute more -> stale
            self.assertEqual(
                check_freshness.evaluate(path, 28.0, NOW)["status"], "fresh"
            )
            self.assertEqual(
                check_freshness.evaluate(path, 27.9, NOW)["status"], "stale"
            )

    def test_missing_file_is_an_error(self):
        out = check_freshness.evaluate("does-not-exist.csv", 36.0, NOW)
        self.assertEqual(out["status"], "error")
        self.assertIsNone(out["age_hours"])


class TestMessage(unittest.TestCase):
    def test_stale_message_names_the_date_and_the_runs_page(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["2026-09-01"])
            out = check_freshness.evaluate(path, 36.0, NOW)
        msg = check_freshness.build_message(out, "site/data/history.csv", env={})
        self.assertIn("STALE", msg.upper())
        self.assertIn("2026-09-01", msg)
        self.assertIn("site/data/history.csv", msg)
        self.assertIn(check_freshness.FALLBACK_RUNS_URL, msg)

    def test_error_message_says_no_usable_data(self):
        out = check_freshness.evaluate("does-not-exist.csv", 36.0, NOW)
        msg = check_freshness.build_message(out, "site/data/history.csv", env={})
        self.assertIn("no usable scan dates", msg)
        self.assertIn(check_freshness.FALLBACK_RUNS_URL, msg)

    def test_ci_env_links_to_the_repo(self):
        msg = check_freshness.build_message(
            {"status": "stale", "detail": "x"},
            env={"GITHUB_SERVER_URL": "https://github.com",
                 "GITHUB_REPOSITORY": "aicologne/aic-hardware-deals"},
        )
        self.assertIn(
            "https://github.com/aicologne/aic-hardware-deals/actions", msg
        )


class TestMainExitCodes(unittest.TestCase):
    def test_fresh_exits_zero(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["2026-09-11"])
            self.assertEqual(
                check_freshness.main(
                    ["--history", path, "--now", "2026-09-12T09:00:00Z",
                     "--dry-run"]
                ),
                0,
            )

    def test_stale_exits_one_and_can_notify_without_a_channel(self):
        with temp_dir() as d:
            path = os.path.join(d, "history.csv")
            write_history(path, ["2026-09-01"])
            # --dry-run exercises the alert path; no channel configured must
            # still exit 1 (the guard reports, the missing channel is noise)
            self.assertEqual(
                check_freshness.main(
                    ["--history", path, "--now", "2026-09-12T09:00:00Z",
                     "--dry-run"]
                ),
                1,
            )

    def test_no_data_exits_two(self):
        self.assertEqual(
            check_freshness.main(
                ["--history", "does-not-exist.csv", "--now",
                 "2026-09-12T09:00:00Z", "--dry-run"]
            ),
            2,
        )

    def test_bad_now_exits_two(self):
        self.assertEqual(check_freshness.main(["--now", "not-a-time"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
