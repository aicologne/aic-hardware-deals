// app_smoke.mjs — executes site/app.js against a stub DOM and the REAL scanned
// CSVs, then asserts the page rendered: a ranked shortlist, the deal highlights
// and the per-category tables. Run from the repo root:
//
//     node tests/app_smoke.mjs
//
// Why: app.js is the user-facing surface and had no test at all. A syntax check
// (node --check) cannot catch a ReferenceError inside a render function — the
// marketplace board once shipped exactly that bug. This harness runs the whole
// load path (chunked CSV fetch -> analyze -> render) in Node with no browser.

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const SITE = path.join(ROOT, 'site');

// --- stub DOM ---------------------------------------------------------------
const allNodes = [];

function makeEl(tag = 'div') {
  const node = {
    tagName: String(tag).toUpperCase(),
    children: [],
    _attrs: {},
    _text: '',
    _html: '',
    hidden: false,
    value: '',
    href: '',
    dataset: {},
    style: {},
    classList: {
      _set: new Set(),
      add(...c) { c.forEach(x => this._set.add(x)); },
      remove(...c) { c.forEach(x => this._set.delete(x)); },
      contains(c) { return this._set.has(c); },
      toggle(c, force) {
        const on = force === undefined ? !this._set.has(c) : !!force;
        if (on) this._set.add(c); else this._set.delete(c);
        return on;
      },
    },
    appendChild(child) { this.children.push(child); return child; },
    append(...kids) { this.children.push(...kids); },
    insertBefore(child) { this.children.unshift(child); return child; },
    removeChild(child) {
      const i = this.children.indexOf(child);
      if (i >= 0) this.children.splice(i, 1);
      return child;
    },
    remove() {},
    setAttribute(name, value) { this._attrs[name] = value; },
    getAttribute(name) { return this._attrs[name]; },
    addEventListener() {},
    removeEventListener() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    closest() { return null; },
    focus() {},
    scrollIntoView() {},
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); this.children = []; },
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    get className() { return [...this.classList._set].join(' '); },
    set className(v) { this.classList._set = new Set(String(v).split(/\s+/).filter(Boolean)); },
  };
  allNodes.push(node);
  return node;
}

const bySelector = new Map();
global.document = {
  createElement: tag => makeEl(tag),
  createTextNode: text => ({ nodeType: 3, textContent: String(text) }),
  querySelector(sel) {
    if (!bySelector.has(sel)) bySelector.set(sel, makeEl('div'));
    return bySelector.get(sel);
  },
  querySelectorAll: () => [],
  documentElement: { lang: 'en', dataset: {} },
  title: '',
};
global.localStorage = { getItem: () => null, setItem: () => {} };
global.location = { search: '' };
global.window = global;
global.IntersectionObserver = class { observe() {} unobserve() {} disconnect() {} };

