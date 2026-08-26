# 🛒 Used AI Hardware — Nightly Price Report & Sourcing Kit (eBay.de · Kleinanzeigen · EU)

<!-- Badges are pre-filled for aicologne/aic-hardware-deals -->
[![Nightly scan](https://github.com/aicologne/aic-hardware-deals/actions/workflows/ebay-scan.yml/badge.svg)](https://github.com/aicologne/aic-hardware-deals/actions/workflows/ebay-scan.yml)
[![GitHub Pages](https://img.shields.io/github/deployments/aicologne/aic-hardware-deals/github-pages?label=GitHub%20Pages&logo=github)](https://github.com/aicologne/aic-hardware-deals/deployments)
[![Last scan](https://img.shields.io/github/last-commit/aicologne/aic-hardware-deals?label=last%20scan)](https://github.com/aicologne/aic-hardware-deals/commits/main/LATEST.md)
[![License](https://img.shields.io/github/license/aicologne/aic-hardware-deals)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](ebay-search-skill/ebay_search.py)
[![RSS](https://img.shields.io/badge/RSS-daily%20deals-FFA500?logo=rss&logoColor=white)](site/feed.xml)

A working deal-hunting kit for buying used/refurbished hardware (headless mini PCs, ≥16 GB VRAM GPUs for local AI, DDR4/DDR5 RAM) — **to resell, to build with, or just to track the market**. It combines:

- **Live market data** from eBay.de via the official Browse API (with a sandbox-friendly HTTP relay),
- **A five-shop review** of German used-hardware dealers (serverando, servershop24, serverschmiede, servermall, plusedv),
- **A Kleinanzeigen playbook** (alerts, testing, negotiation, scam flags) tuned to the current 2026 DRAM-shortage market,
- **A 2× RTX 3090 AI-workstation build plan** with two priced paths (DDR4/X99 vs. DDR5/AM5) and a full parts matrix,
- **Working Python tooling** (`ebay-search-skill/`) that you can run in two minutes,
- **Facebook Marketplace deep links** (`facebook-marketplace-skill/`) — per-country/city search URLs for the same niches, since Marketplace has no public API (no scraping — see below).

> ⚠️ Prices are **snapshots** (probed 2026-08-14 and via archived captures). The market is moving fast — treat this as a methodology and a starting point, not a price list. Always verify live before buying.

---

## Three ways to use this repo

| You want to… | Start here |
|---|---|
| 🔄 **Flip used hardware** — buy low (private sellers/shops), verify, sell tested at market | [`kleinanzeigen_playbook.md`](kleinanzeigen_playbook.md) + the 🔥 deal highlights in the [nightly report](LATEST.md) |
| 🛠️ **Build a budget local-AI rig or homelab** — 2× RTX 3090 workstation, DDR4 vs. DDR5, what fits €1,000 / €2,000 / €3,000 | [`build_plan_2x3090.md`](build_plan_2x3090.md) + [`build_parts_matrix.md`](build_parts_matrix.md) · new here? start with [`glossary.md`](glossary.md) |
| 📊 **Track the DRAM-shortage market in numbers** — nightly medians, buy-low flags, price context | [nightly report](LATEST.md) · [live site](https://aicologne.github.io/aic-hardware-deals/) · [RSS feed](site/feed.xml) |

---

## Repository contents

| File | What it is |
|---|---|
| [`LATEST.md`](LATEST.md) | **The final price report** — regenerated every night by the workflow (deal highlights, per-category medians, €/GB value, 30-day trend, median movers, market index, buy-low flags) |
| [`ebay_deals.csv`](ebay_deals.csv) | Raw scan output (30 queries, EUR/used, client-side filtered, with marketplace column) |
| [`site/data/history.csv`](site/data/history.csv) | **Price history** — one median/cheapest row per (marketplace, category) per scan date; powers the 30-day trendline, movers and the index |
| [`site/data/listing_history.csv`](site/data/listing_history.csv) | **Per-listing price history** — first-seen vs last-seen per listing URL, for "was €X on DATE" repricing notes and **price-drop alerts** |
| [`sold_anchors.csv`](sold_anchors.csv) | **Sold-price anchors (opt-in)** — median sold price per category from eBay's "Verkauft" search, merged into the report as resale context (generated only when `EBAY_SOLD_ANCHORS=1` is set) |
| [`site/feed.xml`](site/feed.xml) | **RSS feed of the daily deal highlights** — regenerated every night, served at `/feed.xml` on the Pages site |
| `site/data/marketplace/` | **Facebook Marketplace board data (nightly)** — `searches.csv` + `*.md` (per-country/city deep links for the key niches), `collected_links.txt` (paste links from your own browsing), `watchlist.csv`/`watchlist.md` (deduped, first/last-seen). Links only, no listings — Marketplace has no public API (see `facebook-marketplace-skill/`) |
| [`glossary.md`](glossary.md) | **Bilingual glossary (EN/DE)** — plain-language explanations of RDIMM, ECC, VRAM, €/GB, buy-low targets, … |
| [`build_plan_2x3090.md`](build_plan_2x3090.md) | Detailed build plan for the 2× RTX 3090 AI tower (DDR4/DDR5 paths, server question, sourcing matrix) |
| [`build_parts_matrix.md`](build_parts_matrix.md) | **4 build configurations** — platform (DDR4/X99 vs DDR5/AM5) × GPU generation (newer RTX vs. older Quadro), all priced from live scans |
| [`kleinanzeigen_playbook.md`](kleinanzeigen_playbook.md) | The full Kleinanzeigen strategy: 25+ search alerts, test protocols, negotiation script, scam flags |
| `ebay-search-skill/` | Working tooling: Browse API scanner (multi-marketplace), local relay, report/history/listing/feed renderers, alert notifier, skill docs |
| `facebook-marketplace-skill/` | **Country/city search-link generator** for Facebook Marketplace (19 countries): builds the exact deep links Marketplace understands (keyword, exact phrase, radius, min/max price, sort, days listed, delivery) and can print, open, or save them as a markdown report — **deep links only, no scraping** (Marketplace has no public API) |
| `.github/workflows/ebay-scan.yml` | Nightly scan → history → report → feed → alerts → GitHub Pages deployment |
| [`ebay.env.example`](ebay.env.example) | Credentials template (never commit the real `ebay.env`) |
| [`SETUP.md`](SETUP.md) | Step-by-step GitHub + Pages setup (this repo, ready to publish) |
| [`selfhost_fonts.py`](selfhost_fonts.py) | One-time font self-hosting: downloads the Inter variable-font woff2 files (latin/latin-ext, OFL-licensed) into `site/fonts/` and generates `site/fonts.css` — removes the Google Fonts dependency from the site (re-run after changing weights) |

---

## TL;DR — the 2026 market in five bullets

1. **Used RTX 3090 (24 GB) now asks €1000–1500 on eBay.de** — the GDDR/DRAM shortage pushed used prices far past the old €450–750 "value king" window. Cheapest complete card seen: €1000 (ex-mining, watercooled); typical air-cooled €1149–1500; Founders Edition €1400.
2. **RAM is the widest arbitrage window**: shops ask €219–230 for a 32 GB DDR4 RDIMM, while private Kleinanzeigen sellers still list pre-shortage stock at €60–120. DDR5 German retail is ~4.2–4.5× its July-2025 level.
3. **Mini PCs: buy 8th gen+, skip 6th gen.** EliteDesk 800 G4 Mini / OptiPlex 3070 Micro / ThinkCentre M720q–M920q resell at €200–300 with real homelab/AI-crossover demand; 6th-gen (ProDesk 400 G2 class) sits at the €130–150 floor and moves slowly.
4. **Of the five German shops, only two matter for this strategy**: [serverando.de](https://serverando.de) (ECC server RAM supply, occasional mini PC) and [servershop24.de](https://servershop24.de) (RAM category + a GPU category worth a manual sweep). The others are server/datacenter or telecom dealers.
5. **Verify live, weekly** — the shortage is the single biggest variable. The tooling below does exactly that.

---

## Live market snapshot (probed 2026-08-14 via the Browse API, eBay.de, used, EUR)

| Item | Asking price | Notes |
|---|---|---|
| RTX 3090 24 GB | **€1000–1500** | cheapest full card €1000 ex-mining watercooled; typical €1149–1500; FE €1400; one with 12-month warranty €1399.90 |
| RTX 3090 Ti | ~€1450 (FE) | |
| 32 GB DDR4-2666 RDIMM (serverando, shop) | €229.95 | private market €60–120 → arbitrage |
| 32 GB DDR4-2933/3200 RDIMM | €219–450 (shop, snapshot) | check live; 3200 is premium |
| 64 GB DDR4 RDIMM/LRDIMM | €319.95–895.95 (shop snapshots) | speed/rank drive huge spreads |
| 16 GB DDR4 regECC | €24.95 (Aug'25) → €149.95 (Jul'26) | the shortage in one line |
| HP ProDesk 600 G5 Mini i3/8/256 | €169.95 (serverando, Mar'26) | market-fair, liquid, Win11 |
| EliteDesk 800 G4 Mini i5-8500T | €199–272 (refurb stores) | the resale sweet spot |
| Strix Halo (Ryzen AI Max 395) | used €2,340–4,625 · **new BOSGAME M5 128 GB €1,581–1,700** | used prices above new = overpriced; buy used only < €1,400–1,500 or buy new ([EU €1,581](https://news.miracleplus.com/share_link/94219), [US $1,699](https://www.tweaktown.com/news/105448/check-out-bosgames-new-monster-mini-pc-powered-by-amds-strix-halo-apu-costs-1699/index.html)) |

Context anchors: DDR5 German retail **+419–448% vs July 2025** ([wccftech](https://wccftech.com/ddr5-memory-prices-continue-to-spiral-upwards-in-germany-now-419-higher-than-in-july-2025/)); used RTX 3090 **+17% MoM**, RTX 4090 **+28–33% MoM** in the May-2026 spike ([UsedGamer](https://www.usedgamer.com/blog/used-gpu-prices-spiking-may-2026), [LLM Requirements](https://llmrequirements.com/news/2026-05-23-memory-shortage-may-price-spike)).

---

## The five German shops, reviewed

| Shop | What it is | Fit for this strategy | Verdict |
|---|---|---|---|
| [serverando.de](https://serverando.de) | ~20-year-old used-server dealer; ECC RDIMM/LRDIMM RAM, servers, CPUs, storage, some laptops/minis | **RAM supply** (tested, warranty PDF) + occasional mini PC | ✅ **Best RAM source of the five** — verify prices live |
| [servershop24.de](https://servershop24.de) | ServerShop24 GmbH; used servers + DDR3/DDR4/DDR5 server RAM + GPU category + buy-back program | RAM category; graphic-cards category sorted by price | ⚠️ **Worth a manual sweep**; archived DDR5 prices (32 GB @ €99.99, Aug'25) were pre-spike |
| [serverschmiede.com](https://www.serverschmiede.com) | Serverschmiede.com GmbH (Hirschfeld); B2B/gov enterprise servers & networking; custom configurator shop | none of the three categories verifiable (catalog not indexable) | 🔍 Verify manually; Trustami-reviewed, real GmbH |
| [servermall.com](https://servermall.com) | UAB ServerMall (Vilnius); rack servers + **new** datacenter GPUs (T4/L40/A100/H100), 5-year warranty claims | none (no mini PCs, no used consumer GPUs, no standalone RAM) | ❌ Datacenter-only; skip for flipping |
| [plusedv.de](https://www.plusedv.de) | Telecom/legacy-IT dealer (IP phones, headsets, ISDN, old Windows licenses, surveillance) | none | ❌ Not relevant to hardware flipping |

**Detail notes:**
- **serverando** prices verified from archived product pages: 32 GB DDR4-2666 regECC **€229.95** (Feb'26), 64 GB DDR4-2933 regECC **€449.95** (Feb'26), 64 GB DDR4-2666 LRDIMM **€319.95** (Dec'25), 64 GB DDR4-3200 LRDIMM **€895.95** (May'26), 16 GB DDR4-2666 **€24.95** (Aug'25 — the pre-spike price), plus a **51× DDR3 mixed module lot at €139.95** (≈€2.74/module, bulk play).
- **servershop24** archived: Transcend 32 GB DDR5 **€99.99** (Aug'25), 16 GB DDR5 **€59.99** (Sep'25) — pre-spike; if any of those SKUs are still priced near that, buy immediately. ZOTAC GTX 1080 Ti was €279.99 back in 2023 (historical).
- **serverschmiede** surfaced a **Tesla T4 16 GB** configurator at ~€821 (Sep'25 snapshot) — meets the 16 GB VRAM bar, but it's a datacenter card; weak flip candidate.
- These shops repriced for the shortage — **the private Kleinanzeigen market is where the margin lives now** (see the playbook).

---

## Kleinanzeigen — the primary sourcing channel

Full details in [`kleinanzeigen_playbook.md`](kleinanzeigen_playbook.md) (21 ready-to-use search alerts, on-the-spot test protocols, German negotiation script, 9 scam red flags, margin table). Highlights:

- **Sourcing**: saved searches + push alerts; private sellers lag shop prices 15–30 %; post your own "Suche" ads; cash + pickup; never pay in advance.
- **The arbitrage**: 32 GB DDR4 RDIMM at €60–120 private vs. €219–230 shop → buy low, sell tested at market. RTX 3090 at €800–1000 private → €1250–1500 on eBay.de.
- **Scam rules**: refusal of pickup, deposits, fake payment confirmations, payment links, Computrace/BIOS-locked gear — all hard stops.
- **Test before you pay**: memtest86, GPU-Z (watch for BIOS-modded "32 GB RTX 4080" cards — resale poison), SMART, stress loops.

---

## Tooling — the eBay scanner

`ebay-search-skill/` contains a complete, tested deal scanner for the **eBay Browse API**:

| File | Purpose |
|---|---|
| `ebay_search.py` | CLI scanner: 30 default queries (GPUs ≥16 GB incl. Quadro RTX, Radeon PRO W7800/W7900, Tesla T4/P100, RTX 4060 Ti 16 GB, 8th-gen mini PCs, DDR4/DDR5 RAM incl. RDIMM, NVMe 2 TB, Macs with big unified memory, AI hardware — DGX Spark / Strix Halo, whole gaming PCs, X99 build parts), realm auto-detection (sandbox vs production), correct filter syntax, client-side currency/price/condition enforcement, **adaptive deal windows** from the price history, **multi-marketplace mode** (`--marketplaces EBAY_DE,EBAY_AT,…` or the `EBAY_MARKETPLACES` env var, per-marketplace currency), `--demo`/`--debug`/`--relay` modes, CSV output with marketplace column |
| `ebay_relay.py` | Local HTTP relay (127.0.0.1 only) that forwards to eBay's HTTPS API — enables live scans from network-restricted environments (e.g., a DSH sandbox that blocks outbound HTTPS but allows loopback HTTP) |
| `render_report.py` | Renders `ebay_deals.csv` → `LATEST.md` (deal highlights, per-category medians, **€/GB column**, **Net column after ~13 % eBay fees**, buy-low flags, 30-day trend + **median movers** + **market index** from `site/data/history.csv`, **repricing notes** from `site/data/listing_history.csv`, **sold medians** from `sold_anchors.csv`, marketplace columns in multi-marketplace mode) |
| `windows.py` | **Adaptive deal windows** — refines each query's static min/max from the last 30 days of medians (`site/data/history.csv`): the buy-low target tracks the market's lower quartile and the window ceiling widens as prices rise, so the scan and the 🔥 flags never go stale |
| `sold_anchors.py` | **Sold-price anchors (opt-in)** — best-effort median sold prices per category from eBay's public "Verkauft" search → `sold_anchors.csv`, shown in the report as "sold median €X (n=Y)"; set the repo Variable `EBAY_SOLD_ANCHORS=1` to enable |
| `render_history.py` | Appends one median/cheapest row per (marketplace, category) per scan date to `site/data/history.csv` (idempotent — re-runs replace the same date's rows) |
| `render_listing_history.py` | Tracks first-seen vs last-seen price per listing URL in `site/data/listing_history.csv` (repricing detection; stale entries pruned after 60 days) |
| `render_feed.py` | Renders `ebay_deals.csv` → `site/feed.xml` (RSS 2.0 feed of the daily deal highlights for the Pages site, incl. marketplace + repricing notes) |
| `notify.py` | **Buy-low + price-drop alerts** — sends NEW flagged deals **and** listings that dropped ≥5 % below their first-seen price to Telegram and/or Discord (state file dedupes across runs; `--dry-run` to preview) |
| `SKILL.md` | The same knowledge packaged as a [DeepSeek Harness](https://github.com/deepseek-ai) skill — plain Markdown instructions, usable standalone too |

### What the scanner knows (hard-won lessons, all verified against the [Browse API spec](https://developer.ebay.com/api-docs/master/buy/browse/openapi/3/buy_browse_v1_oas3.yaml))

- **Marketplace is a header, not a query param**: `X-EBAY-C-MARKETPLACE-ID: EBAY_DE` (a `marketplace_ids` query param is silently ignored → results fall back to `EBAY_US`/USD).
- **`price` requires `priceCurrency`** (API error 12012).
- **Condition values take curly braces**: `conditions:{USED}`.
- **Use category IDs to kill keyword noise** ("RTX 3090" otherwise matches an iPhone *A3090*): `27386` Grafik-/Videokarten, `171957` Desktops & All-in-One-PCs, `170083` Arbeitsspeicher (RAM), `11210` Server-Speicher (RAM) — fetched live from the eBay.de Taxonomy API.
- eBay **silently ignores malformed params** — so the scanner also enforces the deal window client-side and reports dropped items.
- **Deal windows are adaptive**: the static min/max in `queries.py` are the fallback; once `site/data/history.csv` has a few days of medians per category, `windows.py` derives the scan window from the market (lower-quartile buy-low target, ceiling that widens as prices rise). Categories the shortage pushed above their old windows (RTX 3090, DDR5, …) are no longer invisible.

### Quick start

```bash
# 0) prerequisites: python3 + requests; a free eBay developer app (production keyset)

# 1) credentials
cp ebay.env.example ebay.env          # then paste your Client ID + Secret into it

# 2) offline sanity check (no API calls, no credentials needed)
python ebay-search-skill/ebay_search.py --demo --keyword "RTX 3090" --min 450 --max 750

# 3) live scan — direct (needs normal outbound HTTPS)
python ebay-search-skill/ebay_search.py

# 3b) live scan — via the relay (works from network-restricted sandboxes)
python ebay-search-skill/ebay_relay.py &                     # terminal 1
python ebay-search-skill/ebay_search.py --relay http://127.0.0.1:8787   # terminal 2

# one-off query with overrides
python ebay-search-skill/ebay_search.py --keyword "RTX 3090" --min 750 --max 1150 \
    --category 27386 --out rtx3090.csv
```

Output: console table + `ebay_deals.csv` (Excel-compatible).

---

## Tooling — Facebook Marketplace search links (no API, no scraping)

Facebook Marketplace has **no official public API** (unlike eBay's Browse API),
and scraping it violates Facebook's ToS — so this repo integrates Marketplace
the only supported way: **deep links**. `facebook-marketplace-skill/` generates
the exact search URLs Marketplace itself produces, for **19 countries**
(DE AT CH NL BE FR IT ES PT GB IE DK SE NO FI PL CZ US CA) and any city:

| File | Purpose |
|---|---|
| `fb_marketplace.py` | CLI: keyword + country/city → clickable Marketplace search links. Flags: `--city all` (every registered city), `--countries DE,AT,CH,GB` (multi-country), `--no-location` (uses the account's saved location), `--exact`, `--radius`, `--min/--max` (local currency), `--sort newest/price-asc/price-desc/ranking`, `--days 1/7/30`, `--delivery local/meetup/pickup`, `--open` (launch browser), `--report out.md` (markdown sheet), `--csv out.csv` (append rows to a combined CSV), `--list`, `--parse URL` (**glean info from an existing link offline** — keyword, location, radius, prices, sort, days, delivery, item ID), and `--collect file` (**watchlist**: parse links you pasted from your own browsing into a deduped first/last-seen watchlist, offline) |
| `cities.py` | Per-country registry: marketplace currency + default city + city list (English-exonym slugs, e.g. `cologne`, `vienna`, `rome`) |
| `SKILL.md` | The same knowledge as a [DeepSeek Harness](https://github.com/deepseek-ai) skill, incl. the honest API/ToS picture |

```bash
# one market (the exact pattern of the URL in the repo, plus a price window)
python facebook-marketplace-skill/fb_marketplace.py --country DE --city cologne \
    --query "RTX 5070" --exact --radius 65 --min 500 --max 900

# every registered German city, newest first, last 7 days
python facebook-marketplace-skill/fb_marketplace.py --country DE --city all \
    --query "RTX 3090" --max 1100 --sort newest --days 7

# multi-country scan (default cities) → clickable markdown sheet
python facebook-marketplace-skill/fb_marketplace.py --countries DE,AT,CH,GB \
    --query "RTX 5070" --report fb_marketplace_links.md
```

Fully offline — no credentials, no network, no approvals needed. Prices are
shown in each market's local currency (EUR/GBP/CHF/PLN/CZK/DKK/SEK/NOK/USD/CAD);
results depend on the logged-in account's region. If a city slug ever stops
resolving, drop it (`--no-location`) — the account's saved location takes over.
Third-party "Marketplace API" scraper services (Apify, Social Fetch, …) exist
but violate Facebook's ToS and break constantly — out of scope here, same
stance as Kleinanzeigen.

**In the nightly workflow:** `ebay-scan.yml` regenerates the four link sheets
into `site/data/marketplace/*.md` plus one combined `searches.csv` every run
(niches: RTX 3090, RTX 5070, mini PCs, RAM), builds the watchlist from
`collected_links.txt` if present, commits everything with the rest of the
scan, and the Pages site serves it all as the **Marketplace board** (watchlist
table + per-query search tables). Change the countries via the
`FB_MARKETPLACES` repo Variable (default `DE,AT,CH,GB`).

---

## Automated nightly scans (GitHub Actions)

The repo ships `.github/workflows/ebay-scan.yml`:

- **Runs daily at 05:00 UTC** (`schedule` cron — GitHub Actions cron is UTC) plus a manual **Run workflow** button (`workflow_dispatch`).
- Executes `ebay_search.py` with credentials injected from **GitHub secrets** (never stored in the repo), then updates the price history, per-listing price history, renders **`LATEST.md`** + **`site/feed.xml`**, optionally sends buy-low alerts, and commits everything back to the repo.
- **Multi-marketplace (optional):** set a repo **Variable** `EBAY_MARKETPLACES` (e.g. `EBAY_DE,EBAY_AT,EBAY_CH`) under **Settings → Variables → Actions**; each marketplace is scanned with its default currency. Empty/unset = `EBAY_DE` only.
- **Facebook Marketplace link sheets + board:** the same nightly run regenerates `site/data/marketplace/*.md` **and** one combined `searches.csv` — deep-link search sheets per country/city for the key niches (RTX 3090, RTX 5070, mini PCs, RAM) using `facebook-marketplace-skill/fb_marketplace.py` (offline, no credentials). The Pages site renders them as the **Marketplace board** (`marketplace.js`). Countries come from a repo **Variable** `FB_MARKETPLACES` (e.g. `DE,AT,CH,GB`); empty/unset = `DE,AT,CH,GB`.
- **Marketplace watchlist (user-driven):** commit Marketplace links you found while browsing (your own browser, normal use) into `site/data/marketplace/collected_links.txt`; the nightly job runs `fb_marketplace.py --collect` on it (offline parsing) and tracks them in `watchlist.csv` with first/last-seen dates. **These are links, not listings** — Marketplace has no public API and scraping violates its ToS, so the sheets are entry points to open in a logged-in browser, not a data feed.
- Skips the commit when nothing changed; `concurrency` prevents overlapping runs.

### Setup (2 minutes)

1. Push the repo including `.github/workflows/ebay-scan.yml`.
2. Repo → **Settings → Secrets and variables → Actions** → add two repository secrets:
   - `EBAY_CLIENT_ID` — your production Client ID
   - `EBAY_CLIENT_SECRET` — your production Client Secret
3. Repo → **Settings → Pages** → Source: **"GitHub Actions"** (once).
4. **Actions → "eBay deal scan (nightly)" → Run workflow** to trigger the first scan.
5. Read the results: **`LATEST.md`** in the repo, or the rendered site at
   `https://<your-user>.github.io/<repo>/`.

> ⚠️ The workflow needs the **production** keyset — a sandbox (`SBX`) keyset produces only test data and a misleading report.

**Optional: sold-price anchors** — set a repo **Variable** `EBAY_SOLD_ANCHORS=1` under **Settings → Variables → Actions** to make the nightly run fetch median sold prices from eBay's "Verkauft" search (`sold_anchors.py`, best-effort — see Methodology). Unset = skipped.

### Buy-low + price-drop alerts (optional, Telegram / Discord)

The nightly run also notifies you when **new** listings hit the buy-low window **and** when a watched listing drops ≥5 % below its first-seen price. Only deals and drops that have not been reported before are sent (a state file dedupes across runs), so you get a ping when something new shows up — not every night.

1. **Telegram**: create a bot with [@BotFather](https://t.me/BotFather) → get `TELEGRAM_BOT_TOKEN`; message your bot once, then get your `TELEGRAM_CHAT_ID` (e.g. via `https://api.telegram.org/bot<TOKEN>/getUpdates`).
2. **Discord** (alternative or in addition): create a webhook in your server channel → copy `DISCORD_WEBHOOK_URL`.
3. Add the secrets you use to **Settings → Secrets and variables → Actions**. The alert step only runs when at least one channel is configured.

```bash
# preview locally without sending (state file is only written on real sends)
python ebay-search-skill/notify.py ebay_deals.csv --state site/data/notified.json \
    --listing-history site/data/listing_history.csv --dry-run
```

## The report (`LATEST.md`) — the final product

Every nightly run commits `ebay_deals.csv` and renders **`LATEST.md`** — a self-contained price report with:

- 🔥 **Deal highlights** — listings currently at or within 15 % of the buy-low target (the shortlist to inspect first), with **repricing notes** ("was €X on DATE")
- Per-category sections with the **deal window, median, cheapest item**, a **€/GB value column**, a **Net column (asking price after ~13 % eBay fees)**, a **sold median** when sold anchors are enabled, a **30-day median trend** once history has accumulated, and per-listing notes (`🔥 at/near buy-low` / `⚠️ above scan window`)
- **📊 Used-market index + median movers** — an aggregate "market index" headline (mean of category median changes vs. ~7 days back) plus risers/fallers vs. the previous scan, once history has accumulated
- Market context, methodology, and a fees disclaimer

The workflow also publishes `ebay_deals.csv` into `site/data/` and deploys `site/` to **GitHub Pages**. The page (`site/index.html`) is a thin shell: it **reads its listings from the generated CSV at runtime** (`app.js` fetches `data/ebay_deals.csv`), renders the same deal highlights, per-category tables and medians in the browser, and builds a table of contents with scroll-spy navigation. The load path is optimized for slow connections: the report renders from a **single fetch** (history/repricing data upgrades the page in the background), the Inter font is **self-hosted** (`site/fonts.css` + woff2, OFL-licensed — zero third-party font hosts), and `history.csv`/`listing_history.csv` are **capped** (180 days / 3000 listings) so the site stays fast as the repo ages. No listing data is baked into the HTML, so the nightly scan alone refreshes the site. The site has a modern responsive design with a sticky app bar, a **light/dark theme** (auto-detects the OS preference), an **EN/DE language toggle**, **interactive filters** (search, marketplace, category, max price, sort by price / best-deal / best-€/GB), **flag chips** for deal/above-window listings, **30-day median sparklines** that expand into full trend charts (from `data/history.csv`), **median movers** and a **market index**, **repricing notes** (from `data/listing_history.csv`), a quick-start **glossary**, and a **PWA manifest**. The same run renders **`site/feed.xml`** — an RSS feed of the deal highlights you can subscribe to at `/feed.xml`.

---

## Methodology & data quality (read before trusting any number)

- **eBay prices**: live Browse API probes (production keyset), category-restricted, used + currency enforced both server- and client-side (EUR default; per-marketplace currency in multi-marketplace mode). **Deal windows adapt to the last 30 days of history** (`windows.py`), so flags stay relative to the current market.
- **Net column**: asking price minus the ~13 % eBay seller fee (configurable via the `EBAY_FEE_RATE` env var) — shipping and your own costs still apply.
- **Sold anchors**: `sold_anchors.csv` comes from eBay's public "Verkauft" search (opt-in, `EBAY_SOLD_ANCHORS=1`) — best-effort HTML parsing, sample size shown, no Browse-API guarantee. Absence of an anchor = not fetched, not "no sales".
- **Shop prices**: mostly **archived snapshots** (Wayback Machine) because the research sandbox cannot fetch HTTPS directly — every price carries its capture date, and several (e.g., servershop24 DDR5) are *pre-shortage* and almost certainly stale. **Verify live**.
- **Kleinanzeigen**: no public API; prices come from real ads + market-tracker anchors, not systematic scraping.
- **Absence ≠ absence**: serverschmiede/plusedv catalogs are barely indexable — "not found" means "verify manually", not "doesn't exist".
- The Browse API exposes **active listings only** — no sold-price history (use eBay.de's "Verkauft" filter or Terapeak for that).

---

## Ideas for the next iteration

- [x] **Scheduled nightly scan** (GitHub Actions) that commits fresh `ebay_deals.csv` + rendered `LATEST.md`
- [x] **LATEST.md as the final price report** — deal highlights, per-category medians/windows, buy-low flags
- [x] **CSV-driven web report** — `site/` reads `ebay_deals.csv` at runtime (no data embedded in HTML) + table of contents
- [x] **Visitor tracking (GoatCounter)** — cookieless; set your site code in `site/index.html` (see SETUP.md)
- [x] **RSS feed** — `site/feed.xml` with the daily deal highlights, regenerated by the nightly run
- [x] **Bilingual site (EN/DE)** — language toggle on the Pages site (listing titles stay German; UI and methodology text switch)
- [x] **Buy-low alerts (Telegram/Discord)** — `notify.py` pings only *new* flagged deals (state file dedupes across runs)
- [x] **Price history + 30-day median trend** — `site/data/history.csv` (one row per category per day) + sparkline on the site and a trend in `LATEST.md`
- [x] **Interactive site filters** — search, category, max price, sort (price ↑/↓, best deal first, best €/GB)
- [x] **Multi-marketplace mode** — `--marketplaces` / `EBAY_MARKETPLACES` (EBAY_DE, EBAY_AT, EBAY_CH, …) with per-marketplace currency, marketplace column + filter on the site
- [x] **€/GB value metrics** — capacity map (24 GB RTX 3090, 32 GB RDIMM, …) → €/GB column and a "Best €/GB" sort
- [x] **Median movers + market index** — risers/fallers vs. the previous scan and an aggregate **"Used-market index" headline** in `LATEST.md` and on the site
- [x] **Per-listing repricing notes** — `site/data/listing_history.csv` tracks first-seen vs last-seen prices ("was €X on DATE")
- [x] **Glossary (EN/DE)** — [`glossary.md`](glossary.md) + a quick-start glossary on the site
- [x] **Dark mode + PWA manifest + expandable trend charts + JSON-LD** — site polish
- [x] **Adaptive buy-low targets** — `windows.py` derives each category's window from the last 30 days of history, so scan windows and 🔥 flags follow the market (static windows in `queries.py` are only the fallback)
- [x] **Net-price column** — every report table shows the asking price net of the ~13 % eBay fee (override with `EBAY_FEE_RATE`)
- [x] **Price-drop alerts** — `notify.py` pings listings that dropped ≥5 % below their first-seen price
- [x] **Sold-price anchors (opt-in)** — `sold_anchors.py` fetches median sold prices from eBay's "Verkauft" search → "sold median €X (n=Y)" in the report
- [x] **More scan categories** — MacBook Pro Max / Mac Studio Ultra (big unified memory), RTX 4060 Ti 16 GB, Radeon PRO W7800/W7900, Tesla T4/P100, DDR5 RDIMM, NVMe 2 TB — and current-market static windows for the shortage-era prices
- [ ] **Kleinanzeigen auto-digest** — automate the private-market channel (nightly search of saved alerts, below-target filtering, same alerting)
- [ ] **Dynamic build configurator** — budget → cheapest current parts assembled from the live CSV
- [ ] **Seller-feedback column** (needs one extra Browse API call per item)

---

## License & disclaimer

MIT (see [LICENSE](LICENSE)). Prices and market conditions change constantly; this repository is research and tooling, **not financial advice**. Always verify condition, warranty, and current prices before buying. Respect the terms of service of eBay, eBay Kleinanzeigen, and the shops involved — and never publish your API credentials (`ebay.env` is gitignored for a reason).
