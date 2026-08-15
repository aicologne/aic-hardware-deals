# Build-Parts-Matrix: 2× GPU AI-Workstation

**Stand: 2026-08-15 — alle Preise aus Live-Scans (eBay.de Browse API) bzw. Kleinanzeigen-/Shop-Recherche.**
Vier Konfigurationen: **Plattform (DDR4/X99 vs. DDR5/AM5) × GPU-Generation (neuere RTX vs. ältere Quadro).**

---

## GPU-Auswahl — neuere RTX vs. ältere Quadro (€/GB entscheidet)

| GPU | VRAM | Preis gebraucht (live) | €/GB | Gen | ECC | bf16 | Für Feintuning |
|---|---|---|---|---|---|---|---|
| **RTX 3090** | 24 GB | €1.000–1.500 | ~42–63 | Ampere | – | ✅ | ⭐ König (CUDA, schnell) |
| RTX 3090 Ti | 24 GB | ~€1.450 (FE) | ~60 | Ampere | – | ✅ | mehr Strom, wenig Mehrwert |
| RTX 4070 Ti Super | 16 GB | €783–850 | ~51 | Ada | – | ✅ | effizient, schnell, 16 GB |
| RTX 4080 Super | 16 GB | €820–920 | ~54 | Ada | – | ✅ | stark, 16 GB |
| **Quadro RTX 6000** | 24 GB | **€799–840** | **~34** | Turing | ✅ | – | ⭐ bester €/GB, ECC |
| Quadro RTX 5000 | 16 GB | **€432–500** | ~29 | Turing | ✅ | – | günstigster 16-GB-Einstieg |
| RTX A4000 | 16 GB | €819–999 | ~57 | Ampere | ✅ | ✅ | Workstation, Ampere |
| Tesla T4 | 16 GB | ~€821 (serverschmiede) | ~51 | Turing | ✅ | – | 70 W passiv, 24/7-Inferenz |

**Kernaussage:** Die **Quadro-RTX-6000 (24 GB, ECC) ist mit ~€34/GB der Preis-Leistungs-Sieger** — billiger pro VRAM-Gigabyte als jede 3090. Einschränkung: Turing-Generation (kein bf16, langsamere Tensor-Cores, kein Flash-Attention-Boost), Blower/passiv → braucht Luftstrom. Für QLoRA/Inferenz in FP16 völlig tauglich; für modernstes Feintuning (bf16) bleiben Ampere/Ada vorne.

---

## Plattform A: DDR4 / X99 (Server-Ebene im Tower)

| Teil | Empfehlung | Zielpreis | Quelle (live) |
|---|---|---|---|
| Board | ASUS Z10PA-U8 (C612, 8× DDR4) / X99-A II | €40–120 | eBay: **€52–54 funktionierend** |
| CPU | Xeon E5-2690v4 (14C/28T) | €15–35 | eBay: €14–30 |
| RAM | 128 GB RDIMM (4× 32 GB) | €240–480 | Kleinanzeigen €60–120/Modul; eBay ab €42 (Median €86) |
| Kühler | Noctua/be quiet! Tower | €25–50 | eBay |
| **Plattform-Summe** | | **~€350–650** | |

## Plattform B: DDR5 / AM5 (aktuelle Generation)

| Teil | Empfehlung | Zielpreis | Quelle (live) |
|---|---|---|---|
| CPU | Ryzen 9 9900X (12C/24T) | €295–350 | eBay: €295–350 |
| Board | ASUS PRIME B650M-K / MSI PRO B650M-B | €75–80 | eBay: €75–78 |
| RAM | 64 GB DDR5 (2× 32 GB UDIMM) | €420–500 | eBay: Kingston 2×32 4800 **€490**; 32 GB SODIMM €210 |
| Kühler | AM5-Tower-Kühler | €30–50 | eBay |
| **Plattform-Summe** | | **~€900–1.000** | |

> DDR5-Falle: 128 GB AM5 ≈ €1.000+ (Shortage). Wer >64 GB System-RAM will, muss DDR4 wählen.

---

## Die 4 Konfigurationen

### Konfig 1: DDR4/X99 + 2× RTX 3090 — ⭐ empfohlen (48 GB, CUDA, resellbar)
| Posten | Preis |
|---|---|
| 2× RTX 3090 | €2.000–2.400 |
| X99-Plattform inkl. 128 GB RDIMM | €350–650 |
| PSU 1000–1200 W ATX 3.0 | €80–140 |
| Case + 2 TB NVMe | €110–220 |
| **Summe** | **~€2.550–3.400** |

### Konfig 2: DDR4/X99 + 2× Quadro RTX 6000 — Budget-AI (48 GB ECC, billiger)
| Posten | Preis |
|---|---|
| 2× Quadro RTX 6000 (24 GB ECC) | €1.600–1.680 |
| X99-Plattform inkl. 128 GB RDIMM | €350–650 |
| PSU 850–1000 W | €70–120 |
| Case + 2 TB NVMe | €110–220 |
| **Summe** | **~€2.130–2.670** |

> 48 GB VRAM **günstiger als 2×3090** — aber Turing: kein bf16, Blower-Luftstrom nötig. Beste Wahl, wenn €/GB zählt und du in FP16 arbeitest.

### Konfig 3: DDR5/AM5 + RTX 4080 Super — aktuelle Plattform (16 GB)
| Posten | Preis |
|---|---|
| 1× RTX 4080 Super (16 GB) | €820–920 |
| AM5-Plattform inkl. 64 GB DDR5 | €900–1.000 |
| PSU 850–1000 W | €70–120 |
| Case + 2 TB NVMe | €110–220 |
| **Summe** | **~€1.900–2.260** |

> Upgrade-Pfad: 2. Karte später (2× 4080S = 32 GB, ~€1.700 GPU-Gesamt). 16-GB-Deckel pro Karte.

### Konfig 4: DDR5/AM5 + 2× Quadro RTX 6000 — Kombi (48 GB ECC, neue Plattform)
| Posten | Preis |
|---|---|
| 2× Quadro RTX 6000 | €1.600–1.680 |
| AM5-Plattform inkl. 64 GB DDR5 | €900–1.000 |
| PSU 850–1000 W | €70–120 |
| Case + 2 TB NVMe | €110–220 |
| **Summe** | **~€2.680–3.020** |

---

## Entscheidungsregel

| Priorität | Konfiguration |
|---|---|
| Feintuning-Performance + Resale-Wert (dein Profil) | **Konfig 1** (2×3090, CUDA, flüssig verkäuflich) |
| Max. VRAM pro Euro, FP16-Workloads | **Konfig 2** (2× Quadro RTX 6000) |
| Aktuelle Plattform + Upgrade-Pfad, 16-GB-Deckel ok | Konfig 3 (1× 4080S → später 2×) |
| Neue Plattform + 48 GB ECC | Konfig 4 |

**Anbieter-Regel (aus der Recherche):** eBay/Kleinanzeigen = Preis · serverando/servershop24 = geprüfte Ware mit Garantie (RAM/Boards) · serverschmiede = T4/Server-Teile · Gaming-PC-Käufe ("Gaming PC RTX 3090" ab €1.600) = GPU-Kosten-nahe-Null-Play.

*Detailplan mit Server-Frage und kompletten Quellen: siehe `build_plan_2x3090.md`.*
