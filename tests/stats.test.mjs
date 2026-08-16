// stats.test.mjs — validates site/csv.js against the real generated CSV.
// Run from the repo root:  node --test tests/
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { parseCSV, toRows, analyze, euro, num, median, flagFor } from '../site/csv.js';

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
  assert.deepEqual(headers, ['condition', 'currency', 'price', 'query', 'seller', 'title', 'url', 'win_max', 'win_min']);
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
  assert.equal(new Set(groups.map(g => g.query)).size, groups.length, 'group names are unique');
  for (const g of groups) {
    assert.ok(g.count > 0);
    assert.ok(g.median > 0, 'median is a positive number');
    assert.equal(num(g.cheapest.price), Math.min(...g.rows.map(r => num(r.price))), 'cheapest is the min price');
    assert.ok(g.atTargetCount <= g.count);
  }
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

// --- human-readable sanity summary (node --test shows it in the report) ---
{
  const { groups, flagged, total, queries } = analyze(toRows(text));
  console.log(`\n[summary] ${total} items across ${queries.length} categories, ${flagged.length} flagged deal(s)`);
  for (const g of groups) {
    console.log(`  ${g.query.padEnd(24)} n=${g.count.toString().padStart(3)}  median=${euro(g.median).padStart(12)}  cheapest=${euro(g.cheapest.price).padStart(12)}  atTarget=${g.atTargetCount}`);
  }
}
