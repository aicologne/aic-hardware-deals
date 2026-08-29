// app.js — client-side rendering for the eBay price report.
// Fetches the nightly-generated CSV (data/ebay_deals.csv), renders the deal
// highlights + per-category tables, builds the table of contents, applies the
// EN/DE language toggle, shows a 30-day median sparkline per category (from
// data/history.csv) with an expandable trend chart, an aggregate index and
// median movers, per-listing repricing notes (data/listing_history.csv), a
// dark-mode toggle, and interactive filters (search, marketplace, category,
// max price, sort).
//
// Override the data source anytime, e.g. for local testing:
//   ?csv=../ebay_deals.csv   -> app.js reads window.DEALS_CSV
import {
  toRows, toHistoryRows, toAnyRows, analyze, euro, flagFor, num, median, marketplaceOf,
  euroPerGb, historySeries, movers, indexPct, CAPACITY_GB,
} from './csv.js';

const CSV_URL = window.DEALS_CSV || 'data/ebay_deals.csv';
const DEALS_INDEX_URL = window.DEALS_INDEX || 'data/deals/index.json';
const DEALS_DIR = 'data/deals/';
const HISTORY_URL = window.DEALS_HISTORY || 'data/history.csv';
const LISTING_URL = window.DEALS_LISTING_HISTORY || 'data/listing_history.csv';

const $ = (sel, root = document) => root.querySelector(sel);

/** Fetch + read the full body under one hard timeout, so a stalled request
 *  (headers OR body stream) can never leave the page stuck on the loading
 *  spinner forever. Throws on timeout; aborts the underlying request. */
async function fetchWithTimeout(url, ms = 10000) {
  const ctrl = new AbortController();
  const timerId = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetch(url, { cache: 'no-cache', signal: ctrl.signal });
    const text = await res.text(); // body read is inside the timeout too
    return { res, text };
  } finally {
    clearTimeout(timerId);
  }
}

/** Load the deal rows. Preferred path: per-category chunks (data/deals/
 *  index.json + one small CSV per category) fetched IN PARALLEL, each with
 *  its own timeout, rendered as each chunk lands — a single stalled request
 *  can no longer blank the whole report. Falls back to one big CSV when the
 *  split files don't exist yet (older artifact, or ?csv= override). */
