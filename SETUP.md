# GitHub + GitHub Pages Setup-Anleitung

In 10 Minuten läuft dein nächtlicher eBay-Preis-Report als öffentliche Webseite.
Alles in diesem Ordner (`publish/`) ist bereit zum Pushen — **außer deine echten Zugangsdaten, die wandern in GitHub-Secrets.**

---

## 1. Repository auf GitHub erstellen

**Web-UI** ([github.com/new](https://github.com/new)):
- Repository-Name: **`aic-hardware-deals`** (dein Profil: `aicologne`)
- Description: `Nightly eBay.de used-hardware price report + reseller playbook (Browse API)`
- Topics (optional): `ebay-api`, `browse-api`, `used-hardware`, `reselling`, `ai-hardware`, `german`
- **Nichts anklicken** (kein README/`.gitignore`/License generieren — alles liegt schon bereit)
- → **Create repository**

**Oder per CLI** (falls `gh` installiert):
```powershell
gh repo create aic-hardware-deals --public --source . --push
```

## 2. Lokale Dateien pushen

```powershell
cd E:\Development\ai_buying\publish
git init
git add .
git commit -m "eBay deal-hunting kit: scanner, relay, playbook, nightly Pages report"
git branch -M main
git remote add origin https://github.com/<DEIN-USERNAME>/<REPO-NAME>.git
git push -u origin main
```

> ✅ `ebay.env` ist per `.gitignore` ausgeschlossen — es kann **nicht** mitgepusht werden. Kontrolle: `git status` zeigt nur die gewollten Dateien, `git ls-files` listet keine Secrets.

## 3. Secrets hinzufügen (die Produktions-Keys)

1. Repo → **Settings → Secrets and variables → Actions → New repository secret**
2. Zwei Secrets anlegen:

| Name | Wert |
|---|---|
| `EBAY_CLIENT_ID` | deine **Production** Client ID (enthält `-PRD-` oder ohne `-SBX-`) |
| `EBAY_CLIENT_SECRET` | deine **Production** Client Secret |

> ⚠️ **Nur Production funktioniert.** Sandbox-Keys (`-SBX-` / `SBX-…`) liefern Testdaten und einen irreführenden Report. Die Werte findest du unter [developer.ebay.com](https://developer.ebay.com) → dein App → **Application Keys → Production**.

## 4. GitHub Pages aktivieren (einmalig, 2 Klicks)

1. Repo → **Settings → Pages**
2. **Source: "GitHub Actions"** auswählen (nicht "Deploy from a branch"!)
3. Fertig — die URL lautet: `https://<DEIN-USERNAME>.github.io/<REPO-NAME>/`

## 5. Ersten Workflow-Run starten

1. Repo → **Actions** → **"eBay deal scan (nightly)"** (links)
2. Rechts → **Run workflow** → grünen Button klicken
3. Ablauf (≈2–3 Min.): Scan (21 Queries) → `LATEST.md` rendern → `ebay_deals.csv` in `site/data/` veröffentlichen → **Commit + Push** → **Pages-Deploy**
4. Fertig: Der Report liegt als
   - **Datei:** `LATEST.md` im Repo
   - **Webseite:** `https://<DEIN-USERNAME>.github.io/<REPO-NAME>/` (die Seite liest ihre Daten zur Laufzeit aus `data/ebay_deals.csv`)

## 6. Verifizieren

- [ ] `Actions` zeigt grüne Häkchen (scan + deploy)
- [ ] Im Repo liegt ein frischer Commit `chore: refresh eBay price report (YYYY-MM-DD)`
- [ ] `LATEST.md` enthält 🔥-Highlights
- [ ] Die Pages-URL lädt (erstmal kann 1–2 Min. dauern, Cache leeren mit Strg+F5)

---

## Troubleshooting

| Problem | Ursache | Lösung |
|---|---|---|
| Workflow-Run `scan` schlägt fehl | Secrets fehlen/falsch | Settings → Secrets prüfen; Production-Keyset verwenden |
| Fehler `401 Unauthorized` | Sandbox-/Production-Mix oder falsches Secret | Keyset-Paarung prüfen (ID + Secret aus **derselben** Umgebung) |
| `LATEST.md` zeigt 0 Treffer | Deal-Fenster aktuell leer (z. B. 3090 unter €750) | Normal — Fenster in `ebay-search-skill/ebay_search.py` anpassen |
| Pages-Deploy fehlt / alte Seite | Source nicht auf "GitHub Actions" | Settings → Pages → Source: GitHub Actions |
| Seite zeigt alten Stand | Cache | Strg+F5; Deploy-Lauf in Actions abwarten |
| Seite zeigt „Could not load the report data“ | `site/data/ebay_deals.csv` fehlt (noch kein Run) oder Datei direkt per `file://` geöffnet | Datei lokal per HTTP-Server öffnen (siehe unten); nach dem ersten Workflow-Run liegt die CSV automatisch in `site/data/` |
| Kein Run um 05:00 UTC | Cron-Wiederholung pausiert nach 60 Tagen Inaktivität | Einmal manuell `Run workflow` — danach läuft der Cron wieder |

## Optionen (optional)

- **Nächtlicher Rhythmus:** Workflow cront `0 5 * * *` UTC (~07:00 MEZ / 09:00 MESZ). Frequenz in `.github/workflows/ebay-scan.yml` änderbar (z. B. `0 */6 * * *` = alle 6 h).
- **Status-Badges** sind bereits oben in der README eingebaut und auf `aicologne/aic-hardware-deals` vorbefüllt:
  - **Nightly scan** — Workflow-Status (leuchtet nach dem ersten Run)
  - **GitHub Pages** — Deploy-Status der Webseite
  - **Last scan** — Datum des letzten Commits von `LATEST.md` (≈ letzter Scan)
  - **License / Python** — statisch, funktionieren sofort
- **Report in der README verlinken:** `[Aktueller Report](LATEST.md)` — GitHub rendert ihn direkt im Repo.

- **Lokal testen:** Die Seite liest ihre Daten client-seitig aus `data/ebay_deals.csv` — `file://` blockiert das. Also mit HTTP-Server im Repo-Ordner testen:
  ```powershell
  cd E:\Development\ai_buying\publish
  python -m http.server 8000
  # dann im Browser: http://localhost:8000/site/
  ```

## Besucher-Tracking (optional, GoatCounter)

Die Seite enthält bereits den GoatCounter-Snippet — kostenlos, cookieless und DSGVO-freundlich (kein Consent-Banner nötig). Einrichten in 2 Minuten:

1. Konto anlegen unter [goatcounter.com](https://www.goatcounter.com) (Free-Tier reicht).
2. Dort deinen **Site-Code** kopieren, z. B. `meinedeals` (bzw. die komplette URL `https://meinedeals.goatcounter.com/count`).
3. In `site/index.html` die Zeile anpassen:
   ```html
   <script data-goatcounter="https://meinedeals.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
   ```
   → `YOURSITE` durch deinen Site-Code ersetzen, den Rest stehen lassen, committen & pushen.
4. Fertig: Jeder Seitenaufruf wird gezählt; Dashboard unter `https://meinedeals.goatcounter.com`. Sobald konfiguriert, erscheint im Seitenfuß automatisch ein Link „Visitor stats (GoatCounter)“.

> Solange der Platzhalter `YOURSITE` drinsteht, wird **nichts** getrackt — der Snippet ist dann inaktiv.

## Sicherheit

- `ebay.env` (mit deinen Secrets) gehört **nur** auf deinen Rechner — nie pushen.
- Secrets in GitHub Actions sind verschlüsselt und nur in Logs *redigiert* sichtbar — Logs nie vollständig teilen.
- GitHub-Actions-Runner haben vollen HTTPS-Zugriff — der Workflow nutzt den Scanner **direkt**, der lokale Relay (`ebay_relay.py`) ist nur für Sandbox/offline-Umgebungen.
