# 📖 Glossary — used AI hardware, plain language (EN / DE)

New to used AI-hardware hunting? Start here. Terms are explained in English and
German; everything else in the repo assumes you know these.

| Term | What it means (EN) | Was es bedeutet (DE) |
|---|---|---|
| **RDIMM** | Registered server RAM with ECC. Cheap and abundant used; fits X99/EPYC/server boards, **not** normal desktop motherboards. | Registrierter Server-RAM mit ECC. Gebraucht günstig und reichlich; passt in X99/EPYC/Server-Boards, **nicht** in normale Desktop-Mainboards. |
| **UDIMM** | Unbuffered (normal) desktop RAM. | Ungepufferter (normaler) Desktop-RAM. |
| **ECC** | Error-correcting memory; catches single-bit errors — matters for long-running AI training/inference. | Fehlerkorrigierender Speicher; fängt Einzelbit-Fehler ab — wichtig bei langen AI-Training-/Inferenzläufen. |
| **VRAM** | GPU memory. The real bottleneck for local AI: 16 GB is the current comfort bar, 24 GB (RTX 3090/4090) much better. | Grafikspeicher der GPU. Der eigentliche Engpass bei lokaler AI: 16 GB ist die Komfortgrenze, 24 GB (RTX 3090/4090) deutlich besser. |
| **X99 / LGA2011-3** | Cheap used platform (Xeon E5-v4) with 8 RAM slots and 40 PCIe lanes — the budget AI-workstation path (see `build_plan_2x3090.md`). | Günstige Gebrauchtplattform (Xeon E5-v4) mit 8 RAM-Slots und 40 PCIe-Lanes — der Budget-Weg zur AI-Workstation (siehe `build_plan_2x3090.md`). |
| **Buy-low target** | The price window a category is scanned for. A listing at/within 15 % of it gets the 🔥 flag — the shortlist to inspect first. | Das Preisfenster, nach dem eine Kategorie gescannt wird. Ein Angebot am/ innerhalb von 15 % davon bekommt 🔥 — die Shortlist zuerst prüfen. |
| **€/GB** | Price ÷ capacity. The value metric for GPUs and RAM used in the report tables (e.g. €88 for a 32 GB RDIMM = €2,75/GB). | Preis ÷ Kapazität. Die Wert-Kennzahl für GPUs und RAM in den Report-Tabellen (z. B. €88 für 32-GB-RDIMM = €2,75/GB). |
| **Median** | The middle price of a category (not the average) — robust against a few crazy listings. | Der mittlere Preis einer Kategorie (nicht der Durchschnitt) — robust gegen einzelne Ausreißer. |
| **Index** | Mean of the per-category median changes vs. the previous scan; one number for "the used AI hardware market moved +X % this week". | Mittelwert der Median-Veränderungen aller Kategorien vs. vorheriger Scan; eine Zahl für „der Gebrauchtmarkt für AI-Hardware ist diese Woche um +X % gestiegen". |
| **Refurb / used** | Refurbished = professionally tested/repaired, often with warranty; used = as-is from the previous owner. Both are scanned here. | Refurbished = professionell getestet/repariert, oft mit Garantie; gebraucht = wie vom Vorbesitzer. Beides wird hier gescannt. |
| **GPU-Z / memtest86** | Free tools to verify a card/RAM stick before paying (BIOS-modded "32 GB RTX 4080" fakes are a known scam — see the Kleinanzeigen playbook). | Kostenlose Tools zum Prüfen von Karte/RAM vor dem Kauf (BIOS-modifizierte Fake-„32-GB-RTX-4080"-Karten sind ein bekannter Scam — siehe Kleinanzeigen-Playbook). |
| **Homelab** | Your own small server/PC setup at home (mini PCs are the classic entry point). | Eigene kleine Server-/PC-Umgebung zu Hause (Mini-PCs sind der klassische Einstieg). |
| **Marketplace** | Which eBay site the listing comes from (EBAY_DE = ebay.de, EBAY_AT = ebay.at, EBAY_GB = ebay.co.uk, …). | Welche eBay-Seite das Angebot kommt (EBAY_DE = ebay.de, EBAY_AT = ebay.at, EBAY_GB = ebay.co.uk, …). |

The site has a short version under the footer (📖 Glossary); this file is the
full reference. New terms get added here as the scan categories grow.
