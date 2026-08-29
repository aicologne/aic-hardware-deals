// stats.test.mjs — validates site/csv.js against the real generated CSV.
// Run from the repo root:  node --test tests/
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import {
  parseCSV, toRows, toHistoryRows, toAnyRows, analyze, euro, num, median, flagFor,
  historySeries, movers, indexPct, euroPerGb, CAPACITY_GB, groupKey, topDeals,
} from '../site/csv.js';

const csvPath = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'site', 'data', 'ebay_deals.csv');
const text = readFileSync(csvPath, 'utf8');

test('parser handles quoted fields, commas and escaped quotes', () => {
  const t = 'a,b,c\r\n"x, y","q ""z""",3\nplain,field,9\n';
  assert.deepEqual(parseCSV(t), [
    ['a', 'b', 'c'],
    ['x, y', 'q "z"', '3'],
    ['plain', 'field', '9'],
  ]);
});

test('toRows maps the generated CSV to objects with the expected headers', () => {
  const rows = toRows(text);
  const headers = Object.keys(rows[0]).sort();
  assert.deepEqual(headers, ['condition', 'currency', 'marketplace', 'price', 'query', 'seller', 'title', 'url', 'win_max', 'win_min']);
  assert.equal(rows.length, parseCSV(text).length - 1, 'one data row per CSV record after the header');
  assert.ok(rows.length > 100, 'scan should contain a healthy number of listings');
  for (const r of rows) {
    assert.ok(r.query && r.title && r.url, 'every row has query, title and url');
    assert.equal(num(r.price) > 0, true, `price parses to a positive number: ${r.price}`);
  }
});

test('analyze groups every row exactly once and keeps totals consistent', () => {
  const { rows, groups, total } = analyze(toRows(text));
  assert.equal(total, rows.length);
  assert.equal(groups.reduce((n, g) => n + g.count, 0), total, 'sum of group counts == total rows');
  assert.equal(new Set(groups.map(g => g.key)).size, groups.length, 'group keys are unique');
  for (const g of groups) {
    assert.ok(g.count > 0);
    assert.ok(g.median > 0, 'median is a positive number');
    assert.equal(num(g.cheapest.price), Math.min(...g.rows.map(r => num(r.price))), 'cheapest is the min price');
    assert.ok(g.atTargetCount <= g.count);
  }
});

test('composite group keys carry the marketplace', () => {
  assert.equal(groupKey({ query: 'DDR4 RDIMM 32GB', marketplace: 'EBAY_AT' }), 'EBAY_AT · DDR4 RDIMM 32GB');
  assert.equal(groupKey({ query: 'DDR4 RDIMM 32GB' }), 'EBAY_DE · DDR4 RDIMM 32GB', 'missing marketplace defaults to EBAY_DE');
  const { marketplaces, single } = analyze(toRows(text));
  assert.ok(marketplaces.includes('EBAY_DE'), 'committed scan is EBAY_DE');
  assert.equal(single, true, 'single-marketplace scan displays bare query names');
});

test('flagged deals match the 15 % buy-low rule (price <= win_min * 1.15)', () => {
  const { flagged } = analyze(toRows(text));
  for (const r of flagged) {
    assert.ok(num(r.price) <= num(r.win_min) * 1.15, `${r.query} ${r.price} should be flagged`);
  }
  const all = analyze(toRows(text)).rows;
  const expected = all.filter(r => num(r.price) <= num(r.win_min) * 1.15).length;
  assert.equal(flagged.length, expected);
});

test('euro formats like render_report.py (German style)', () => {
  assert.equal(euro(42), '€42,00');
  assert.equal(euro(1750.5), '€1.750,50');
  assert.equal(euro(1234567.891), '€1.234.567,89');
  assert.equal(euro('89.99'), '€89,99');
  assert.equal(euro(null), '—');
  assert.equal(euro('n/a'), '—');
});

