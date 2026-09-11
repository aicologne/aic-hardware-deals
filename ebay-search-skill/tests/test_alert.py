"""Unit tests for alert.py — the shared Telegram/Discord alert sender.

Every send goes through an injected `post`, so these tests never touch the
network and never need real credentials.

Run from the skill directory:
    python -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alert  # noqa: E402

TELEGRAM_ENV = {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "42"}
DISCORD_ENV = {"DISCORD_WEBHOOK_URL": "https://discord.test/webhook"}


class FakePost:
    """Records (url, payload) instead of sending anything."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, payload, headers=None):
        self.calls.append((url, payload))
        return 200


class TestChannels(unittest.TestCase):
    def test_nothing_configured(self):
        self.assertEqual(alert.channels({}), [])

    def test_telegram_needs_both_token_and_chat_id(self):
        self.assertEqual(alert.channels({"TELEGRAM_BOT_TOKEN": "t"}), [])
        self.assertEqual(alert.channels(TELEGRAM_ENV), ["telegram"])

    def test_discord_webhook_must_be_a_url(self):
        self.assertEqual(alert.channels({"DISCORD_WEBHOOK_URL": "nope"}), [])
        self.assertEqual(alert.channels(DISCORD_ENV), ["discord"])

    def test_both(self):
        self.assertEqual(
            alert.channels({**TELEGRAM_ENV, **DISCORD_ENV}),
            ["telegram", "discord"],
        )


class TestSend(unittest.TestCase):
    def test_no_channel_is_not_an_error(self):
        post = FakePost()
        self.assertEqual(alert.send("hi", env={}, post=post), [])
        self.assertEqual(post.calls, [])

    def test_dry_run_sends_nothing(self):
        post = FakePost()
        self.assertEqual(
            alert.send("hi", env=TELEGRAM_ENV, dry_run=True, post=post), ["telegram"]
        )
        self.assertEqual(post.calls, [])

    def test_telegram_payload(self):
        post = FakePost()
        alert.send("nightly failed", env=TELEGRAM_ENV, post=post)
        url, payload = post.calls[0]
        self.assertIn("bot tok".replace(" ", ""), url)
        self.assertEqual(payload["chat_id"], "42")
        self.assertEqual(payload["text"], "nightly failed")
        self.assertTrue(payload["disable_web_page_preview"])

    def test_discord_payload(self):
        post = FakePost()
        alert.send("nightly failed", env=DISCORD_ENV, post=post)
        url, payload = post.calls[0]
        self.assertEqual(url, DISCORD_ENV["DISCORD_WEBHOOK_URL"])
        self.assertEqual(payload, {"content": "nightly failed"})

    def test_both_channels_get_the_message(self):
        post = FakePost()
        used = alert.send("boom", env={**TELEGRAM_ENV, **DISCORD_ENV}, post=post)
        self.assertEqual(used, ["telegram", "discord"])
        self.assertEqual(len(post.calls), 2)

    def test_telegram_truncates_but_keeps_the_head(self):
        post = FakePost()
        long_text = "x" * 5000
        alert.send(long_text, env=TELEGRAM_ENV, post=post)
        sent = post.calls[0][1]["text"]
        self.assertLessEqual(len(sent), 4000)
        self.assertTrue(sent.startswith("xxx"))
        self.assertTrue(sent.endswith("(truncated)"))

    def test_discord_truncates(self):
        post = FakePost()
        alert.send("y" * 5000, env=DISCORD_ENV, post=post)
        self.assertLessEqual(len(post.calls[0][1]["content"]), 1900)


class TestMain(unittest.TestCase):
    def test_dry_run_exits_zero_without_a_channel(self):
        self.assertEqual(alert.main(["--dry-run", "hello"]), 0)

    def test_message_is_required(self):
        with self.assertRaises(SystemExit):
            alert.main([])


if __name__ == "__main__":
    unittest.main(verbosity=2)
