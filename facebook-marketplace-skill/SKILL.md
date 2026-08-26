---
name: facebook-marketplace
description: Build Facebook Marketplace search deep links for any country/city (DE, AT, CH, NL, BE, FR, IT, ES, PT, GB, IE, DK, SE, NO, FI, PL, CZ, US, CA) with keyword, exact phrase, radius, min/max price, sort, days-listed and delivery filters. Deep links only — Facebook has no public Marketplace API, so this skill generates the exact URLs Marketplace understands (same pattern as facebook.com/marketplace/cologne/search/?query=...&exact=false&radius=65) instead of fetching listings. Use whenever the user wants per-country Facebook Marketplace searches, comparison links across countries, or a clickable per-city search sheet.
whenToUse: The user asks to search or compare Facebook Marketplace across countries/cities, wants per-country Marketplace search links for a keyword/price window, or asks whether Marketplace can be integrated like the eBay skill.
---

# Facebook Marketplace — country/city search links

Facebook Marketplace has **no official public API** — unlike eBay's Browse API
(see `ebay-search`), there is nothing to query for listing data. What *is*
fully supported — and what this skill automates — is the **deep-link surface**:
the exact URLs Marketplace itself generates, which work for any country and
city. This skill turns "give me the RTX 5070 market in several countries" into
one command that prints (and can open or save) every search URL, with the same
filters you would click in the UI.

## 0. What this is — and what it deliberately is not

