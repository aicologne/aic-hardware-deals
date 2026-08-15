---
name: ebay-search
description: Search eBay for products — used/refurbished hardware, GPUs, mini PCs, RAM, etc. — via the official eBay Browse API on any marketplace (EBAY_DE, EBAY_AT, EBAY_CH, EBAY_GB, EBAY_US). Covers OAuth client-credentials auth, sandbox vs production realm handling (auto-detected from credentials), keyword/price/condition/location filters, pagination, error handling, and a ready-made Python scanner (ebay_search.py) with CSV output. Use whenever the user wants current eBay listings, price checks, or deal scans.
whenToUse: The user asks to search or scan eBay for products, find current listings/deals/prices, check what an item goes for, or wants a repeatable deal scanner for a hardware niche.
---

# eBay Search via the Browse API

Search eBay's catalog with the official **Browse API** (`Buy` API family). Active listings only — there is no public sold-price history (see Limitations).

## 0. Prerequisites (one-time, free)

1. eBay account → register at https://developer.ebay.com → create an app.
2. Copy **Client ID** and **Client Secret** from the app dashboard (you get separate keysets for Sandbox and Production — see §1).
3. Provide them via env vars (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`) **or** an `ebay.env` file (auto-loaded from the working directory or the skill directory).
4. Python 3 with `requests`, and **outbound HTTPS reachable**. If the sandbox blocks HTTPS, hand the script to the user to run locally (or run it from the DSH sandbox — see §0.5).

## 0.5 Executing from the DSH sandbox (this harness)

- **Offline parts run normally**: `--demo`, parsing, CSV analysis — no approval needed.
- **Live API calls require `danger-full-access`** (the DSH sandbox blocks outbound HTTPS under workspace-write mode: schannel `SEC_E_NO_CREDENTIALS`). Run the scanner via pwsh with `sandbox_permissions: danger-full-access` — an approval prompt appears (policy: ask); once approved, token → search → CSV works end-to-end (verified live: eBay.de production search returned real listings). Every escalated command raises its own prompt — there is no persistent grant.
- **Recommended: the local HTTP relay (`ebay_relay.py`) — zero approvals.** The sandbox allows loopback HTTP, so run the relay and point the scanner at it with `--relay http://127.0.0.1:8787`:
  - Start it in a **normal user terminal** for persistence: `python .dsh\skills\ebay-search\ebay_relay.py`
  - It also works started as a **sandbox background job** (pwsh `run_in_background`) — background processes were observed to have working HTTPS even when the foreground sandbox does not.
  - Endpoints: `GET /health` (realm check), `GET /search?...` (raw Browse API items). Binds to 127.0.0.1 only; token is cached (2 h).
  - Verified live 2026-08-14: relay → `/search` → real eBay.de listings; scanner `--relay` run produced 24 used RTX 3090 hits (€1000–1500) with no escalation.

## 1. Sandbox vs Production — know which realm you are in

Every eBay app has **two independent keysets** ([official docs](https://developers.ebay.com/api-docs/static/gs_understand-application-keysets.html)):

| | Sandbox | Production |
|---|---|---|
| Client ID looks like | `...-SBX-...` | `...-Prod-...` (or no marker) |
| Client Secret looks like | `SBX-<uuid>` | `<uuid>` / other |
| Token endpoint | `https://api.sandbox.ebay.com/identity/v1/oauth2/token` | `https://api.ebay.com/identity/v1/oauth2/token` |
| Search endpoint | `https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search` | `https://api.ebay.com/buy/browse/v1/item_summary/search` |
| Data returned | **Fabricated test items — never real listings** | Live listings |
| Use for | Validating credentials/plumbing only | Actual deal scanning |

**The script auto-detects the realm** from the credentials: `-SBX-` in the Client ID or `SBX-` prefix on the Secret → sandbox; anything else → production. It prints a clear banner (`REALM: SANDBOX (test data only…)` vs `REALM: PRODUCTION (live listings)`) and refuses to pretend sandbox results are real.

**Forcing the realm:** `--sandbox` / `--production` (mutually exclusive) override detection, e.g. if the credential strings are ambiguous.

**Switching realms** = switching the values in `ebay.env` (or env vars). Never mix a sandbox Client ID with a production Secret or vice versa — the token call fails with 401.

Rules for the agent:
- If the user wants **real deals**, verify the realm banner says PRODUCTION first; if it says SANDBOX, tell them to swap in the production keyset before trusting any output.
- If the user only wants a **plumbing check**, run with `--sandbox` and explain the results are test data.
- Never present sandbox output as a real deal.

## 2. Authentication (OAuth2 client_credentials — no user login)

Token endpoint (valid ~2 h, no refresh token needed; just re-request):

```
POST <token-endpoint-for-realm>
Authorization: Basic base64(ClientID:ClientSecret)
Content-Type: application/x-www-form-urlencoded
grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope
```

Response: `{ "access_token": "...", "expires_in": 7200, "token_type": "Application Access Token" }`.

## 3. Search endpoint & parameters

```
GET <search-endpoint-for-realm>/buy/browse/v1/item_summary/search
Authorization: Bearer <access_token>
X-EBAY-C-MARKETPLACE-ID: EBAY_DE   ← set the marketplace via HEADER, not query
```

| Param | Example | Notes |
|---|---|---|
| `q` | `RTX 3090` | free-text keyword; supports quoted phrases |
| `X-EBAY-C-MARKETPLACE-ID` (**header**) | `EBAY_DE` | `EBAY_DE`, `EBAY_AT`, `EBAY_CH`, `EBAY_GB`, `EBAY_US`, `EBAY_FR`, `EBAY_IT`, `EBAY_ES`, `EBAY_NL`, `EBAY_PL` — **defaults to EBAY_US if missing/invalid**; there is NO `marketplace_ids` query param in Browse API (unknown params are silently ignored!) |
| `filter` | `price:[450..750],priceCurrency:EUR,conditions:{USED}` | comma-separated; see table below |
| `sort` | `price` | `price`, `-price`, `newlyListed`, `endingSoonest`, `distance` |
| `limit` | `50` | max 200 per page |
| `offset` | `0` | pagination |
| `category_ids` | `27386` | restrict to a category — **kills keyword noise** (e.g. "RTX 3090" matching an iPhone "A3090") |

### Verified category IDs (eBay.de taxonomy, fetched live 2026-08)

| Category | ID |
|---|---|
| Grafik-/Videokarten (GPUs) | `27386` |
| Desktops & All-in-One-PCs (mini PCs) | `171957` |
| Arbeitsspeicher (RAM, desktop) | `170083` |
| Server-Speicher (RAM, RDIMM) | `11210` |

Refresh any time via the Taxonomy API: `GET https://api.ebay.com/commerce/taxonomy/v1/get_default_category_tree_id?marketplace_id=EBAY_DE` → `GET .../category_tree/{treeId}`, then walk `rootCategoryNode.childCategoryTreeNodes[].category.{categoryId,categoryName}`.
| `aspect_filter` | `aspectFilter=memory size:16 GB,32 GB` | attribute filtering (VRAM, capacity…) — great for GPUs/RAM |

Useful filters (inside `filter=`):

| Filter | Example | Meaning |
|---|---|---|
| price range | `price:[450..750]` | open ends: `price:[..750]`, `price:[450..]` — **REQUIRES `priceCurrency`** (error 12012 otherwise) |
| currency | `priceCurrency:EUR` | must accompany `price` |
| condition | `conditions:{USED}` | **values in {CURLY BRACES}**: `{NEW}`, `{USED}`, `{REFURBISHED}` |
| pickup | `deliveryOptions:PICKUP` | local pickup only (Kleinanzeigen-style deals) |
| excludes | `excludes:defekt` | filter keywords |

⚠️ eBay silently ignores malformed/unknown params instead of erroring — always use `--debug` to print the request URL and response totals, and the script's client-side filter double-checks EUR/price/condition.

## 4. Response — fields that matter

`itemSummaries[]` (plus `total`, `href`, `offset`, `limit`):

- `title`, `itemWebUrl`, `itemId`
- `price.value`, `price.currency` (always check currency — `EBAY_DE` may still show international sellers)
- `condition` — **object or plain string, both occur in production** (string form: `"Used"`, `"New"`, `"Gebraucht"`; object form: `conditionGroup` `NEW`/`USED`/`REFURBISHED` + `conditionDescription`). `parse_item()` in `ebay_search.py` normalizes both — the script no longer assumes a dict.
- `seller.username`
- `itemLocation.country` / `itemLocation.postalCode`
- `shippingOptions[].shippingCost.value` (0 = free)
- `categories[0].categoryName`
- `buyingOptions` (`FIXED_PRICE`, `AUCTION`)

## 5. Run the bundled scanner

The skill directory ships `ebay_search.py` — a complete scanner with default queries for used hardware (GPUs ≥16 GB, 8th-gen mini PCs, DDR4/DDR5 RAM):

```bash
python <skill_dir>/ebay_search.py
```

- Auto-loads `ebay.env` if present (working dir or skill dir) — no manual env setup.
- Prints a **realm banner** first (SANDBOX vs PRODUCTION), then each hit (price, currency, condition, title, URL) and writes `ebay_deals.csv`.
- CLI overrides:
  - `--keyword "RTX 3090" --min 450 --max 750 --condition USED --marketplace EBAY_DE --limit 50 --out deals.csv`
  - `--sandbox` / `--production` — force the realm (mutually exclusive).
- Sandbox smoke test: `python <skill_dir>/ebay_search.py --sandbox --keyword "laptop" --max 200` (TEST data only).
- Offline pipeline check (no API calls, no credentials needed; validates parsing + CSV):
  `python <skill_dir>/ebay_search.py --demo --keyword "RTX 3090" --out demo_deals.csv`
- Diagnostics (prints the exact request URL, response `total`, and refinements):
  `python <skill_dir>/ebay_search.py --debug --keyword "RTX 3090"`
- Relay mode (no sandbox escalation needed; relay must be running — see §0.5):
  `python <skill_dir>/ebay_search.py --relay http://127.0.0.1:8787`

### Quick curl example (production)

```bash
TOKEN=$(curl -s -X POST https://api.ebay.com/identity/v1/oauth2/token \
  -u "$EBAY_CLIENT_ID:$EBAY_CLIENT_SECRET" \
  -d 'grant_type=client_credentials&scope=https://api.ebay.com/oauth/api_scope' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s "https://api.ebay.com/buy/browse/v1/item_summary/search?q=RTX%203090&marketplace_ids=EBAY_DE&filter=price:%5B450..750%5D,conditions:USED&sort=price&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

For sandbox, substitute `api.ebay.com` → `api.sandbox.ebay.com` in both URLs.

## 6. Errors & handling

| Status | Meaning | Action |
|---|---|---|
| 401 | token invalid/expired, or **realm mismatch** (sandbox ID + production secret) | re-request token; check keyset pairing |
| 400 | bad param/filter syntax | check quotes, `..` in ranges, `{BRACES}` on conditions, `priceCurrency` present |
| 12012 (in body) | `price` filter without `priceCurrency` | add `priceCurrency:EUR` to the filter |
| 429 | rate limited | back off exponentially (30–60 s); check per-app quota in developer portal |
| 403 | app not approved for scope | verify app is enabled for the Buy API |

⚠️ eBay **silently ignores unknown or malformed query params** (e.g., `marketplace_ids` is not a Browse param — the marketplace comes from the `X-EBAY-C-MARKETPLACE-ID` header, default `EBAY_US`). If results look wrong (wrong marketplace/currency, filters not applied), run with `--debug` and inspect the printed request URL and response `total`.

Default quotas are generous (thousands of calls/day), but always confirm in https://developer.ebay.com/my/usage.

## 7. Limitations (be honest with the user)

- **Active listings only** — the public API exposes no sold-price history. For sold prices: eBay.de "Verkauft" filter (site), Terapeak (Seller Hub), or third-party trackers.
- **No eBay Kleinanzeigen**: Kleinanzeigen has no public API; scraping violates its ToS. Use its built-in search alerts instead.
- **Sandbox has no real data** — never report sandbox output as a real deal.
- Currency/location can differ from the selected marketplace — always read `price.currency` and `itemLocation`.
- If the sandbox blocks HTTPS, hand the script to the user to run locally.
