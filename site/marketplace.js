// marketplace.js — "Facebook Marketplace board" (deep links only).
//
// Renders two OFFLINE-built datasets next to the eBay report:
//   1. Your watchlist (data/marketplace/watchlist.csv) — links you pasted
//      from your OWN browser session (site/data/marketplace/collected_links.txt
//      is parsed by the nightly job; nothing is ever fetched from Facebook).
//   2. Per-country search entry points (data/marketplace/searches.csv) —
//      Marketplace deep links regenerated nightly by the workflow.
//
// Both datasets are plain URLs. Opening one takes you to a logged-in
// Marketplace search/item in your browser — the board itself never requests
// facebook.com. Marketplace has no public API; scraping violates its ToS.
import { toAnyRows } from './csv.js';

const WATCHLIST_URL = window.MP_WATCHLIST || 'data/marketplace/watchlist.csv';
const SEARCHES_URL = window.MP_SEARCHES || 'data/marketplace/searches.csv';

const I18N = {
  en: {
    title: 'Facebook Marketplace — deep links',
    note: 'Deep links only — no listing data is fetched (Marketplace has no public API, and scraping violates its ToS). Open the links in your logged-in Facebook browser: each one is a pre-configured search or item.',
    wlTitle: 'Your watchlist — links you pasted from your own browsing',
    wlEmpty: 'Nothing yet — paste Marketplace links into <code>site/data/marketplace/collected_links.txt</code> (one per line, <code>#</code> comments ok). The nightly job parses them offline and tracks first/last-seen here.',
    searchesTitle: 'Per-country search entry points (regenerated nightly)',
    thType: 'Type',
    thTarget: 'Target',
    thLocation: 'Location',
    thNote: 'Note',
    thFirst: 'First seen',
    thLast: 'Last seen',
    thOpen: 'Open',
    thQuery: 'Search',
    thCountry: 'Country',
    thCity: 'City',
    thCurrency: 'Currency',
    itemWord: 'Item',
    searchWord: 'Search',
    savedLocation: '(saved location)',
    openLabel: 'Open ↗',
  },
  de: {
    title: 'Facebook Marketplace — Deep Links',
    note: 'Nur Deep Links — es werden keine Angebotsdaten abgerufen (Marketplace hat keine öffentliche API, Scraping verletzt die ToS). Die Links im eingeloggten Facebook-Browser öffnen: jeder ist eine vorkonfigurierte Suche oder ein Artikel.',
    wlTitle: 'Deine Watchlist — Links aus deinem eigenen Browsen',
    wlEmpty: 'Noch leer — Marketplace-Links in <code>site/data/marketplace/collected_links.txt</code> einfügen (eine pro Zeile, <code>#</code>-Kommentare ok). Der Nacht-Job parst sie offline und führt hier Erst-/Letzt-Gesehen.',
    searchesTitle: 'Such-Einstiegspunkte pro Land (nächtlich neu erzeugt)',
    thType: 'Typ',
    thTarget: 'Ziel',
    thLocation: 'Ort',
    thNote: 'Notiz',
    thFirst: 'Erst gesehen',
    thLast: 'Zuletzt gesehen',
    thOpen: 'Öffnen',
    thQuery: 'Suche',
    thCountry: 'Land',
    thCity: 'Stadt',
    thCurrency: 'Währung',
    itemWord: 'Artikel',
    searchWord: 'Suche',
    savedLocation: '(gespeicherter Ort)',
    openLabel: 'Öffnen ↗',
  },
};

let lang = localStorage.getItem('lang') ||
  (navigator.language && navigator.language.toLowerCase().startsWith('de') ? 'de' : 'en');

function t(key) {
  return (I18N[lang] || I18N.en)[key] ?? I18N.en[key] ?? key;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else if (k === 'html') node.innerHTML = v;
    else node.setAttribute(k, v);
  }
  for (const child of children) {
    if (child == null) continue;
    node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return node;
}

function openCell(url) {
  return el('td', {}, el('a', { href: url || '#', target: '_blank', rel: 'noopener' }, t('openLabel')));
}

function buildTable(headers, rows, cellFns, cls) {
  const table = el('table');
  table.append(
    el('thead', {}, el('tr', {}, ...headers.map(h => el('th', { text: h })))),
    el('tbody', {}, ...rows.map(r => el('tr', {}, ...cellFns.map(fn => fn(r))))),
  );
  return el('div', { class: 'table-wrap' + (cls ? ' ' + cls : '') }, table);
}

