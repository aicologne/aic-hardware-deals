# Build Plan: 2× RTX 3090 AI Workstation (Feintuning + Inferenz)

**Stand: 2026-08-15 — Preise aus Live-Scans (eBay.de Browse API), Kleinanzeigen-Markt und Shop-Recherche.**
Ziel: LoRA/QLoRA-Feintuning (7B–34B) + lokale Inferenz, CUDA/x86, resellbar. Budget: **~€2.400–3.000**.

---

## Der Kern: 2× RTX 3090

| Position | Empfehlung | Gebrauchtziel | Quellen (diskutierte Anbieter) |
|---|---|---|---|
| GPU 1 | RTX 3090 axial (EVGA FTW3 / MSI Suprim / ASUS Strix) | **≤ €1.000–1.100** | eBay.de €1.000–1.500 · Kleinanzeigen 750–1150 · **servershop24-GPU-Kategorie** (manueller Check, Garantie) |
| GPU 2 | RTX 3090, wenn möglich gleiche Serie | ≤ €1.000–1.100 | dito |
| Optionale Zusatz-GPU | **Tesla T4 16 GB (70 W, passiv)** für 24/7-Inferenz nebenbei | ~€700–850 | **serverschmiede.com** ~€821 (Konfigurator, Sep'25) |

> **Killer-Play:** Komplette **"Gaming PC mit RTX 3090"** kosten €1.600–2.600 — GPU allein €1.000–1.500 wert. PC kaufen → GPU behalten → Rest verkaufen → **GPU-Kosten nahe Null** (eBay + Kleinanzeigen).

## RAM: DDR4 **und** DDR5 — beide Wege, mit echten Zahlen

Der entscheidende Build-Faktor. Aktuelle Marktlage (2026-08, live gemessen):

| | **DDR4-Weg** (X99/X299 — empfohlen) | **DDR5-Weg** (AM5/B650, Ryzen 7000/9000) |
|---|---|---|
| Ausbau | 128 GB (4× 32 GB RDIMM) | 64 GB (2× 32 GB DIMM) — teuer, selten 128 GB |
| **eBay.de (gebraucht, live)** | **32-GB-RDIMM ab €42**, Median €86 | 16-GB-Module **€160–224**, 32-GB-SODIMM **€210** |
| **Kleinanzeigen (privat)** | **€60–120 / 32 GB** → 4× ≈ €240–480 | kaum Angebot; Besitzer wissen um den Wert |
| **serverando.de** (geprüft, Garantie) | 32-GB-DDR4-2666 RDIMM **€219–230** | — (keine DDR5-Module im Sortiment) |
| **servershop24.de** | DDR4-Server-RAM-Kategorie | **Transcend 32 GB DDR5: €99,99** (archiviert Aug'25, **vor** dem Spike — **Preis live prüfen!**) |
| Neupreis-Index | ~2× des Vorkrisen-Niveaus | **4,2–4,5× des Juli-2025-Niveaus** (DE-Index) |
| Kosten 64 GB | ~€120–240 | **€420–900+** |
| Kosten 128 GB | ~€240–480 | €900–1.800 (praktisch unsinnig) |

**Fazit:** Der **DDR4-Weg spart €300–1.000** gegenüber DDR5 bei gleicher oder höherer Kapazität. DDR5 lohnt nur, wenn du zwingend eine aktuelle Plattform (AM5) willst — dann budgetiere 64 GB ab €420 und halte Ausschau nach dem **servershop24-Archivpreis (€99,99/32 GB)** sowie eBay-Auktionen. Für die 2×3090-Last (GPU-VRAM ist der Flaschenhals, System-RAM nur Kontext/CPU) reicht DDR4-2666/2933 völlig.

## Plattform & Rest (X99-Pfad, empfohlen)

| Position | Empfehlung | Gebrauchtziel | Quellen |
|---|---|---|---|
| Mainboard | ASUS X99-A II / MSI X99 SLI PLUS / **ASUS Z10PA-U8** (C612, 8× DDR4) | **€40–120** | eBay ab €29 (defekt) / **€52–54 funktionierend (Z10PA-U8)** · serverando/servershop24 führen Server-Boards |
| CPU | **Xeon E5-2690v4** (14C/28T) oder E5-2680v4 | **€15–35** | eBay €14–30 · Kleinanzeigen · serverando (CPU-Kategorie) |
| CPU-Kühler | Noctua / be quiet! (135 W TDP) | €25–50 | eBay/Kleinanzeigen |
| Netzteil | **1000–1200 W ATX 3.0** | €80–140 | eBay/Kleinanzeigen; neu ab €140 (Retail) |
| Gehäuse | Tower mit Luftstrom (Fractal/Phanteks) | €40–90 | eBay/Kleinanzeigen |
| Storage | 1–2 TB NVMe (SSD-Preise steigen mit der DRAM-Krise) | €70–130 | eBay/Kleinanzeigen |
| NVLink (optional) | 2-Slot-Bridge | €50–160 | eBay (live €117–163 gesehen) |

**Gesamtsumme X99-Pfad: ~€2.400–3.000** · AM5/DDR5-Alternative: +€300–600 nur für den RAM-Unterschied.

## Anbieter-Matrix für den Build (alle diskutierten Quellen)

| Teil | eBay.de | Kleinanzeigen | serverando.de | servershop24.de | serverschmiede.com |
|---|---|---|---|---|---|
| 2× RTX 3090 | ✅ €1.000–1.500 | ✅ Ziel ≤€1.100 | ❌ | ⚠️ GPU-Kategorie (manuell) | ⚠️ nur T4 (~€821) |
| DDR4 RDIMM | ✅ **ab €42** | ✅ €60–120 | ✅ €219–230 (geprüft) | ✅ Kategorie | ⚠️ RAM-Konfigurator (CTO) |
| DDR5 | ✅ 16 GB €160–224 | ⚠️ selten | ❌ | ✅ **€99,99 archiviert (prüfen!)** | ⚠️ DDR5-Konfigurator |
| X99-Board | ✅ €29–120 | ✅ | ⚠️ Server-Boards | ⚠️ Server-Boards | ✅ (Server-Komponenten) |
| Xeon E5-v4 | ✅ €14–30 | ✅ | ✅ CPU-Kategorie | ⚠️ | ✅ (Server-Komponenten) |
| PSU/Case/SSD | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ |

**Regel:** eBay/Kleinanzeigen = Preis; serverando/servershop24 = **geprüfte Ware mit Garantie** (Aufpreis ok für kritische Teile wie RAM/Boards); serverschmiede = Server-Komponenten + T4.

## Solltest du in ein Server-Setup investieren?

**Nein — nicht als Hauptsystem.** X99-Tower liefert die Server-Vorteile (ECC-RDIMM günstig, 128 GB, 40 Lanes) bei Desktop-Lautstärke/-Strom und **flüssigem Wiederverkauf**; Rack-Server (4U) sind laut, stromhungrig und als Chassis die **langsamsten Verkäufer** im Homelab-Markt. Rack nur bei eigenem Raum + 24/7 + IPMI-Wunsch — dann gebrauchten 4U-Supermicro/Dell (€300–600) kaufen und die 3090er umziehen.
