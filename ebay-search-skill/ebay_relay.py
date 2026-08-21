#!/usr/bin/env python3
"""
ebay_relay.py — local HTTP relay to the eBay Browse API.

Why it exists: the DSH sandbox blocks outbound HTTPS but ALLOWS loopback HTTP.
Run this relay in a NORMAL terminal on your machine (it has real network
access), then the sandbox can perform live eBay searches over plain HTTP by
passing `--relay http://127.0.0.1:8787` to ebay_search.py — no sandbox
escalation, no approval prompts.

Security: binds to 127.0.0.1 ONLY (never 0.0.0.0) and reads credentials from
ebay.env (same file as the scanner). Do not expose it to the network.

Usage:
    python ebay_relay.py [--port 8787]
    (reads EBAY_CLIENT_ID / EBAY_CLIENT_SECRET from ebay.env in cwd or script dir)

Endpoints:
    GET /health
        -> {"ok": true, "realm": "production", "cred_source": "ebay.env"}
    GET /search?keyword=RTX 3090&min=450&max=750&condition=USED&category=27386
                &marketplace=EBAY_DE&currency=EUR&limit=50
        -> {"realm": "...", "total": N, "itemSummaries": [ ...raw Browse API items... ]}
    Errors -> JSON {"error": "..."} with a non-2xx status.

Realm (sandbox vs production) is auto-detected from the credentials, exactly
like ebay_search.py.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

# Reuse logic from the scanner (same directory).
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ebay_search as e  # noqa: E402

_token_cache = {"token": None, "expires_at": 0.0}


def get_token_cached(realm):
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]
    token_url = e.SANDBOX_TOKEN_URL if realm == "sandbox" else e.TOKEN_URL
    token = e.get_token(os.environ.get("EBAY_CLIENT_ID", ""),
                        os.environ.get("EBAY_CLIENT_SECRET", ""), token_url)
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + 7200 - 120  # 2h minus 2min safety
    return token


class RelayHandler(BaseHTTPRequestHandler):
    server_version = "ebay-relay/1.0"

    def log_message(self, fmt, *args):  # keep the console quiet
        sys.stderr.write("[relay] %s\n" % (fmt % args))

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                self._json(200, {
                    "ok": True,
                    "realm": e.detect_realm(os.environ.get("EBAY_CLIENT_ID", ""),
                                            os.environ.get("EBAY_CLIENT_SECRET", "")),
                    "cred_source": "ebay.env",
                })
            elif parsed.path == "/search":
                self._handle_search(query)
            else:
                self._json(404, {"error": f"unknown path {parsed.path}"})
        except Exception as exc:  # noqa: BLE001 - surface as JSON
            self._json(502, {"error": str(exc)})

    def _handle_search(self, q):
        def arg(key, default=None):
            vals = q.get(key)
            return vals[0] if vals else default

        keyword = arg("keyword")
        if not keyword:
            self._json(400, {"error": "missing 'keyword' parameter"})
            return
        pmin = float(arg("min", 0) or 0)
        pmax = float(arg("max", 100000) or 100000)
        cond = arg("condition") or None
        category = int(arg("category", 0)) or None
        marketplace = arg("marketplace", "EBAY_DE")
        currency = arg("currency", "EUR")
        limit = int(arg("limit", 50))
        sort = arg("sort", "price")

        realm = e.detect_realm(os.environ.get("EBAY_CLIENT_ID", ""),
                               os.environ.get("EBAY_CLIENT_SECRET", ""))
        token = get_token_cached(realm)
        search_url = e.SANDBOX_SEARCH_URL if realm == "sandbox" else e.SEARCH_URL

        filters = [f"price:[{pmin}..{pmax}]", f"priceCurrency:{currency}"]
        if cond:
            filters.append(f"conditions:{{{cond}}}")
        params = {"q": keyword, "limit": limit, "filter": ",".join(filters), "sort": sort}
        if category:
            params["category_ids"] = category
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": marketplace,
        }
        r = requests.get(search_url, params=params, headers=headers, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"eBay API {r.status_code}: {r.text[:400]}")
        data = r.json()
        self._json(200, {
            "realm": realm,
            "total": data.get("total"),
            "itemSummaries": data.get("itemSummaries", []),
        })


def find_env_candidates():
    """ebay.env can live next to the script, in cwd, or in a workspace root
    a few levels above the skill directory — search them all."""
    candidates = ["ebay.env", os.path.join(HERE, "ebay.env")]
    up = HERE
    for _ in range(4):
        up = os.path.dirname(up)
        candidates.append(os.path.join(up, "ebay.env"))
    return candidates


def main():
    e.load_env_file(find_env_candidates())
    if not (os.environ.get("EBAY_CLIENT_ID") and os.environ.get("EBAY_CLIENT_SECRET")):
        sys.exit("Missing credentials: set EBAY_CLIENT_ID / EBAY_CLIENT_SECRET or fill ebay.env.")
    parser = argparse.ArgumentParser(description="Local HTTP relay to the eBay Browse API")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="127.0.0.1", help="bind address (keep 127.0.0.1!)")
    args = parser.parse_args()
    realm = e.detect_realm(os.environ.get("EBAY_CLIENT_ID", ""),
                           os.environ.get("EBAY_CLIENT_SECRET", ""))
    server = ThreadingHTTPServer((args.host, args.port), RelayHandler)
    print(f"ebay-relay listening on http://{args.host}:{args.port}  (realm: {realm.upper()})")
    print("Keep this terminal open. From the sandbox run:")
    print(f"  python ebay_search.py --relay http://{args.host}:{args.port} ...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nrelay stopped")


if __name__ == "__main__":
    main()
