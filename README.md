# 🛒 Used Hardware Deal-Hunting for Resellers — eBay.de + Kleinanzeigen (Germany)

<!-- Badges are pre-filled for aicologne/aic-hardware-deals -->
[![Nightly scan](https://github.com/aicologne/aic-hardware-deals/actions/workflows/ebay-scan.yml/badge.svg)](https://github.com/aicologne/aic-hardware-deals/actions/workflows/ebay-scan.yml)
[![GitHub Pages](https://img.shields.io/github/deployments/aicologne/aic-hardware-deals/github-pages?label=GitHub%20Pages&logo=github)](https://github.com/aicologne/aic-hardware-deals/deployments)
[![Last scan](https://img.shields.io/github/last-commit/aicologne/aic-hardware-deals?label=last%20scan)](https://github.com/aicologne/aic-hardware-deals/commits/main/LATEST.md)
[![License](https://img.shields.io/github/license/aicologne/aic-hardware-deals)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](ebay-search-skill/ebay_search.py)

A working deal-hunting kit for buying used/refurbished hardware (headless mini PCs, ≥16 GB VRAM GPUs for local AI, DDR4/DDR5 RAM) **to resell**. It combines:

- **Live market data** from eBay.de via the official Browse API (with a sandbox-friendly HTTP relay),
- **A five-shop review** of German used-hardware dealers (serverando, servershop24, serverschmiede, servermall, plusedv),
- **A Kleinanzeigen playbook** (alerts, testing, negotiation, scam flags) tuned to the current 2026 DRAM-shortage market,
- **Working Python tooling** (`ebay-search-skill/`) that you can run in two minutes.

> ⚠️ Prices are **snapshots** (probed 2026-08-14 and via archived captures). The market is moving fast — treat this as a methodology and a starting point, not a price list. Always verify live before buying.

---

## Repository contents

| File | What it is |
|---|---|
| [`LATEST.md`](LATEST.md) | **The final price report** — regenerated every night by the workflow (deal highlights, per-category medians, buy-low flags) |
| [`ebay_deals.csv`](ebay_deals.csv) | Raw scan output (21 queries, EUR/used, client-side filtered) |
| [`build_plan_2x3090.md`](build_plan_2x3090.md) | Detailed build plan for the 2× RTX 3090 AI tower (DDR4/DDR5 paths, server question, sourcing matrix) |
| [`build_parts_matrix.md`](build_parts_matrix.md) | **4 build configurations** — platform (DDR4/X99 vs DDR5/AM5) × GPU generation (newer RTX vs. older Quadro), all priced from live scans |
| [`kleinanzeigen_playbook.md`](kleinanzeigen_playbook.md) | The full Kleinanzeigen strategy: 25+ search alerts, test protocols, negotiation script, scam flags |
| `ebay-search-skill/` | Working tooling: Browse API scanner, local relay, report renderer, skill docs |
| `.github/workflows/ebay-scan.yml` | Nightly scan → report → GitHub Pages deployment |
| [`ebay.env.example`](ebay.env.example) | Credentials template (never commit the real `ebay.env`) |
| [`SETUP.md`](SETUP.md) | Step-by-step GitHub + Pages setup (this repo, ready to publish) |

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
| `ebay_search.py` | CLI scanner: 21 default queries (GPUs ≥16 GB incl. Quadro RTX, 8th-gen mini PCs, DDR4/DDR5 RAM, AI hardware — DGX Spark / Strix Halo, whole gaming PCs, X99 build parts), realm auto-detection (sandbox vs production), correct filter syntax, client-side EUR/price/condition enforcement, `--demo`/`--debug`/`--relay` modes, CSV output |
| `ebay_relay.py` | Local HTTP relay (127.0.0.1 only) that forwards to eBay's HTTPS API — enables live scans from network-restricted environments (e.g., a DSH sandbox that blocks outbound HTTPS but allows loopback HTTP) |
| `SKILL.md` | The same knowledge packaged as a [DeepSeek Harness](https://github.com/deepseek-ai) skill — plain Markdown instructions, usable standalone too |

### What the scanner knows (hard-won lessons, all verified against the [Browse API spec](https://developer.ebay.com/api-docs/master/buy/browse/openapi/3/buy_browse_v1_oas3.yaml))

- **Marketplace is a header, not a query param**: `X-EBAY-C-MARKETPLACE-ID: EBAY_DE` (a `marketplace_ids` query param is silently ignored → results fall back to `EBAY_US`/USD).
- **`price` requires `priceCurrency`** (API error 12012).
- **Condition values take curly braces**: `conditions:{USED}`.
- **Use category IDs to kill keyword noise** ("RTX 3090" otherwise matches an iPhone *A3090*): `27386` Grafik-/Videokarten, `171957` Desktops & All-in-One-PCs, `170083` Arbeitsspeicher (RAM), `11210` Server-Speicher (RAM) — fetched live from the eBay.de Taxonomy API.
- eBay **silently ignores malformed params** — so the scanner also enforces the deal window client-side and reports dropped items.

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

## Automated nightly scans (GitHub Actions)

The repo ships `.github/workflows/ebay-scan.yml`:

- **Runs daily at 05:00 UTC** (`schedule` cron — GitHub Actions cron is UTC) plus a manual **Run workflow** button (`workflow_dispatch`).
- Executes `ebay_search.py` with credentials injected from **GitHub secrets** (never stored in the repo), then renders **`LATEST.md`** — a readable report grouped by query, price-sorted, with clickable listing links — and commits `ebay_deals.csv` + `LATEST.md` back to the repo.
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

## The report (`LATEST.md`) — the final product

Every nightly run commits `ebay_deals.csv` and renders **`LATEST.md`** — a self-contained price report with:

- 🔥 **Deal highlights** — listings currently at or within 15 % of the buy-low target (the shortlist to inspect first)
- Per-category sections with the **deal window, median, cheapest item**, and per-listing notes (`🔥 at/near buy-low` / `⚠️ above scan window`)
- Market context, methodology, and a fees disclaimer

The workflow also builds `site/index.html` from it and deploys it to **GitHub Pages**, so the report is readable as a web page — not just as a CSV dump.

---

## Methodology & data quality (read before trusting any number)

- **eBay.de prices**: live Browse API probes (production keyset), category-restricted, used + EUR enforced both server- and client-side.
- **Shop prices**: mostly **archived snapshots** (Wayback Machine) because the research sandbox cannot fetch HTTPS directly — every price carries its capture date, and several (e.g., servershop24 DDR5) are *pre-shortage* and almost certainly stale. **Verify live**.
- **Kleinanzeigen**: no public API; prices come from real ads + market-tracker anchors, not systematic scraping.
- **Absence ≠ absence**: serverschmiede/plusedv catalogs are barely indexable — "not found" means "verify manually", not "doesn't exist".
- The Browse API exposes **active listings only** — no sold-price history (use eBay.de's "Verkauft" filter or Terapeak for that).

---

## Ideas for the next iteration

- [x] **Scheduled nightly scan** (GitHub Actions) that commits fresh `ebay_deals.csv` + rendered `LATEST.md`
- [x] **LATEST.md as the final price report** — deal highlights, per-category medians/windows, buy-low flags; deployed to **GitHub Pages** as `site/index.html`
- [ ] Telegram/e-mail notification when a listing hits the buy-low window (e.g., a workflow step comparing against thresholds)
- [ ] Margin column (subtract ~13 % eBay fees per hit)
- [ ] Sold-price tracking via Terapeak / third-party data for true resale anchors
- [ ] Multi-marketplace mode (EBAY_AT, EBAY_CH, EBAY_NL) via the header

---

## License & disclaimer

MIT (see [LICENSE](LICENSE)). Prices and market conditions change constantly; this repository is research and tooling, **not financial advice**. Always verify condition, warranty, and current prices before buying. Respect the terms of service of eBay, eBay Kleinanzeigen, and the shops involved — and never publish your API credentials (`ebay.env` is gitignored for a reason).