| | This skill | Not this skill |
|---|---|---|
| Input | keyword, country, city, radius, price window, sort, age | — |
| Output | **Clickable deep links** per country/city (console / browser / markdown report) | ❌ listing data, prices, sellers |
| Network | **None — fully offline** (no credentials, no approvals needed in a sandbox) | — |
| ToS | 100 % clean: it only constructs public URLs | scraping / headless browsers / third-party "Marketplace API" services (all violate Facebook's ToS — see §7) |

The tool is `fb_marketplace.py` (companion `cities.py` holds the per-country
registry). Run from the skill directory or give the full path.

## 1. URL anatomy (the pattern this skill generates)

```
https://www.facebook.com/marketplace/<location>/search/?query=KEYWORD&exact=false&radius=65&minPrice=500&maxPrice=900&sortBy=price_ascend&daysSinceListed=7&deliveryMethod=local_shipping
```

- `<location>` is the **city slug** — lowercase, no spaces, English exonym
  (`cologne` for Köln, `munich` for München, `vienna` for Wien, `rome` for
  Roma, `london`, `paris`, …). Verified live (2026): `cologne` resolves.
- Omitting `<location>` entirely → `…/marketplace/search/?query=…` uses the
  **account's saved location** — the built-in fallback when a slug stops
  resolving.
- Parameters are plain query-string keys; Facebook **silently ignores**
  unknown/renamed ones, so a stale param degrades to a working search page.

| Param | Values | Notes |
|---|---|---|
| `query` | free text | the keyword; the only required one |
| `exact` | `true` / `false` | exact-phrase match |
| `radius` | integer km (0–500) | default 65 in the CLI |
| `minPrice` / `maxPrice` | integer | **local currency** of the country (EUR, GBP, CHF, PLN, CZK, DKK, SEK, NOK, USD, CAD) |
| `sortBy` | `overall_search_ranking` · `newest_listing` · `price_ascend` · `price_descend` | CLI shortcuts: `ranking` / `newest` / `price-asc` / `price-desc` |
| `daysSinceListed` | 1 · 7 · 30 | new listings only |
| `deliveryMethod` | `local_shipping` · `meetup` · `pickup` | CLI shortcuts: `local` / `meetup` / `pickup` |

### Gleaning info from a link (offline)

`--parse` extracts every piece of info that is *in the link itself* — pure URL
parsing, no network, no page fetch, no ToS issues:

```bash
python <skill_dir>/fb_marketplace.py --parse \
  "https://www.facebook.com/marketplace/cologne/search/?query=rtx%205070&exact=false&radius=65&minPrice=500&maxPrice=900"
# → type=search, location=cologne, keyword="rtx 5070", exact=false,
#   radius_km=65, min_price=500, max_price=900

python <skill_dir>/fb_marketplace.py --parse \
  "https://www.facebook.com/marketplace/item/1234567890/"
# → type=item, item_id=1234567890   (handy for dedupe/tracking single listings)
```

Also handles location-less search links and category links
(`/marketplace/{location}/category/{id}/`); unknown query params are passed
through verbatim. **What is deliberately NOT there:** listing titles, prices,
sellers, results — that data only exists on Facebook's page, and fetching it
is scraping (see §7). The link tells you *what the search is configured to
find*, not *what it found*.

## 2. Countries & cities (the "different countries" part)

`cities.py` ships a registry for **19 countries** (EU-first, mirroring the
repo's hardware-flipping focus) — DE AT CH NL BE FR IT ES PT GB IE DK SE NO FI
PL CZ US CA — each with its marketplace currency and a city list. Print it:

```bash
python <skill_dir>/fb_marketplace.py --list
```

Rules:
- `--country DE` (default) + no `--city` → the country's **default city**
  (DE → `cologne`).
- `--city all` → **every registered city** of the country.
- `--countries DE,AT,CH` → default city of each country in one run.
- `--no-location` → drop the slug (account's saved location).
- Any ad-hoc `--city` value is slug-normalized (umlauts → `ae/oe/ue/ss`,
  spaces removed), so `--city "New York"` → `newyork`.

## 3. Run it

```bash
# the exact URL from the question, rebuilt with a price window:
python <skill_dir>/fb_marketplace.py --country DE --city cologne \
    --query "RTX 5070" --exact --radius 65 --min 500 --max 900

# every registered German city, newest first, last 7 days:
python <skill_dir>/fb_marketplace.py --country DE --city all \
    --query "RTX 3090" --max 1100 --sort newest --days 7

# multi-country scan (default cities): Germany / Austria / Switzerland / UK:
python <skill_dir>/fb_marketplace.py --countries DE,AT,CH,GB \
    --query "EliteDesk 800 G4" --max 200

# open every link in the default browser (logged-in FB needed):
python <skill_dir>/fb_marketplace.py --country DE --city all \
    --query "DDR4 RDIMM 32GB" --open

# save a clickable markdown report:
python <skill_dir>/fb_marketplace.py --countries DE,AT,CH,GB \
    --query "RTX 5070" --report fb_marketplace_links.md

# all supported countries at once, one link per country (saved location):
python <skill_dir>/fb_marketplace.py --countries DE,AT,CH,FR,IT,ES,GB \
    --query "RTX 3090" --max 1100 --no-location

# combined CSV of every generated link (append mode; header written once):
python <skill_dir>/fb_marketplace.py --countries DE,AT,CH,GB \
    --query "RTX 5070" --max 900 --csv searches.csv

# watchlist ("bring your own browsing"): links the user pasted from their OWN
# browser session -> deduped watchlist with first/last-seen dates (offline):
python <skill_dir>/fb_marketplace.py --collect collected_links.txt \
    --state watchlist_state.json --out watchlist.csv --report watchlist.md
```

Typical agent flow: generate the links → hand them to the user (or open the
browser) → the user reads listings manually in each market. This is the same
division of labor the repo already uses for Kleinanzeigen (no API, no
scraping — the UI does the browsing).

**Nightly GitHub workflow:** the repo's `ebay-scan.yml` runs this tool every
night:
- **Link sheets** — regenerates four niche sheets (`RTX 3090`, `RTX 5070`,
  mini PCs, RAM) into `site/data/marketplace/*.md` **plus** one combined
  `searches.csv` (`--csv`), which the Pages site board renders as tables.
  Countries come from the repo Variable `FB_MARKETPLACES` (default
  `DE,AT,CH,GB`).
- **Watchlist** — if the user committed `site/data/marketplace/
  collected_links.txt` (links pasted from their own browsing), the job runs
  `--collect` on it: deduped `watchlist.csv` + `watchlist.md` with
  first/last-seen dates (state persists in `watchlist_state.json`).

**Links only — no listing data is fetched** (Marketplace has no public API;
scraping violates Facebook's ToS).

## 4. DSH sandbox notes

Fully offline — no network, no credentials, no escalation. `python
<skill_dir>/fb_marketplace.py …` runs as-is under workspace-write. `--open`
launches the default browser (harmless, but only do it when the user wants
tabs opened).

## 5. Hardware-flipping quick starts (matches the repo's niches)

```bash
# GPUs: the RTX 5070 market across DACH + UK, price-ascending:
python <skill_dir>/fb_marketplace.py --countries DE,AT,CH,GB \
    --query "RTX 5070" --sort price-asc --report fb_rtx5070.md

# Mini PCs, per-city in Germany (where pickup actually works):
python <skill_dir>/fb_marketplace.py --country DE --city all \
    --query "EliteDesk 800 G4" --max 200 --radius 100

# RAM arbitrage (shops ~€220 vs private ~€60-120): the same query as the
# Kleinanzeigen playbook, but on Marketplace:
python <skill_dir>/fb_marketplace.py --countries DE,AT \
    --query "DDR4 RDIMM 32GB" --min 40 --max 120
```

## 6. Caveats (read before relying on it)

- **Prices are shown in the listing's local currency**; `minPrice`/`maxPrice`
  are interpreted in that currency, and Marketplace does not convert.
- **City slugs can drift.** If a link shows an empty/odd page, drop the slug
  (`--no-location`) — the account's saved location then drives the search.
- The results you see depend on the **logged-in account's region settings**
  and Facebook's ranking; the link is the *entry point*, not a data feed.
- Marketplace coverage varies by country — some regions (e.g. parts of
  Scandinavia) are thinner than DE/UK/US.

## 7. Limitations — the honest answer to "can we integrate Marketplace?"

- **No official API.** Meta's Graph API does not expose Marketplace listing
  search (its commerce endpoints cover a *business's own* catalog, not other
  people's listings). There is no Browse-API equivalent to plug in.
- **Scraping violates Facebook's ToS**, and Meta actively enforces it
  (e.g. the Meta v. Bright Data litigation). The repo takes the same stance
  here as it does for Kleinanzeigen: no scraping, use the platform's own
  surface. Headless-browser "solutions" additionally risk account bans.
- **Third-party "Marketplace API" services** (Apify, Social Fetch, Crawlora,
  Data365, MrScraper, …) exist and will sell you scraped listings — but they
  are unofficial, cookie/session-based, break whenever Facebook changes
  anything, and sit on the wrong side of the ToS line above. Treat them as
  out of scope for this project; if the user insists on raw listing data,
  say so plainly and let them decide.
- **Deep links are the supported integration**: reliable, free, per-country,
  and filter-complete. That is what this skill automates.

## 8. Staying within ToS — what we can (and can't) do

Rule of thumb: **ToS-clean = zero automated requests to facebook.com**.
Everything that touches Facebook happens in the *user's own browser* (normal
use); everything on our side is offline.

| ✅ Within ToS | ❌ Outside ToS |
|---|---|
| Generate deep links (offline) | Any automated fetch of a facebook.com page — even a nightly HTTP ping |
| `--parse` URLs (offline) | Headless browsers / logged-in automation (also risks account bans) |
| **Watchlist (`--collect`)** — user pastes links from their own browsing; we parse them offline, track first/last seen | Third-party "Marketplace API" scrapers (Apify, Social Fetch, …) — they scrape with your cookies |
| Site board rendering the link sheets + watchlist (offline data) | Redistributing scraped data |
| Official Meta Graph API — but only for a business's **own** catalog (not Marketplace browsing) | — |

The legal nuance: [Meta v. Bright Data](https://brightdata.com/blog/web-data/court-rules-in-favor-of-bright-data-in-meta-v-bright-data-case) went the scraper's way on most *statutory* claims about public data, but that ruling is about law, not ToS — Facebook's [Terms](https://www.facebook.com/legal/terms) still contractually prohibit automated access, and enforcement (bot detection, account bans) is what you'll actually hit. Legal grey ≠ ToS-clean, so we stay offline.