function renderWatchlist(body, rows) {
  const h3 = el('h3', { text: t('wlTitle') });
  if (!rows.length) {
    body.append(h3, el('p', { class: 'mkt-empty', html: t('wlEmpty') }));
    return;
  }
  const items = rows.filter(r => r.type === 'item');
  const searches = rows.filter(r => r.type !== 'item');
  body.append(h3);
  if (items.length) {
    body.append(
      el('h4', { class: 'mkt-sub', text: `${t('itemWord')} (${items.length})` }),
      buildTable(
        [t('thTarget'), t('thNote'), t('thFirst'), t('thLast'), t('thOpen')],
        items,
        [
          r => el('td', { class: 'cell-title' }, el('a', { href: r.url, target: '_blank', rel: 'noopener' }, r.item_id || r.url)),
          r => el('td', { text: r.note || '—' }),
          r => el('td', { text: r.first_seen }),
          r => el('td', { text: r.last_seen }),
          r => openCell(r.url),
        ],
        'table-watchlist',
      ),
    );
  }
  if (searches.length) {
    body.append(
      el('h4', { class: 'mkt-sub', text: `${t('searchWord')} (${searches.length})` }),
      buildTable(
        [t('thTarget'), t('thLocation'), t('thNote'), t('thFirst'), t('thLast'), t('thOpen')],
        searches,
        [
          r => el('td', { class: 'cell-title' }, el('a', { href: r.url, target: '_blank', rel: 'noopener' }, r.keyword || r.url)),
          r => el('td', { text: r.location || t('savedLocation') }),
          r => el('td', { text: r.note || '—' }),
          r => el('td', { text: r.first_seen }),
          r => el('td', { text: r.last_seen }),
          r => openCell(r.url),
        ],
        'table-watchlist',
      ),
    );
  }
}

function renderSearches(body, rows) {
  const h3 = el('h3', { text: t('searchesTitle') });
  if (!rows.length) {
    body.append(h3, el('p', { class: 'mkt-empty' }, '—'));
    return;
  }
  body.append(h3);
  const byQuery = new Map();
  for (const r of rows) {
    const q = r.query || '—';
    if (!byQuery.has(q)) byQuery.set(q, []);
    byQuery.get(q).push(r);
  }
  for (const [query, qrows] of byQuery) {
    body.append(
      el('h4', { class: 'mkt-sub', text: query }),
      buildTable(
        [t('thCountry'), t('thCity'), t('thCurrency'), t('thOpen')],
        qrows,
        [
          r => el('td', { text: `${r.country_name || r.country || '—'} (${r.country || ''})` }),
          r => el('td', { text: r.city }),
          r => el('td', { text: r.currency || '—' }),
          r => openCell(r.url),
        ],
        'table-searches',
      ),
    );
  }
}

function renderAll() {
  const section = document.getElementById('marketplace-section');
  if (!section) return;
  const title = document.getElementById('marketplace');
  if (title) title.textContent = t('title');
  const body = document.getElementById('marketplace-body');
  if (!body || !window.__MP_DATA) return;
  const { watchlist, searches } = window.__MP_DATA;
  body.textContent = '';
  body.append(el('p', { class: 'mkt-note', text: t('note') }));
  renderWatchlist(body, watchlist);
  renderSearches(body, searches);
  section.hidden = false;
}

function fetchWithTimeout(url, ms = 8000) {
  // A hung fetch must not leave the board stuck in "loading" forever — after
  // the timeout the request is treated as "no data" and the board renders its
  // empty state instead of hanging silently.
  let timerId;
  const timer = new Promise((_, reject) => { timerId = setTimeout(() => reject(new Error(`timeout fetching ${url}`)), ms); });
  return Promise.race([fetch(url, { cache: 'no-cache' }), timer]).finally(() => clearTimeout(timerId));
}

async function main() {
  const [wlRes, seRes] = await Promise.all([
    fetchWithTimeout(WATCHLIST_URL).catch(() => null),
    fetchWithTimeout(SEARCHES_URL).catch(() => null),
  ]);
  const watchlist = wlRes && wlRes.ok ? toAnyRows(await wlRes.text()) : [];
  const searches = seRes && seRes.ok ? toAnyRows(await seRes.text()) : [];
  // Always render the board: with data it shows the tables, without data it
  // shows the empty-state guidance (never a silent "nothing happened").
  window.__MP_DATA = { watchlist, searches };
  renderAll();

  // stay in sync with app.js's language toggle
  document.getElementById('lang-en')?.addEventListener('click', () => { lang = 'en'; renderAll(); });
  document.getElementById('lang-de')?.addEventListener('click', () => { lang = 'de'; renderAll(); });
}

main();

// Exported for tests (publish/tests/marketplace_smoke.mjs) — the render
// functions execute against a stub DOM so runtime ReferenceErrors like the
// openCell(r.url) bug are caught, not just syntax.
export { renderWatchlist, renderSearches };