test('median and flagFor unit behaviour', () => {
  assert.equal(median([3, 1, 2]), 2);
  assert.equal(median([4, 1, 2, 3]), 2.5);
  assert.equal(median([]), null);
  assert.equal(flagFor({ price: '40', win_min: '40', win_max: '120' }), '🔥 at/near buy-low target');
  assert.equal(flagFor({ price: '46.01', win_min: '40', win_max: '120' }), 'ok');
  assert.equal(flagFor({ price: '130', win_min: '40', win_max: '120' }), '⚠️ above scan window');
  assert.equal(flagFor({ price: 'x' }), 'ok');
});

test('toHistoryRows parses history.csv rows without a title column', () => {
  const rows = toHistoryRows(
    'date,marketplace,query,median,cheapest,count,at_target\n' +
    '2026-08-14,EBAY_DE,DDR4 RDIMM 32GB,85.00,40.00,46,2\n' +
    '2026-08-15,EBAY_DE,Nvidia Quadro RTX,600.00,406.24,42,8\n',
  );
  assert.equal(rows.length, 2);
  assert.equal(rows[0].query, 'DDR4 RDIMM 32GB');
  assert.equal(rows[1].median, '600.00');
  assert.equal(toHistoryRows('date,query\n\n').length, 0);
});

test('historySeries sorts by date and keeps one point per date (composite keys)', () => {
  const rows = [
    { query: 'RAM', marketplace: 'EBAY_DE', date: '2026-08-16', median: '90' },
    { query: 'RAM', marketplace: 'EBAY_DE', date: '2026-08-14', median: '85' },
    { query: 'RAM', marketplace: 'EBAY_DE', date: '2026-08-16', median: '95' }, // same date — later value wins
    { query: 'GPU', marketplace: 'EBAY_DE', date: '2026-08-15', median: '1200' },
    { query: 'RAM', marketplace: 'EBAY_AT', date: '2026-08-15', median: '88' }, // different marketplace
    { query: 'RAM', marketplace: 'EBAY_DE', date: 'n/a', median: 'x' },         // unparsable — dropped
  ];
  assert.deepEqual(historySeries(rows, 'EBAY_DE · RAM'), [
    { date: '2026-08-14', median: 85 },
    { date: '2026-08-16', median: 95 },
  ]);
  assert.deepEqual(historySeries(rows, 'EBAY_DE · GPU'), [{ date: '2026-08-15', median: 1200 }]);
  assert.deepEqual(historySeries(rows, 'EBAY_AT · RAM'), [{ date: '2026-08-15', median: 88 }]);
  assert.deepEqual(historySeries(rows, 'EBAY_DE · MISSING'), []);
});

test('movers compares the latest median against ~7 days ago and computes an index', () => {
  const mk = (dates, medians) => dates.map((d, i) => ({ date: d, median: medians[i] }));
  const history = {
    'EBAY_DE · DDR4 RDIMM 32GB': mk(['2026-08-11', '2026-08-14', '2026-08-18'], [80, 85, 95]),
    'EBAY_DE · Nvidia Quadro RTX': mk(['2026-08-10', '2026-08-17', '2026-08-18'], [600, 620, 580]),
    'EBAY_DE · OptiPlex 3070 Micro': mk(['2026-08-17', '2026-08-18'], [140, 140]), // flat
    'EBAY_DE · Single': mk(['2026-08-18'], [100]), // not enough history
  };
  const mv = movers(history);
  assert.ok(mv.length >= 2, 'flat/single entries are excluded, risers/fallers included');
  const byKey = Object.fromEntries(mv.map(m => [m.key, m]));
  const ram = byKey['EBAY_DE · DDR4 RDIMM 32GB'];
  assert.ok(ram, 'RAM is a mover');
  assert.equal(ram.latest, 95);
  assert.equal(ram.ref, 80, 'reference is the earliest point at-or-after 7 days before latest');
  assert.equal(ram.refDate, '2026-08-11');
  assert.ok(Math.abs(ram.delta - ((95 - 80) / 80) * 100) < 1e-9, 'delta computed');
  const flat = byKey['EBAY_DE · OptiPlex 3070 Micro'];
  assert.ok(flat && flat.delta === 0, 'flat series is a mover with delta 0 (consumers filter risers/fallers)');
  assert.equal(byKey['EBAY_DE · Single'], undefined, 'single-point series is not a mover');
  for (let i = 1; i < mv.length; i++) {
    assert.ok(Math.abs(mv[i - 1].delta) >= Math.abs(mv[i].delta), 'sorted by |delta| desc');
  }
  const idx = indexPct(mv);
  assert.ok(idx != null && Number.isFinite(idx), 'index is a finite number');
  assert.equal(indexPct([]), null);
  assert.equal(indexPct(null), null);
});

