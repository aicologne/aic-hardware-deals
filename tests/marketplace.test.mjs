// marketplace.test.mjs — unit tests for site/marketplace.js (Facebook
// Marketplace board render functions).
//
// Run from the repo root:
//   node --test tests/            (test runner; spawns per-file processes)
//   node tests/marketplace.test.mjs   (in-process, works under sandboxes)
//
// marketplace.js touches browser globals at import time (window, document,
// localStorage, navigator, fetch) and calls main() on load, so all stubs
// must exist BEFORE the module is imported.

import test from 'node:test';
import assert from 'node:assert/strict';

// --- stub DOM / browser globals (must exist before importing the module) ---

let storedLang = 'en';

class FakeNode {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this._attrs = {};
    this._text = '';
    this._html = '';
    this._className = '';
  }
  appendChild(c) { this.children.push(c); return c; }
  append(...cs) { this.children.push(...cs); }
  setAttribute(name, val) { this._attrs[name] = String(val); }
  addEventListener() {} // main() wires the lang toggles after rendering
  get textContent() { return this._text; }
  set textContent(v) { this._text = String(v); }
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = String(v); }
  get className() { return this._className; }
  set className(v) { this._className = v; }
}

global.document = {
  createElement: tag => new FakeNode(tag),
  createTextNode: text => ({ nodeType: 3, textContent: String(text) }),
  getElementById: () => new FakeNode('DIV'),
};
global.localStorage = { getItem: () => storedLang, setItem: () => {} };
// Node 21+ already ships a read-only global navigator (language en-US), so
// only define one when the runtime does not provide it.
if (!('navigator' in globalThis)) globalThis.navigator = { language: 'en-US' };
global.window = global;
// main() fetches the board CSVs; in Node these are relative URLs, so stub
// fetch to return "not found" — main() then exits early with empty data.
global.fetch = async () => ({ ok: false });
process.on('unhandledRejection', () => {});

const { renderWatchlist, renderSearches } = await import('../site/marketplace.js');

// --- fake-DOM helpers -------------------------------------------------------

function walk(node, fn) {
  fn(node);
  for (const c of node.children || []) walk(c, fn);
}

function byTag(root, tag) {
  const out = [];
  walk(root, n => { if (n.tagName === tag) out.push(n); });
  return out;
}

function textOf(node) {
  if (node.nodeType === 3) return node.textContent;
  if (node._text) return node._text;
  if (node._html) return node._html;
  return (node.children || []).map(textOf).join('');
}

// --- renderWatchlist --------------------------------------------------------

test('renderWatchlist with no rows shows the empty note and no tables', () => {
  const body = new FakeNode('DIV');
  renderWatchlist(body, []);
  assert.equal(byTag(body, 'H3').length, 1);
  assert.match(textOf(byTag(body, 'H3')[0]), /watchlist/i);
  assert.equal(byTag(body, 'TABLE').length, 0);
  const empty = byTag(body, 'P')[0];
  assert.ok(empty, 'renders an empty-state paragraph');
  assert.equal(empty.className, 'mkt-empty');
  assert.ok(empty._html.length > 0, 'empty note carries guidance text');
});

test('renderWatchlist renders item rows with title and open deep links', () => {
  const rows = [
    { type: 'item', item_id: '1234567890', url: 'https://www.facebook.com/marketplace/item/1234567890/', note: 'GPU seller', first_seen: '2026-08-26', last_seen: '2026-08-26' },
    { type: 'item', item_id: '42', url: 'https://www.facebook.com/marketplace/item/42/', first_seen: '2026-08-25', last_seen: '2026-08-26' },
  ];
  const body = new FakeNode('DIV');
  renderWatchlist(body, rows);
  const h4s = byTag(body, 'H4').map(textOf);
  assert.deepEqual(h4s, ['Item (2)'], 'one sub-heading with the item count');
  const wrapper = byTag(body, 'DIV').find(d => d.className.includes('table-wrap'));
  assert.equal(wrapper.className, 'table-wrap table-watchlist');
  const table = byTag(body, 'TABLE')[0];
  assert.ok(table, 'items render a table');
  assert.deepEqual(
    byTag(table, 'TH').map(textOf),
    ['Target', 'Note', 'First seen', 'Last seen', 'Open'],
  );
  assert.equal(byTag(table, 'TR').length, 3, 'header row + 2 data rows');
  const links = byTag(table, 'A');
  assert.equal(links.length, 4, 'title link + open link per row');
  // title link — item_id is the link text, deep link opens in a new tab
  assert.equal(textOf(links[0]), '1234567890');
  assert.equal(links[0]._attrs.href, rows[0].url);
  assert.equal(links[0]._attrs.target, '_blank');
  assert.equal(links[0]._attrs.rel, 'noopener');
  // open link
  assert.equal(textOf(links[1]), 'Open ↗');
  assert.equal(links[1]._attrs.href, rows[0].url);
  assert.equal(links[1]._attrs.target, '_blank');
  // note fallback: second row has no note -> em dash
  const tds = byTag(table, 'TD').map(textOf);
  assert.equal(tds[1], 'GPU seller');
  assert.equal(tds[6], '—');
});

