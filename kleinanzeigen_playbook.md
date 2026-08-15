# Kleinanzeigen Playbook — Hardware Reselling (DE)

Target categories: GPUs ≥16 GB VRAM (AI), 8th-gen+ mini PCs (headless), DDR4/DDR5 RAM.
Strategy: **buy 10–30 % below refurb-shop / eBay.de prices from private sellers, resell at market**.
All prices in EUR; **refresh anchors weekly with the ebay-search skill** (see §7).

---

## 0. Market snapshot — live eBay.de probe (2026-08-14, via ebay-search skill)

Hard data from a live Browse API scan (used, EUR, eBay.de):

| Item | eBay.de asking (used) | Meaning for Kleinanzeigen |
|---|---|---|
| RTX 3090 24 GB | **€1000–1500** (cheapest full card €1000 ex-mining watercooled; typical air-cooled €1149–1500; FE €1400; one with 12-month warranty €1399.90) | Old "buy ≤750" window is **obsolete** — the DRAM-shortage spike pushed used prices up hard. Private sellers lag the market 15–30 %: a 3090 at **€800–1000** on Kleinanzeigen is now a real flip. |
| RTX 3090 Ti | €1450 (FE) | Buy ≤€1200 |
| RAM (DDR4 RDIMM) | Shops ask €219–230 for 32 GB (serverando) | Kleinanzeigen private stock at €60–120 = the widest arbitrage window in this list |

Re-verify before every buying round: `python .dsh\skills\ebay-search\ebay_search.py --relay http://127.0.0.1:8787` (see §7).

---

## 1. Search alerts ("Suchaufträge")

How to set: Kleinanzeigen app → search → set filters → **"Suchauftrag speichern"** → enable **push notifications + email**. Set **sort = neueste zuerst** and **radius 100–150 km** (bigger for RAM lots/GPU deals — shipping a GPU is fine, mini PCs better locally).

Run **one alert per keyword** — never combine brands/sizes in one alert, you'll drown in noise.

### A) GPUs (≥16 GB VRAM) — ranges updated for the 2026 market
| Alert keyword | Price filter | Notes |
|---|---|---|
| `RTX 3090` | **750–1150** | buy-low target ≤€1000; resell €1250–1500 on eBay.de |
| `RTX 3090 Ti` | **850–1250** | FE resells ~€1450 |
| `RTX 4070 Ti Super` | 700–1000 | verify with scanner; 16 GB sweet spot |
| `RTX 4080 Super` | 800–1100 | verify with scanner |
| `Tesla P40` | 100–200 | budget novelty play, unchanged |
| `RTX A5000` / `RTX 5000 Ada` | 800–1300 / 1800–2400 | niche pro market |
| `Quadro RTX` | 400–1000 | **AI value pick** (live 2026-08): RTX 5000 16 GB €450–500, RTX 6000 24 GB €799–840 — 24 GB cheaper than a used 3090; Turing gen (no bf16) but ECC GDDR6, blower/passive, workstation-proven |

Optional: add `-defekt -Tausch` as negative terms if you don't want repair projects (or *do* want them — a fixable "defekt" 3090 is often 40 % off).