// --- fetch serving the real site/ data --------------------------------------
const requested = [];
global.fetch = async url => {
  const rel = String(url).replace(/^\.\//, '');
  const file = path.join(SITE, rel);
  requested.push(rel);
  if (!existsSync(file)) return { ok: false, status: 404, headers: { get: () => null }, text: async () => '' };
  const body = readFileSync(file, 'utf8');
  return {
    ok: true,
    status: 200,
    headers: { get: name => (name.toLowerCase() === 'last-modified' ? 'Fri, 11 Sep 2026 05:09:57 GMT' : null) },
    text: async () => body,
  };
};
process.on('unhandledRejection', err => { console.error('unhandled rejection:', err); process.exit(1); });

// --- run the app -------------------------------------------------------------
await import('../site/app.js');
await new Promise(r => setTimeout(r, 300));   // let the async load path settle

const content = bySelector.get('#content');
if (!content) {
  console.error('FAIL: app.js never rendered into #content');
  process.exit(1);
}

function walk(node, out = []) {
  if (!node || typeof node !== 'object') return out;
  out.push(node);
  for (const child of node.children || []) walk(child, out);
  return out;
}
const nodes = walk(content);
/** All visible text under a node: element textContent plus real text nodes. */
function textOf(n) {
  if (!n || typeof n !== 'object') return '';
  if (n.nodeType === 3) return String(n.textContent || '');
  return String(n._text || '') + ' ' + (n.children || []).map(textOf).join(' ');
}

function find(pred) { return nodes.find(pred); }
function findAll(pred) { return nodes.filter(pred); }
const hasClass = (n, c) => n.classList && n.classList.contains(c);

let failures = 0;
function check(name, fn) {
  try {
    fn();
    console.log('  ok   ' + name);
  } catch (err) {
    failures++;
    console.error('  FAIL ' + name + ': ' + err.message);
  }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }

const shortlistH2 = find(n => n._attrs && n._attrs.id === 'shortlist');
const shortlistTable = find(n => hasClass(n, 'table-shortlist'));
const shortlistRows = shortlistTable
  ? walk(shortlistTable).filter(n => n.tagName === 'TR' && n.children.some(c => c.tagName === 'TD'))
  : [];
const { buildShortlist } = await import('../site/csv.js');
const expected = buildShortlist(
  (await import('../site/csv.js')).toRows(readFileSync(path.join(SITE, 'data', 'ebay_deals.csv'), 'utf8')),
  { listingRows: (await import('../site/csv.js')).toAnyRows(readFileSync(path.join(SITE, 'data', 'listing_history.csv'), 'utf8')).filter(r => r.url), feeRate: 0.13 },
).items.length;

check('the page rendered the ranked shortlist section', () => {
  assert(shortlistH2, 'no <h2 id="shortlist"> in the rendered content');
  assert(shortlistTable, 'no .table-shortlist rendered');
  assert(shortlistRows.length === expected,
    'rendered ' + shortlistRows.length + ' shortlist rows, buildShortlist returned ' + expected);
  const cellsInFirst = shortlistRows[0].children.filter(c => c.tagName === 'TD').length;
  assert(cellsInFirst >= 7, 'expected rank/category/price/estimate/margin/churn/title/note cells, got ' + cellsInFirst);
});

check('shortlist rows carry a rank, a margin and a churn chip', () => {
  const first = shortlistRows[0];
  const tds = first.children.filter(c => c.tagName === 'TD');
  assert(/^\d+$/.test(tds[0]._text.trim()), 'first cell is not a rank: ' + JSON.stringify(tds[0]._text));
  assert(/€/.test(tds[4]._text + textOf(tds[4])), 'margin cell has no euro amount');
  const churnChip = findAll(n => hasClass(n, 'chip-churn'));
  assert(churnChip.length > 0, 'no churn chips rendered');
  assert(/churn \d+ % of \d+ tracked/.test(churnChip[0]._text), 'unexpected churn chip text: ' + churnChip[0]._text);
});

check('the intro states the estimate provenance and the churn baseline', () => {
  const text = textOf(content);
  assert(/market churn/.test(text), 'intro does not explain the churn weighting');
  assert(/asking median|sold medians/.test(text), 'intro does not label the estimate source');
});

check('the rest of the report still rendered', () => {
  assert(find(n => n._attrs && n._attrs.id === 'deal-highlights'), 'deal highlights missing');
  const categoryTables = findAll(n => hasClass(n, 'table-category'));
  assert(categoryTables.length > 0, 'no per-category tables rendered');
  const generated = bySelector.get('#generated-line');
  assert(generated && /items across/.test(generated._text), 'generated line not filled: ' + JSON.stringify(generated && generated._text));
});

check('the load path used the split per-category chunks', () => {
  assert(requested.includes('data/deals/index.json'), 'did not fetch the chunk manifest');
  assert(requested.some(u => u.startsWith('data/deals/') && u.endsWith('.csv')), 'did not fetch any category chunk');
  assert(requested.includes('data/listing_history.csv'), 'did not fetch the per-listing history (shortlist churn needs it)');
});

if (failures) {
  console.error('\n' + failures + ' check(s) FAILED');
  process.exit(1);
}
console.log('\nAll app render checks passed (' + shortlistRows.length + ' ranked rows)');