test('renderWatchlist renders search rows with keyword links and saved-location fallback', () => {
  const rows = [
    { type: 'search', keyword: 'RTX 3090', location: 'cologne', url: 'https://www.facebook.com/marketplace/cologne/search/?query=RTX+3090', first_seen: '2026-08-26', last_seen: '2026-08-26' },
    { type: 'search', keyword: 'RAM', url: 'https://fb/search/ram', first_seen: '2026-08-25', last_seen: '2026-08-26' },
  ];
  const body = new FakeNode('DIV');
  renderWatchlist(body, rows);
  const h4s = byTag(body, 'H4').map(textOf);
  assert.deepEqual(h4s, ['Search (2)']);
  const table = byTag(body, 'TABLE')[0];
  assert.deepEqual(
    byTag(table, 'TH').map(textOf),
    ['Target', 'Location', 'Note', 'First seen', 'Last seen', 'Open'],
  );
  const links = byTag(table, 'A');
  assert.equal(textOf(links[0]), 'RTX 3090', 'keyword is the link text');
  assert.equal(links[0]._attrs.href, rows[0].url);
  assert.equal(textOf(links[2]), 'RAM');
  const tds = byTag(table, 'TD').map(textOf);
  assert.equal(tds[1], 'cologne');
  assert.equal(tds[7], '(saved location)', 'missing location falls back');
});

test('renderWatchlist splits mixed rows into item and search tables', () => {
  const rows = [
    { type: 'item', item_id: '1', url: 'https://fb/i/1', first_seen: 'a', last_seen: 'b' },
    { type: 'search', keyword: 'GPU', url: 'https://fb/s/1', first_seen: 'a', last_seen: 'b' },
  ];
  const body = new FakeNode('DIV');
  renderWatchlist(body, rows);
  assert.deepEqual(
    byTag(body, 'H4').map(textOf),
    ['Item (1)', 'Search (1)'],
    'one sub-heading per non-empty group, items first',
  );
  assert.equal(byTag(body, 'TABLE').length, 2);
});

// --- renderSearches ---------------------------------------------------------

test('renderSearches with no rows shows a dash placeholder', () => {
  const body = new FakeNode('DIV');
  renderSearches(body, []);
  assert.equal(byTag(body, 'H3').length, 1);
  assert.equal(byTag(body, 'TABLE').length, 0);
  const p = byTag(body, 'P')[0];
  assert.equal(p.className, 'mkt-empty');
  assert.equal(textOf(p), '—');
});

test('renderSearches groups rows by query and formats country cells', () => {
  const rows = [
    { query: 'RTX 3090', country: 'DE', country_name: 'Germany', city: 'cologne', currency: 'EUR', url: 'https://fb/s/rtx' },
    { query: 'RTX 3090', country: 'AT', country_name: 'Austria', city: 'wien', currency: 'EUR', url: 'https://fb/s/rtx-at' },
    { query: 'DDR4 RDIMM 32GB', country: 'DE', country_name: 'Germany', city: 'berlin', url: 'https://fb/s/ram' },
  ];
  const body = new FakeNode('DIV');
  renderSearches(body, rows);
  assert.deepEqual(
    byTag(body, 'H4').map(textOf),
    ['RTX 3090', 'DDR4 RDIMM 32GB'],
    'one heading per query, insertion order preserved',
  );
  const tables = byTag(body, 'TABLE');
  assert.equal(tables.length, 2);
  assert.deepEqual(byTag(tables[0], 'TH').map(textOf), ['Country', 'City', 'Currency', 'Open']);
  assert.equal(byTag(tables[0], 'TR').length, 3, 'header + 2 RTX rows');
  const tds = byTag(tables[0], 'TD').map(textOf);
  assert.equal(tds[0], 'Germany (DE)', 'country_name plus code');
  assert.equal(tds[1], 'cologne');
  assert.equal(tds[2], 'EUR');
  assert.equal(tds[4], 'Austria (AT)');
  const ramTds = byTag(tables[1], 'TD').map(textOf);
  assert.equal(ramTds[2], '—', 'missing currency renders a dash');
  const links = byTag(body, 'A');
  assert.equal(links.length, 3, 'one open link per search row');
  assert.equal(links[0]._attrs.href, 'https://fb/s/rtx');
});

test('renderSearches groups rows without a query under a dash heading', () => {
  const body = new FakeNode('DIV');
  renderSearches(body, [{ country: 'DE', city: 'koln', currency: 'EUR', url: 'https://fb/s/x' }]);
  assert.deepEqual(byTag(body, 'H4').map(textOf), ['—']);
});

test('open cell degrades to "#" when a row has no url', () => {
  const body = new FakeNode('DIV');
  renderSearches(body, [{ query: 'Q', country: 'DE', city: 'c', currency: 'EUR' }]);
  const link = byTag(body, 'A')[0];
  assert.equal(link._attrs.href, '#');
});

// --- i18n -------------------------------------------------------------------

test('German locale strings are used when localStorage lang is de', async () => {
  storedLang = 'de';
  try {
    // query-string import creates a fresh module instance that re-reads
    // localStorage at load time (the default instance cached lang='en').
    const mod = await import('../site/marketplace.js?lang=de');
    const body = new FakeNode('DIV');
    mod.renderWatchlist(body, [{ type: 'item', item_id: '1', url: 'https://fb/i/1', first_seen: 'a', last_seen: 'b' }]);
    assert.equal(textOf(byTag(body, 'H4')[0]), 'Artikel (1)');
    const links = byTag(body, 'A');
    assert.equal(textOf(links[1]), 'Öffnen ↗', 'German open label');
    const empty = new FakeNode('DIV');
    mod.renderWatchlist(empty, []);
    assert.match(textOf(byTag(empty, 'P')[0]), /Noch leer/, 'German empty note');
  } finally {
    storedLang = 'en';
  }
});