### A2) AI hardware (new wave — hot, thin supply, high margins)
| Alert keyword | Price filter | Notes |
|---|---|---|
| `DGX Spark` | 1800–3200 | Nvidia's compact AI box (GB10, 128 GB); **no used market on eBay.de yet** (2026-08) — be early: private first-wave sellers underprice; resell potential €2800+ |
| `Ryzen AI Max 395` / `Strix Halo` | **900–2000** | ⚠️ **new anchor: BOSGAME M5 128 GB ≈ €1581–1700** ([€1581 EU promo](https://news.miracleplus.com/share_link/94219), [$1699 US](https://www.tweaktown.com/news/105448/check-out-bosgames-new-monster-mini-pc-powered-by-amds-strix-halo-apu-costs-1699/index.html)). Used listings at €2340–4625 are **mostly ABOVE new** — only premium brands (HP Z2 Mini/ZBook, ASUS ROG Flow Z13) with warranty justify those prices. **Buy used only below ~€1400–1500, or buy new BOSGAME directly.** |
| `BOSGAME M5` | 700–1500 | resold units; deal only well under the €1581 new price |

> These are premium AI devices: verify thoroughly (memory size, BIOS, warranty) and expect slow turnover — buyers are few but willing to pay. Watch the new-price anchors: a used price above the current new price is never a deal.

### A3) Whole gaming PCs & build parts (the value flips — live data 2026-08)
| Alert keyword | Price filter | Notes |
|---|---|---|
| `Gaming PC RTX 3090` | 1200–2200 | **the killer play**: whole PCs observed €1600–2600, GPU alone worth €1000–1500 → keep GPU, flip the rest for €300–500 |
| `Gaming PC RTX 3080` | 600–1100 | budget whole-PC flips (observed €710–950: FE+3600, 10850K, 9900K+3080 Ti) |
| `X99 Mainboard` | 30–120 | AI-tower base; working ASUS Z10PA-U8 (C612, 8× DDR4) seen at €52–54 |
| `Xeon E5-2690v4` | 10–50 | 14-core 2011-3 CPU, seen at €14–30 — pairs with RDIMM arbitrage |
| `128GB DDR4` / `4x32GB` | 240–480 | kit buys for the tower (vs. €219–230/module in shops) |

> Buying a whole 3090 PC is usually cheaper per component than assembling — GPU-cost-to-zero strategy, see `build_plan_2x3090.md`.

### B) Mini PCs (8th gen+ only — skip 6th/7th gen, slow resale)
| Alert keyword | Price filter | Notes |
|---|---|---|
| `EliteDesk 800 G4 Mini` | 80–180 | i5-8400T/8500T = the sweet spot |
| `EliteDesk 800 G5 Mini` | 100–200 | |
| `OptiPlex 3070 Micro` | 80–180 | |
| `OptiPlex 3080 Micro` | 100–200 | |
| `ThinkCentre M720q` | 80–180 | |
| `ThinkCentre M920q` | 100–200 | dual NVMe, most wanted Tiny |
| `ProDesk 600 G5 Mini` | 90–190 | |

Generic fallbacks: `Mini PC i5`, `Mini PC i7`, `USFF i5`.

### C) RAM (the arbitrage play — widest window right now)
| Alert keyword | Price filter | Notes |
|---|---|---|
| `DDR4 RDIMM 32GB` | 40–120 | **#1 target** — shops ask 219–230 € (serverando) |
| `DDR4 RDIMM 64GB` | 80–200 | |
| `ECC Server RAM` | 30–200 | catches mixed lots |
| `DDR5 32GB` | 60–150 | incl. SODIMM, sealed is gold |
| `DDR4 32GB` | 30–100 | UDIMM/SODIMM |
| `16GB DDR4` | 10–40 | volume SODIMM |

### D) Bulk / lots (best margins)
`Server RAM Konvolut`, `DDR4 Palettenware`, `PC Auflösung`, `Firmenauflösung IT`, `Mini PC Konvolut`, `Grafikkarten Konvolut`, `Server Auflösung`.

---

## 2. Buying checklist (test before you pay — private sales are "wie gesehen", no returns)

### Mini PC (5 min on the spot)
1. **Power supply**: original HP/Dell/Lenovo brick included? (proprietary connectors — replacing costs 15–30 €, negotiate it in).
2. **BIOS/security**: boot to BIOS — any **BIOS password**? Check for **Computrace/Absolute LoJack** (stolen-enterprise red flag).
3. **Boot test**: USB stick with a Linux live ISO (or Hiren's). Verify CPU (`lscpu`), RAM (`dmidecode -t memory`), disk SMART (`smartctl -a /dev/sda` — check hours + reallocated sectors).
4. **Stability**: 2–3 min `stress` loop; check `sensors` temps (idle < 40 °C, load < 90 °C).
5. **Ask**: invoice available? from office liquidation or private? hours of use?

### GPU (10 min on the spot)
1. **Visual**: dust/oil residue (mining), reball/repair marks, stickers intact, box present.
2. **Ask directly**: *"Karte aus Mining oder Gaming? Aus einem Server?"* — blower-style 3090s are usually ex-rig.
3. **GPU-Z**: verify **VRAM = official spec** (24 GB). **Beware Chinese BIOS-modded "32 GB RTX 4080" / "48 GB RTX 4090" cards** — resale poison, refuse.
4. **Stress**: FurMark/OCCT 10–15 min — no artifacts, hotspot ≤ 105 °C on 3090.
5. **Serial check**: some brands (EVGA historically) transfer warranty — 30 sec online check can add 50–100 € value.
6. **Power**: bring a known-good 850 W+ PSU if testing away from home.

### RAM
- **On the spot**: visual (chips intact, no burn marks), ask "getestet?"
- **At home, immediately**: memtest86 (PassMark) full pass per stick, or RST Pro for lots. Untested lots = buy at a discount, test, sell tested for a premium.
- Check rank/ECC via CPU-Z: 2Rx4 32 GB RDIMMs are the most liquid spec.

---

## 3. Negotiation script (German)

```
Hallo, ist der Artikel noch verfügbar? Ich kann heute/morgen bar abholen.

[after confirmation]
Ich biete <X € — 20–30 % unter dem Preis>. Bei Barzahlung und Abholung, ohne Versand.

[pushback]
Ich verstehe. Bei dem aktuellen Marktpreis / wegen der kleinen Macke
gehe ich auf <X+5 €>. Sonst muss ich leider passen.

[closing]
Okay, machen wir <X €> bar bei Abholung. Können Sie mir kurz ein
aktuelles Foto mit heutigem Datum schicken?
```

- **Lots**: *"Wenn Sie mir einen Paketpreis für alles machen, nehme ich das komplette Konvolut ab."* (bulk discount 20–30 % is normal).
- **"Tausche" ads**: offer cash at 60–70 % of their trade value.
- Always counter-offer once even if the price is already good — 5 % free margin.

---

## 4. Scam red flags (non-negotiable rules)

1. **Seller refuses pickup, insists on shipping** → stop.
2. **Advance payment / "Anzahlung" / deposit** to "reserve" the item → scam.
3. **Fake payment confirmations** ("Geld ist unterwegs, bitte versenden") → scam.
4. **Payment links** — PayPal "Freunde", odd URLs, fake "Sicher bezahlen" pages → scam.
5. **Too-good price + new account + stock photos** → scam.
6. **Foreign sellers** (UK/CH/PL claiming to ship) for high-value items → treat as scam until proven.
7. **Enterprise gear with Computrace/BIOS lock** → walk away unless you know how to handle it.
8. **No original PSU** on mini PCs (proprietary) — factor 15–30 € into your offer.
9. Meeting: **daytime, public place, bring someone**, pay only after testing, **cash or "Sicher bezahlen"**.

---

## 5. Selling tips (free listings = full margin)

- Photos: bright, serial visible, **screenshots of test results** (GPU-Z, memtest pass, SMART) — builds trust and justifies a premium.
- Price "VB" ~10 % above your target; accept 10 % off.
- **Channel choice matters now**: for GPUs, eBay.de currently pays more than Kleinanzeigen (3090s at €1250–1500 on eBay vs. €1100–1300 private) — but eBay takes ~13 % + payment fees, so compare net after fees.
- Ship with insurance + tracking only via "Sicher bezahlen" or bank transfer; prefer pickup/cash.
- RAM lots: sell tested sticks individually (2–3 × lot price) or as 4×8/2×16 kits.

---

## 6. Sample margin math (current market)

| Play | Buy (Kleinanzeigen) | Sell (eBay.de) | Gross | Fees ~13 % + ship | Net |
|---|---|---|---|---|---|
| RTX 3090 air-cooled | €900 | €1350 | €450 | ~€190 | **~€260** |
| RTX 3090 ex-mining watercooled | €800 | €1200 | €400 | ~€170 | **~€230** |
| 32 GB DDR4 RDIMM (private lot) | €70 | €180 (shops/retail) | €110 | low (private/kit) | **~€90–110** |
| EliteDesk 800 G4 Mini bare + 16 GB/512 GB | €130 | €220 (configured) | €90 | ~€30 | **~€60** |

---

## 7. Refresh price anchors (weekly, 2 minutes)

Live eBay.de anchors via the ebay-search skill:

```powershell
# terminal 1 (persistent): start the local relay
python .dsh\skills\ebay-search\ebay_relay.py

# terminal 2 (or ask the agent): run the default 15-query scan through the relay
python .dsh\skills\ebay-search\ebay_search.py --relay http://127.0.0.1:8787
```

- The scanner enforces EUR/price/condition client-side and writes `ebay_deals.csv`.
- Sanity-check: `--demo` runs offline; `--debug` prints the exact request URL and response totals.
- Also check [whereismyram DE](https://whereismyram.com/de/price-chart) for RAM and eBay.de "Verkauft" for true sold prices.
