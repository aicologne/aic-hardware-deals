"""Unit tests for ebay_relay.py — env candidate discovery and token caching.

The HTTP handler itself is thin; the pure logic worth pinning is the env-file
candidate list and the token cache (fetch-once-then-reuse, refresh on expiry).

Run from the skill directory:
    python -m unittest discover -s tests -v
or directly:
    python tests/test_ebay_relay.py
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ebay_relay  # noqa: E402


class TestFindEnvCandidates(unittest.TestCase):
    def test_candidate_paths(self):
        cands = ebay_relay.find_env_candidates()
        self.assertGreaterEqual(len(cands), 3, "cwd, script dir, and workspace roots")
        self.assertEqual(cands[0], "ebay.env")
        self.assertTrue(all(os.path.isabs(c) for c in cands[1:]), "rest are absolute")
        # the script's own directory must be among them
        script_dir = os.path.dirname(os.path.abspath(ebay_relay.__file__))
        self.assertIn(os.path.join(script_dir, "ebay.env"), cands)


class TestGetTokenCached(unittest.TestCase):
    def setUp(self):
        ebay_relay._token_cache["token"] = None
        ebay_relay._token_cache["expires_at"] = 0.0

    def test_fetches_then_reuses(self):
        with mock.patch.object(ebay_relay.e, "get_token", return_value="tok-1") as gt, \
             mock.patch.dict(os.environ, {"EBAY_CLIENT_ID": "c", "EBAY_CLIENT_SECRET": "s"}):
            self.assertEqual(ebay_relay.get_token_cached("production"), "tok-1")
            self.assertEqual(ebay_relay.get_token_cached("production"), "tok-1")
            gt.assert_called_once()

    def test_refetches_after_expiry(self):
        with mock.patch.object(ebay_relay.e, "get_token", return_value="tok-2") as gt, \
             mock.patch.dict(os.environ, {"EBAY_CLIENT_ID": "c", "EBAY_CLIENT_SECRET": "s"}):
            ebay_relay.get_token_cached("production")
            ebay_relay._token_cache["expires_at"] = 0.0  # simulate expiry
            self.assertEqual(ebay_relay.get_token_cached("production"), "tok-2")
            self.assertEqual(gt.call_count, 2)

    def test_sandbox_realm_uses_sandbox_url(self):
        with mock.patch.object(ebay_relay.e, "get_token", return_value="tok") as gt, \
             mock.patch.dict(os.environ, {"EBAY_CLIENT_ID": "c", "EBAY_CLIENT_SECRET": "s"}):
            ebay_relay.get_token_cached("sandbox")
            self.assertEqual(gt.call_args[0][2], ebay_relay.e.SANDBOX_TOKEN_URL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