async function loadDeals() {
  // If the caller pinned a specific CSV, use it and nothing else.
  if (window.DEALS_CSV) {
    const { res, text } = await fetchWithTimeout(CSV_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${CSV_URL}`);
    return { rows: toRows(text), generated: formatGenerated(res) };
  }

  // Preferred: try the split manifest first.
  try {
    const idx = await fetchWithTimeout(DEALS_INDEX_URL, 5000);
    if (idx.res.ok) {
      const manifest = JSON.parse(idx.text);
      if (Array.isArray(manifest) && manifest.length) {
        const rows = [];
        let first = true;
        const chunks = manifest.map(entry =>
          fetchWithTimeout(DEALS_DIR + entry.file, 8000)
            .then(({ res, text }) => {
              if (!res.ok) return;
              const chunkRows = toRows(text);
              rows.push(...chunkRows);
              // progressive: render as soon as the first chunk lands
              if (first) { first = false; cachedRows = rows; renderReport(); }
            })
            .catch(() => {}) // one stuck chunk must not kill the report
        );
        await Promise.all(chunks); // all chunks are individually time-boxed
        if (rows.length) {
          cachedRows = rows;
          return { rows, generated: formatGenerated(idx.res) };
        }
      }
    }
  } catch (err) {
    // manifest missing/unreadable -> fall back to the single CSV
    console.warn('Per-category split not available, using single CSV:', err && err.message);
  }

  const { res, text } = await fetchWithTimeout(CSV_URL);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${CSV_URL}`);
  return { rows: toRows(text), generated: formatGenerated(res) };
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) {
    if (child == null) continue;
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

// --- i18n --------------------------------------------------------------
// Strings used by the UI; parts may be strings or { code: '...' } for inline
// <code> styling. Listing titles, conditions and the buy-low flags come from
// the data itself and are not translated (German listing text is the source).
const I18N = {
  en: {
    title: '🛒 eBay Used Hardware — Price Report',
    tagline: 'Nightly price intelligence for used AI hardware — GPUs ≥16 GB, server RAM, mini PCs and complete systems. Browse API · used · EUR.',
    heroBadge: 'Nightly scan · eBay.de · Used · EUR',
    navRss: 'RSS',
    navData: 'Data (CSV)',
    navGlossary: 'Glossary',
    navMethodology: 'Methodology',
    ctxLabel: 'Market context (2026):',
    ctxText: 'the DRAM/GDDR shortage keeps used prices elevated. Used RTX 3090s ask €1000–1500 on eBay.de; DDR5 German retail is ~4.2–4.5× its July-2025 level; DDR4 RDIMM shops ask €219–230 for 32 GB while private sellers still move pre-shortage stock at €60–120. Note the new-price anchors: a BOSGAME M5 (Strix Halo, 128 GB) costs €1581–1700 new — used Strix Halo above that is not a deal. Verify everything live — prices move weekly.',
    tocTitle: 'Contents',
    statusLoading: ['Loading deal data from ', { code: CSV_URL }, '…'],
    generated: (date, total, cats) => `Generated ${date} · ${total} items across ${cats} categories`,
    noDeals: 'No listings found in the latest scan.',
    dealHighlights: '🔥 Deal highlights',
    dealHighlightsIntro: 'Listings currently at or within 15 % of the buy-low target — the shortlist to inspect first:',
    noHighlights: 'No listings currently sit at the buy-low targets. Check back after the next nightly scan, or widen the windows in ebay_search.py.',
    thCategory: 'Category',
    thPrice: 'Price',
    thTarget: 'Buy-low target',
    thTitle: 'Title',
    thSeller: 'Seller',
    thCondition: 'Condition',
    thNote: 'Note',
    thEperGB: '€/GB',
    thMkt: 'Mkt',
    window: 'Window',
    median: 'median',
    cheapest: 'cheapest',
    atNearBuyLow: 'at/near buy-low',
    any: 'any',
    itemsWord: 'items',
    fSearch: 'Search',
    fSearchPlaceholder: 'Search title, seller, category…',
    fMarketplace: 'Marketplace',
    fCategory: 'Category',
    fAll: 'All',
    fMaxPrice: 'Max price (€)',
    fMaxPricePlaceholder: 'e.g. 100',
    fSort: 'Sort',
    fPriceAsc: 'Price ↑',
    fPriceDesc: 'Price ↓',
    fBestDeal: 'Best deal first',
    fBestGB: 'Best €/GB',
    fReset: 'Reset',
    fCount: (n, total) => `Showing ${n} of ${total} items`,
    fNoMatches: 'No items match the current filters.',
    moversTitle: '📈 Median movers (vs previous scan)',
    moversRisers: 'Risers',
    moversFallers: 'Fallers',
    moversLatest: 'Latest median',
    moversRef: 'Reference',
    moversChange: 'Change',
    indexLabel: 'index',
    sparklineAria: '30-day median trend',
    chartShow: 'Expand trend chart',
    chartHide: 'Hide trend chart',
    themeTitle: 'Toggle dark mode',
    methodologyTitle: 'Methodology & notes',
    m1: 'Prices are asking prices from active listings (used), collected by the Browse API.',
    m2: ['Buy-low targets are the scan windows configured in ', { code: 'ebay_search.py' }, '; a listing within 15 % of the target is flagged 🔥.'],
    m3: 'eBay seller fees (~13 %) and shipping are NOT included — subtract them from any margin estimate.',
    m4: "Condition and warranty are the seller's; always verify photos, GPU-Z/memtest results, and seller feedback before paying.",
    m5: '€/GB is price ÷ capacity of the scan category (e.g. 32 GB RDIMM, 24 GB RTX 3090); mixed-capacity categories show —.',
    footerTools: ['Tooling: ', { code: 'ebay-search-skill/' }, ' (Browse API scanner + local relay) · Categories: ', { code: '27386 GPUs · 171957 desktops · 170083 RAM · 11210 server RAM' }, ' · Generated by the nightly GitHub Actions workflow'],
    backTop: '↑ Back to top',
    rss: 'RSS feed',
    glossaryTitle: '📖 Glossary (quick start)',
    errTitle: 'Could not load the report data.',
    errorBody: [
      ['The page reads its listings from ', { code: CSV_URL }, ' (generated nightly by the GitHub Actions scan).'],
      ['If you opened this file directly via ', { code: 'file://' }, ', browsers block that fetch — serve the folder over HTTP instead, e.g. ', { code: 'python -m http.server' }, ' in the repo root, then open ', { code: 'http://localhost:8000/site/' }, '.'],
    ],
  },
  de: {
    title: '🛒 eBay Gebraucht-Hardware — Preisreport',
    tagline: 'Nächtliche Preisübersicht für gebrauchte KI-Hardware — GPUs ≥16 GB, Server-RAM, Mini-PCs und Komplettsysteme. Browse API · gebraucht · EUR.',
    heroBadge: 'Nächtlicher Scan · eBay.de · Gebraucht · EUR',
    navRss: 'RSS',
    navData: 'Daten (CSV)',
    navGlossary: 'Glossar',
    navMethodology: 'Methodik',
    ctxLabel: 'Marktkontext (2026):',
    ctxText: 'Die DRAM/GDDR-Knappheit hält die Gebrauchtpreise hoch: Gebrauchte RTX-3090-Karten kosten auf eBay.de €1.000–1.500; DDR5 im deutschen Handel liegt bei ~4,2–4,5× des Niveaus vom Juli 2025; DDR4-RDIMM-Shops verlangen €219–230 für 32 GB, während private Verkäufer Altbestand noch für €60–120 anbieten. Achtung Preisanker: Ein BOSGAME M5 (Strix Halo, 128 GB) kostet neu €1.581–1.700 — gebrauchtes Strix Halo darüber ist kein Deal. Alles live prüfen — die Preise bewegen sich wöchentlich.',
    tocTitle: 'Inhalt',
    statusLoading: ['Lade Angebotsdaten aus ', { code: CSV_URL }, '…'],
    generated: (date, total, cats) => `Erstellt ${date} · ${total} Artikel in ${cats} Kategorien`,
    noDeals: 'Im letzten Scan wurden keine Angebote gefunden.',
    dealHighlights: '🔥 Deal-Highlights',
    dealHighlightsIntro: 'Angebote, die aktuell am oder innerhalb von 15 % des Buy-Low-Ziels liegen — die Shortlist für den ersten Blick:',
    noHighlights: 'Aktuell liegt kein Angebot am Buy-Low-Ziel. Nach dem nächsten Nacht-Scan erneut prüfen oder die Fenster in ebay_search.py anpassen.',
    thCategory: 'Kategorie',
    thPrice: 'Preis',
    thTarget: 'Buy-Low-Ziel',
    thTitle: 'Titel',
    thSeller: 'Verkäufer',
    thCondition: 'Zustand',
    thNote: 'Hinweis',
    thEperGB: '€/GB',
    thMkt: 'MP',
    window: 'Fenster',
    median: 'Median',
    cheapest: 'Günstigstes',
    atNearBuyLow: 'am/im Buy-Low',
    any: 'beliebig',
    itemsWord: 'Artikel',
    fSearch: 'Suche',
    fSearchPlaceholder: 'Titel, Verkäufer, Kategorie suchen…',
    fMarketplace: 'Marktplatz',
    fCategory: 'Kategorie',
    fAll: 'Alle',
    fMaxPrice: 'Max. Preis (€)',
    fMaxPricePlaceholder: 'z. B. 100',
    fSort: 'Sortierung',
    fPriceAsc: 'Preis ↑',
    fPriceDesc: 'Preis ↓',
    fBestDeal: 'Beste Deals zuerst',
    fBestGB: 'Bestes €/GB',
    fReset: 'Zurücksetzen',
    fCount: (n, total) => `Zeige ${n} von ${total} Artikeln`,
    fNoMatches: 'Keine Artikel passen zu den aktuellen Filtern.',
    moversTitle: '📈 Median-Mover (vs. vorherigem Scan)',
    moversRisers: 'Steigerungen',
    moversFallers: 'Rückgänge',
    moversLatest: 'Aktueller Median',
    moversRef: 'Referenz',
    moversChange: 'Änderung',
    indexLabel: 'Index',
    sparklineAria: '30-Tage-Median-Trend',
    chartShow: 'Trenddiagramm einblenden',
    chartHide: 'Trenddiagramm ausblenden',
    themeTitle: 'Dunkelmodus umschalten',
    methodologyTitle: 'Methodik & Hinweise',
    m1: 'Preise sind Verkaufspreise aktiver Angebote (gebraucht), gesammelt über die Browse API.',
    m2: ['Buy-Low-Ziele sind die in ', { code: 'ebay_search.py' }, ' konfigurierten Scan-Fenster; ein Angebot innerhalb von 15 % des Ziels wird mit 🔥 markiert.'],
    m3: 'eBay-Verkäufergebühren (~13 %) und Versand sind NICHT enthalten — bei jeder Margenschätzung abziehen.',
    m4: 'Zustand und Garantie liegen beim Verkäufer; vor dem Kauf immer Fotos, GPU-Z/memtest-Ergebnisse und Verkäuferbewertungen prüfen.',
    m5: '€/GB ist Preis ÷ Kapazität der Scan-Kategorie (z. B. 32-GB-RDIMM, 24-GB-RTX-3090); gemischte Kategorien zeigen —.',
    footerTools: ['Werkzeug: ', { code: 'ebay-search-skill/' }, ' (Browse-API-Scanner + lokaler Relay) · Kategorien: ', { code: '27386 GPUs · 171957 Desktops · 170083 RAM · 11210 Server-RAM' }, ' · Erstellt vom nächtlichen GitHub-Actions-Workflow'],
    backTop: '↑ Nach oben',
    rss: 'RSS-Feed',
    glossaryTitle: '📖 Glossar (Schnellstart)',
    errTitle: 'Die Reportdaten konnten nicht geladen werden.',
    errorBody: [
      ['Die Seite liest ihre Angebote aus ', { code: CSV_URL }, ' (nächtlich vom GitHub-Actions-Scan erzeugt).'],
      ['Wenn du diese Datei direkt über ', { code: 'file://' }, ' geöffnet hast, blockiert der Browser den Abruf — den Ordner stattdessen über HTTP ausliefern, z. B. ', { code: 'python -m http.server' }, ' im Repo-Root, dann ', { code: 'http://localhost:8000/site/' }, ' öffnen.'],
    ],
  },
};

let lang = localStorage.getItem('lang') || (navigator.language && navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en');
let theme = localStorage.getItem('theme') ||
  (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
let cachedRows = null;   // last loaded deal rows, so the toggle can re-render
let lastGenerated = 'latest scan';
let lastError = null;
let tocObserver = null;  // one scrollspy observer at a time
let history = null;      // { compositeKey: [{date, median}] } from data/history.csv (null = unavailable)
let listingHistory = null; // { url: {first_price, first_seen, last_price} } (null = unavailable)
const filters = { search: '', marketplace: 'all', category: 'all', maxPrice: null, sort: 'price-asc' };

function t(key) {
  const value = (I18N[lang] || I18N.en)[key];
  return typeof value === 'function' ? value : value ?? I18N.en[key] ?? key;
}

/** Render an i18n "parts" array (strings + { code } objects) into nodes. */
function partsNodes(key) {
  const parts = (I18N[lang] || I18N.en)[key];
  const list = Array.isArray(parts) ? parts : [parts];
  return list.map(p => (typeof p === 'string' ? p : el('code', { text: p.code })));
}

function slugify(text, used) {
  const base = text.toLowerCase().normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'section';
  let id = base;
  let i = 2;
  while (used.has(id)) id = `${base}-${i++}`;
  used.add(id);
  return id;
}

function pctStr(v) {
  if (v == null || !Number.isFinite(v)) return '—';
  const sign = v > 0 ? '+' : '';
  return sign + v.toLocaleString('de-DE', { maximumFractionDigits: 1 }) + ' %';
}

function windowStr(wmin, wmax) {
  if (wmin == null) return t('any');
  const fmt = n => '€' + Math.round(n).toLocaleString('de-DE');
  return `${fmt(wmin)}–${fmt(wmax)}`;
}

function buildTable(headers, rows, cellFns, cls) {
  const t = el('table');
  const thead = el('thead', {}, el('tr', {}, ...headers.map(h => el('th', { text: h }))));
  const tbody = el('tbody');
  for (const r of rows) tbody.appendChild(el('tr', {}, ...cellFns.map(fn => fn(r))));
  t.append(thead, tbody);
  return el('div', { class: 'table-wrap' + (cls ? ' ' + cls : '') }, t);
}

function titleCell(r) {
  return el('td', { class: 'cell-title' }, el('a', { href: r.url || '#', target: '_blank', rel: 'noopener' }, r.title || '(no title)'));
}

function priceCell(r) {
  return el('td', { class: 'cell-price' }, el('strong', { text: euro(r.price) }));
}

function eurPerGbCell(r) {
  const v = euroPerGb(r.price, r.query);
  if (v == null) return el('td', { class: 'cell-gb', text: '—' });
  return el('td', { class: 'cell-gb', text: v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '/GB' });
}

function noteChips(r) {
  // Flag chips for notable listings; plain "ok" rows stay clean.
  const chips = [];
  const flag = flagFor(r);
  if (flag.includes('🔥')) chips.push(el('span', { class: 'chip chip-deal', text: flag }));
  else if (flag.includes('⚠️')) chips.push(el('span', { class: 'chip chip-above', text: flag }));
  const rp = repricedNote(r);
  if (rp) chips.push(el('span', { class: 'note-reprice', text: rp }));
  return el('td', { class: 'cell-note' }, ...chips);
}

function repricedNote(r) {
  if (!listingHistory) return '';
  const lh = listingHistory[r.url];
  if (!lh) return '';
  const first = num(lh.first_price);
  const last = num(lh.last_price);
  if (first == null || last == null || first === last) return '';
  return `was ${euro(first)} on ${lh.first_seen}`;
}

// --- filters ---------------------------------------------------------------

function filterActive() {
  return filters.search.trim() !== '' || filters.marketplace !== 'all' ||
    filters.category !== 'all' || filters.maxPrice != null;
}

function matchesFilter(r) {
  const q = filters.search.trim().toLowerCase();
  if (q) {
    const hay = `${r.title || ''} ${r.seller || ''} ${r.query || ''}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  if (filters.marketplace !== 'all' && marketplaceOf(r) !== filters.marketplace) return false;
  if (filters.category !== 'all' && r.query !== filters.category) return false;
  if (filters.maxPrice != null && num(r.price) != null && num(r.price) > filters.maxPrice) return false;
  return true;
}

function compareRows(a, b) {
  const pa = num(a.price);
  const pb = num(b.price);
  switch (filters.sort) {
    case 'price-desc':
      return (pb ?? 0) - (pa ?? 0);
    case 'deal': {
      const ra = num(a.win_min) ? (pa ?? Infinity) / num(a.win_min) : Infinity;
      const rb = num(b.win_min) ? (pb ?? Infinity) / num(b.win_min) : Infinity;
      return ra - rb;
    }
    case 'gb-asc': {
      const ga = euroPerGb(a.price, a.query);
      const gb = euroPerGb(b.price, b.query);
      return (ga ?? Infinity) - (gb ?? Infinity);
    }
    default: // price-asc
      return (pa ?? Infinity) - (pb ?? Infinity);
  }
}

function populateSelect(sel, values, allLabel) {
  const prev = sel.value;
  sel.textContent = '';
  sel.appendChild(el('option', { value: 'all' }, allLabel));
  for (const v of values) sel.appendChild(el('option', { value: v, text: v }));
  if (prev && [...sel.children].some(o => o.value === prev)) sel.value = prev;
  else sel.value = 'all';
}

function syncFilterInputs() {
  $('#f-search').value = filters.search;
  $('#f-marketplace').value = filters.marketplace;
  $('#f-category').value = filters.category;
  $('#f-maxprice').value = filters.maxPrice == null ? '' : String(filters.maxPrice);
  $('#f-sort').value = filters.sort;
}

// --- charts ----------------------------------------------------------------

function sparkline(series, key) {
  const values = series.map(p => p.median);
  if (values.length < 2) return null;
  const W = 140, H = 26, PAD = 3;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => {
    const x = PAD + (i * (W - 2 * PAD)) / (values.length - 1);
    const y = H - PAD - ((v - min) / span) * (H - 2 * PAD);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const title = series.map(p => `${p.date}: ${euro(p.median)}`).join(' · ');
  return el('svg', {
    width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: 'sparkline', role: 'img',
    'aria-label': t('sparklineAria'), 'data-key': key, tabindex: '0',
  },
  el('title', { text: title }),
  el('polyline', { points: pts, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }),
  );
}

function trendChart(series) {
  const values = series.map(p => p.median);
  const W = 620, H = 180, PAD = 24;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const xAt = i => PAD + (i * (W - 2 * PAD)) / Math.max(1, values.length - 1);
  const yAt = v => H - PAD - ((v - min) / span) * (H - 2 * PAD);
  const pts = values.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(' ');
  const grid = [0, 0.5, 1].map(f => {
    const y = H - PAD - f * (H - 2 * PAD);
    const val = min + f * span;
    return el('g', {},
      el('line', { x1: PAD, x2: W - PAD, y1: y.toFixed(1), y2: y.toFixed(1), stroke: 'var(--border-soft)', 'stroke-width': 1 }),
      el('text', { x: 2, y: (y + 4).toFixed(1), class: 'chart-label' }, euro(val)),
    );
  });
  const xLabels = series.map((p, i) =>
    el('text', { x: xAt(i).toFixed(1), y: H - 4, class: 'chart-label', 'text-anchor': 'middle' }, p.date.slice(5)));
  return el('svg', { width: '100%', height: H, viewBox: `0 0 ${W} ${H}`, class: 'trend-chart', role: 'img', 'aria-label': t('sparklineAria') },
    ...grid,
    el('polyline', { points: pts, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }),
    ...xLabels,
  );
}

// --- rendering ------------------------------------------------------------

function renderHighlights(flagged, container, single) {
  const h2 = el('h2', { id: 'deal-highlights' }, t('dealHighlights'));
  if (!flagged.length) {
    container.append(h2, el('p', {}, t('noHighlights')));
    return;
  }
  const headers = [t('thCategory'), t('thPrice'), t('thTarget'), t('thTitle'), t('thSeller'), t('thNote')];
  const cells = [
    r => el('td', { class: 'cell-cat', text: r.query }),
    priceCell,
    r => el('td', { class: 'cell-target', text: euro(r.win_min) }),
    titleCell,
    r => el('td', { class: 'cell-seller', text: r.seller }),
    noteChips,
  ];
  if (!single) {
    headers.unshift(t('thMkt'));
    cells.unshift(r => el('td', { class: 'cell-mkt', text: marketplaceOf(r) }));
  }
  container.append(
    h2,
    el('p', { class: 'section-intro' }, t('dealHighlightsIntro')),
    buildTable(headers, flagged, cells, 'table-highlights'),
  );
}

function renderMovers(mv, container, single) {
  const risers = mv.filter(m => m.delta > 0).slice(0, 5);
  const fallers = mv.filter(m => m.delta < 0).slice(0, 5);
  if (!risers.length && !fallers.length) return;
  const h2 = el('h2', { id: 'median-movers' }, t('moversTitle'));
  container.append(h2);
  const display = m => (single ? m.key.split(' · ').slice(1).join(' · ') : m.key);
  const tableFor = items => buildTable(
    [t('thCategory'), t('moversLatest'), t('moversRef'), t('moversChange')],
    items,
    [
      m => el('td', { text: display(m) }),
      m => el('td', { class: 'cell-price' }, el('strong', { text: euro(m.latest) })),
      m => el('td', { text: `${euro(m.ref)} (${m.refDate})` }),
      m => el('td', { class: 'cell-change' }, el('strong', { text: pctStr(m.delta) })),
    ],
    'table-movers',
  );
  if (risers.length) container.append(el('h3', { class: 'movers-risers', text: `▲ ${t('moversRisers')}` }), tableFor(risers));
  if (fallers.length) container.append(el('h3', { class: 'movers-fallers', text: `▼ ${t('moversFallers')}` }), tableFor(fallers));
}

function renderGroup(group, container, usedIds, single, hasCapacity) {
  const sec = el('section', { class: 'category' });
  const h2 = el('h2', { id: slugify(group.key, usedIds) }, `${group.display} (${group.count} ${t('itemsWord')})`);
  const spark = history && history[group.key] ? sparkline(history[group.key], group.key) : null;
  const summary = el('p', { class: 'summary' }, el('em', {},
    t('window'), ' ',
    windowStr(group.wmin, group.wmax),
    ' · ', t('median'), ' ',
    el('strong', { text: euro(group.median) }),
    ' · ', t('cheapest'), ' ',
    el('strong', { text: euro(group.cheapest.price) }),
    ` · ${group.atTargetCount} ${t('atNearBuyLow')}`,
  ));
  sec.append(h2, summary);
  if (spark) {
    const detail = el('div', { class: 'trend-detail', hidden: true });
    const toggle = () => {
      const willShow = detail.hidden;
      detail.hidden = !willShow;
      if (willShow) {
        detail.textContent = '';
        detail.appendChild(trendChart(history[group.key]));
      }
      spark.setAttribute('aria-label', willShow ? t('chartHide') : t('chartShow'));
    };
    spark.addEventListener('click', toggle);
    spark.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    sec.append(el('p', { class: 'summary' }, spark), detail);
  }
  const headers = [t('thPrice'), t('thCondition'), t('thTitle'), t('thSeller'), t('thNote')];
  const cells = [
    priceCell,
    r => el('td', { class: 'cell-condition', text: r.condition }),
    titleCell,
    r => el('td', { class: 'cell-seller', text: r.seller }),
    noteChips,
  ];
  if (hasCapacity) {
    headers.splice(1, 0, t('thEperGB'));
    cells.splice(1, 0, eurPerGbCell);
  }
  if (!single) {
    headers.unshift(t('thMkt'));
    cells.unshift(r => el('td', { class: 'cell-mkt', text: marketplaceOf(r) }));
  }
  sec.append(buildTable(headers, group.rows, cells, 'table-category'));
  container.appendChild(sec);
}

function buildToc() {
  const h2s = [...document.querySelectorAll('#content h2, #marketplace, #methodology')];
  const list = $('#toc-list');
  list.textContent = '';
  for (const h of h2s) {
    const a = el('a', { href: '#' + h.id, text: h.textContent });
    list.appendChild(el('li', {}, a));
  }
  // scrollspy: highlight the TOC entry of the section currently in view
  if (tocObserver) tocObserver.disconnect();
  const links = [...list.querySelectorAll('a')];
  tocObserver = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const l of links) l.classList.toggle('active', l.getAttribute('href') === '#' + entry.target.id);
    }
  }, { rootMargin: '-20% 0px -70% 0px' });
  h2s.forEach(h => tocObserver.observe(h));
}

function setupStatsLink() {
  const script = document.querySelector('script[data-goatcounter]');
  if (!script) return;
  const site = script.dataset.goatcounter;
  if (!site || site.includes('YOURSITE')) return;
  $('#footer-stats').appendChild(
    el('a', { href: 'https://' + site, target: '_blank', rel: 'noopener' }, 'Visitor stats (GoatCounter)'),
  );
}

function formatGenerated(res) {
  const lm = res && res.headers && res.headers.get('last-modified');
  if (!lm) return 'latest scan';
  const d = new Date(lm);
  if (Number.isNaN(d.getTime())) return 'latest scan';
  return d.toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC';
}

// --- i18n + theme application ----------------------------------------------

function applyStaticText() {
  document.documentElement.lang = lang;
  document.title = t('title');
  for (const node of document.querySelectorAll('[data-i18n]')) {
    node.textContent = t(node.dataset.i18n);
  }
  const status = $('#status');
  status.textContent = '';
  status.append(...partsNodes('statusLoading'));
  const list = $('#methodology-list');
  list.textContent = '';
  for (const key of ['m1', 'm2', 'm3', 'm4', 'm5']) {
    list.appendChild(el('li', {}, ...partsNodes(key)));
  }
  const tools = $('#footer-tools');
  tools.textContent = '';
  tools.append(...partsNodes('footerTools'));
  $('#f-search').placeholder = t('fSearchPlaceholder');
  $('#f-maxprice').placeholder = t('fMaxPricePlaceholder');
  $('#lang-en').classList.toggle('active', lang === 'en');
  $('#lang-de').classList.toggle('active', lang === 'de');
  applyTheme();
}

function applyTheme() {
  document.documentElement.dataset.theme = theme;
  const btn = $('#theme-toggle');
  if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
  localStorage.setItem('theme', theme);
  applyTheme();
}

// --- data rendering ---------------------------------------------------------

function renderReport() {
  const content = $('#content');
  content.textContent = '';
  const status = $('#status');
  const error = $('#error');
  if (lastError) {
    status.hidden = true;
    content.hidden = true;
    error.hidden = false;
    error.textContent = '';
    error.append(
      el('p', { class: 'error-title' }, t('errTitle')),
      ...(I18N[lang] || I18N.en).errorBody.map(parts => el('p', {}, ...parts.map(p => (typeof p === 'string' ? p : el('code', { text: p.code }))))),
    );
    return;
  }
  error.hidden = true;
  const { groups, flagged, total, queries, marketplaces, single } = analyze(cachedRows || []);
  const idx = history ? indexPct(movers(history)) : null;
  const idxPart = idx != null ? ` · ${t('indexLabel')} ${pctStr(idx)}` : '';
  $('#generated-line').textContent = t('generated')(lastGenerated, total, queries.length) + idxPart;

  const baseQueries = [...new Set(groups.map(g => g.query))].sort();
  populateSelect($('#f-category'), baseQueries, t('fAll'));
  const mpWrap = $('#f-marketplace-wrap');
  if (mpWrap) mpWrap.hidden = marketplaces.length <= 1;
  if (marketplaces.length > 1) populateSelect($('#f-marketplace'), marketplaces, t('fAll'));

  const active = filterActive();
  const shown = groups
    .map(g => {
      const rows = g.rows.filter(matchesFilter);
      if (!rows.length) return null;
      rows.sort(compareRows);
      const prices = rows.map(r => num(r.price)).filter(v => v != null);
      return {
        ...g,
        rows,
        count: rows.length,
        median: median(prices),
        cheapest: rows[0],
        atTargetCount: rows.filter(r => flagFor(r) === '🔥 at/near buy-low target').length,
      };
    })
    .filter(Boolean);
  const shownTotal = shown.reduce((n, g) => n + g.count, 0);
  $('#f-count').textContent = t('fCount')(shownTotal, total);

  if (!active) renderHighlights(flagged, content, single);
  const mv = history ? movers(history) : [];
  if (!active && mv.length) renderMovers(mv, content, single);
  if (!shown.length) {
    content.append(el('p', {}, t('fNoMatches')));
  } else {
    const hasCapacity = shown.some(g => CAPACITY_GB[g.query] != null);
    const usedIds = new Set(active ? [] : ['deal-highlights', 'median-movers']);
    for (const g of shown) renderGroup(g, content, usedIds, single, hasCapacity);
  }
  content.hidden = false;
  status.hidden = true;
  buildToc();
}

function setLang(next) {
  if (next === lang) return;
  lang = next;
  localStorage.setItem('lang', lang);
  applyStaticText();
  if (cachedRows || lastError) renderReport();
}

async function loadSecondaryData() {
  // History + per-listing history only power sparklines/trends and repricing
  // notes — never gate the report on them. Load in the background and upgrade
  // the page when they arrive.
  const [histRes, listingRes] = await Promise.all([
    fetchWithTimeout(HISTORY_URL).catch(() => null),
    fetchWithTimeout(LISTING_URL).catch(() => null),
  ]);
  let upgraded = false;
  if (histRes && histRes.res.ok) {
    const hrows = toHistoryRows(histRes.text);
    const keys = new Set(hrows.map(r => `${marketplaceOf(r)} · ${r.query}`));
    history = {};
    for (const key of keys) history[key] = historySeries(hrows, key);
    upgraded = true;
  }
  if (listingRes && listingRes.res.ok) {
    const lrows = toAnyRows(listingRes.text);
    listingHistory = {};
    for (const r of lrows) if (r.url) listingHistory[r.url] = r;
    upgraded = true;
  }
  if (upgraded) renderReport();
}

async function main() {
  const status = $('#status');
  applyStaticText();

  // language switcher + theme
  $('#lang-en').addEventListener('click', () => setLang('en'));
  $('#lang-de').addEventListener('click', () => setLang('de'));
  $('#theme-toggle').addEventListener('click', toggleTheme);

  // interactive filters
  $('#f-search').addEventListener('input', e => { filters.search = e.target.value; renderReport(); });
  $('#f-marketplace').addEventListener('change', e => { filters.marketplace = e.target.value; renderReport(); });
  $('#f-category').addEventListener('change', e => { filters.category = e.target.value; renderReport(); });
  $('#f-maxprice').addEventListener('input', e => {
    const v = parseFloat(e.target.value);
    filters.maxPrice = Number.isFinite(v) && v >= 0 ? v : null;
    renderReport();
  });
  $('#f-sort').addEventListener('change', e => { filters.sort = e.target.value; renderReport(); });
  $('#f-reset').addEventListener('click', () => {
    filters.search = '';
    filters.marketplace = 'all';
    filters.category = 'all';
    filters.maxPrice = null;
    filters.sort = 'price-asc';
    syncFilterInputs();
    renderReport();
  });

  try {
    // Critical path: load deal rows (per-category chunks, or one CSV as a
    // fallback). History and per-listing history load afterwards and upgrade
    // the page — the report never waits for them.
    const deals = await loadDeals();
    lastGenerated = deals.generated;
    cachedRows = deals.rows;
    $('#filters').hidden = false;
    renderReport();

    loadSecondaryData();
  } catch (err) {
    console.error('Report failed to load:', err);
    lastError = err;
    status.hidden = true;
    renderReport();
  }
  setupStatsLink();
}

main();