test('toAnyRows parses schemas with no required columns (listing_history.csv)', () => {
  const rows = toAnyRows(
    'url,query,marketplace,first_seen,first_price,last_seen,last_price\n' +
    'https://x/1,DDR4 RDIMM 32GB,EBAY_DE,2026-08-14,42.00,2026-08-18,50.00\n',
  );
  assert.equal(rows.length, 1);
  assert.equal(rows[0].first_price, '42.00');
  assert.equal(rows[0].last_price, '50.00');
  assert.equal(toAnyRows('a,b\n\n').length, 0);
});

test('euroPerGb uses the capacity map and returns null for unknown/mixed categories', () => {
  assert.equal(euroPerGb('88', 'DDR4 RDIMM 32GB'), 2.75);
  assert.equal(euroPerGb('1000', 'RTX 3090'), 1000 / 24);
  assert.equal(euroPerGb('500', 'Nvidia Quadro RTX'), null, 'mixed-capacity category has no map entry');
  assert.equal(euroPerGb('x', 'RTX 3090'), null, 'unparsable price -> null');
  assert.ok(CAPACITY_GB['RTX 3090'] === 24 && CAPACITY_GB['DDR5 32GB'] === 32, 'map sanity');
});

test('topDeals caps the shortlist at 20 while keeping at least one row per category', () => {
  const mk = (query, price) => ({ query, price: String(price), url: `${query}-${price}` });
  // 3 categories × 10 flagged deals each = 30 flagged
  const flagged = [
    ...Array.from({ length: 10 }, (_, i) => mk('RTX 3090', 500 + i * 10)),
    ...Array.from({ length: 10 }, (_, i) => mk('DDR4 RDIMM 32GB', 40 + i * 2)),
    ...Array.from({ length: 10 }, (_, i) => mk('Tesla P40', 300 + i * 5)),
  ].sort((a, b) => num(a.price) - num(b.price));

  const top = topDeals(flagged);
  assert.equal(top.length, 20, 'capped at 20');
  assert.equal(new Set(top.map(r => r.query)).size, 3, 'every category is represented');

  // with fewer than 20 rows nothing is dropped
  const few = flagged.slice(0, 5);
  assert.deepEqual(topDeals(few), few);

  // one-per-category comes first (the cheapest of each category)
  const first = topDeals(flagged, 3);
  assert.deepEqual(new Set(first.map(r => r.query)), new Set(['RTX 3090', 'DDR4 RDIMM 32GB', 'Tesla P40']));
  assert.deepEqual(first.map(r => num(r.price)), [40, 300, 500], 'cheapest per category, price order');

  assert.deepEqual(topDeals([]), []);
});

// --- human-readable sanity summary (node --test shows it in the report) ---
{
  const { groups, flagged, total, queries } = analyze(toRows(text));
  console.log(`\n[summary] ${total} items across ${queries.length} categories, ${flagged.length} flagged deal(s)`);
  for (const g of groups) {
    console.log(`  ${g.query.padEnd(24)} n=${g.count.toString().padStart(3)}  median=${euro(g.median).padStart(12)}  cheapest=${euro(g.cheapest.price).padStart(12)}  atTarget=${g.atTargetCount}`);
  }
}
