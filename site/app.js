// app.js — client-side rendering for the eBay price report.
// Fetches the nightly-generated CSV (data/ebay_deals.csv), renders the deal
// highlights + per-category tables, and builds the table of contents.
//
// Override the data source anytime, e.g. for local testing:
//   ?csv=../ebay_deals.csv   -> app.js reads window.DEALS_CSV
import { toRows, analyze, euro, flagFor, num } from './csv.js';

const CSV_URL = window.DEALS_CSV || 'data/ebay_deals.csv';

const $ = (sel, root = document) => root.querySelector(sel);

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

function windowStr(wmin, wmax) {
  if (wmin == null) return 'any';
  const fmt = n => '€' + Math.round(n).toLocaleString('de-DE');
  return `${fmt(wmin)}–${fmt(wmax)}`;
}

function buildTable(headers, rows, cellFns) {
  const t = el('table');
  const thead = el('thead', {}, el('tr', {}, ...headers.map(h => el('th', { text: h }))));
  const tbody = el('tbody');
  for (const r of rows) tbody.appendChild(el('tr', {}, ...cellFns.map(fn => fn(r))));
  t.append(thead, tbody);
  return el('div', { class: 'table-wrap' }, t);
}

function titleCell(r) {
  return el('td', {}, el('a', { href: r.url || '#', target: '_blank', rel: 'noopener' }, r.title || '(no title)'));
}

function priceCell(r) {
  return el('td', {}, el('strong', { text: euro(r.price) }));
}

// --- rendering ------------------------------------------------------------

function renderHighlights(flagged, container) {
  const h2 = el('h2', { id: 'deal-highlights' }, '🔥 Deal highlights');
  if (!flagged.length) {
    container.append(
      h2,
      el('p', {},
        'No listings currently sit at the buy-low targets. Check back after the next nightly scan, or widen the windows in ',
        el('code', { text: 'ebay_search.py' }),
        '.'),
    );
    return;
  }
  const table = buildTable(
    ['Category', 'Price', 'Buy-low target', 'Title', 'Seller'],
    flagged,
    [
      r => el('td', { text: r.query }),
      priceCell,
      r => el('td', { text: euro(r.win_min) }),
      titleCell,
      r => el('td', { text: r.seller }),
    ],
  );
  container.append(
    h2,
    el('p', {},
      'Listings currently ',
      el('strong', { text: 'at or within 15 % of the buy-low target' }),
      ' — the shortlist to inspect first:'),
    table,
  );
}

function renderGroup(group, container, usedIds) {
  const sec = el('section', { class: 'category' });
  const h2 = el('h2', { id: slugify(group.query, usedIds) }, `${group.query} (${group.count} items)`);
  const summary = el('p', { class: 'summary' }, el('em', {},
    'Window ',
    windowStr(group.wmin, group.wmax),
    ' · median ',
    el('strong', { text: euro(group.median) }),
    ' · cheapest ',
    el('strong', { text: euro(group.cheapest.price) }),
    ` · ${group.atTargetCount} at/near buy-low`,
  ));
  const table = buildTable(
    ['Price', 'Condition', 'Title', 'Seller', 'Note'],
    group.rows,
    [
      priceCell,
      r => el('td', { text: r.condition }),
      titleCell,
      r => el('td', { text: r.seller }),
      r => el('td', { text: flagFor(r) }),
    ],
  );
  sec.append(h2, summary, table);
  container.appendChild(sec);
}

function buildToc() {
  const h2s = [...document.querySelectorAll('#content h2, #methodology')];
  const list = $('#toc-list');
  list.textContent = '';
  for (const h of h2s) {
    const a = el('a', { href: '#' + h.id, text: h.textContent });
    list.appendChild(el('li', {}, a));
  }
  // scrollspy: highlight the TOC entry of the section currently in view
  const links = [...list.querySelectorAll('a')];
  const spy = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const l of links) l.classList.toggle('active', l.getAttribute('href') === '#' + entry.target.id);
    }
  }, { rootMargin: '-20% 0px -70% 0px' });
  h2s.forEach(h => spy.observe(h));
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
  const str = d.toLocaleString('de-DE', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' });
  return `${str} UTC`;
}

async function main() {
  const status = $('#status');
  const error = $('#error');
  const content = $('#content');
  let res;
  try {
    res = await fetch(CSV_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${CSV_URL}`);
    const text = await res.text();
    const { groups, flagged, total, queries } = analyze(toRows(text));

    $('#generated-line').textContent =
      `Generated ${formatGenerated(res)} · ${total} items across ${queries.length} categories · marketplace eBay.de, used, EUR`;

    if (total === 0) {
      content.append(el('p', {}, 'No listings found in the latest scan.'));
    } else {
      renderHighlights(flagged, content);
      const usedIds = new Set(['deal-highlights']);
      for (const g of groups) renderGroup(g, content, usedIds);
    }
    content.hidden = false;
    status.hidden = true;
    buildToc();
  } catch (err) {
    console.error('Report failed to load:', err);
    status.hidden = true;
    error.hidden = false;
    error.textContent = '';
    error.append(
      el('p', { class: 'error-title' }, 'Could not load the report data.'),
      el('p', {},
        'The page reads its listings from ',
        el('code', { text: CSV_URL }),
        ' (generated nightly by the GitHub Actions scan).',
      ),
      el('p', {},
        'If you opened this file directly via ',
        el('code', { text: 'file://' }),
        ', browsers block that fetch — serve the folder over HTTP instead, e.g. ',
        el('code', { text: 'python -m http.server' }),
        ' in the repo root, then open ',
        el('code', { text: 'http://localhost:8000/site/' }),
        '.'),
    );
  }
  setupStatsLink();
}

main();
