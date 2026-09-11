// stats.test.mjs — validates site/csv.js against the real generated CSV.
// Run from the repo root:  node --test tests/
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import {
  parseCSV, toRows, toHistoryRows, toAnyRows, analyze, euro, num, median, flagFor,
  historySeries, movers, indexPct, euroPerGb, CAPACITY_GB, groupKey, topDeals,
  newestScanDate, staleness, SCAN_HOUR_UTC, STALE_AFTER_HOURS,
  marketChurn, scanDatesFrom, estimateResale, buildShortlist, SHORTLIST,
} from '../site/csv.js';

const siteDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'site');
const dataDir = path.join(siteDir, 'data');
const csvPath = path.join(dataDir, 'ebay_deals.csv');
const text = readFileSync(csvPath, 'utf8');
const historyText = readFileSync(path.join(dataDir, 'history.csv'), 'utf8');
const listingRows = toAnyRows(readFileSync(path.join(dataDir, 'listing_history.csv'), 'utf8'))
  .filter(r => r.url);

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

// --- data freshness (mirror of ebay-search-skill/check_freshness.py) -------
// The nightly job can die silently: every scheduled run from 2026-08-30 to
// 2026-09-08 failed at its unit-test step, the scan never ran, and the site
// served ten-day-old prices with no warning. staleness() drives the page's
// warning banner; the same maths runs server-side in check_freshness.py.

test('newestScanDate picks the maximum date and ignores unusable cells', () => {
  assert.equal(newestScanDate([{ date: '2026-09-10' }, { date: '2026-09-08' }, { date: '2026-09-11' }]), '2026-09-11');
  assert.equal(newestScanDate([{ date: '' }, { date: 'n/a' }, { date: '2026-09-09' }]), '2026-09-09');
  assert.equal(newestScanDate([]), null);
  assert.equal(newestScanDate(null), null);
});

test('staleness anchors the scan date to the 05:00 UTC cron hour', () => {
  // 2026-09-11 05:00 UTC -> 2026-09-12 09:00 UTC is 28 h old, not 33 h
  const now = Date.parse('2026-09-12T09:00:00Z');
  const s = staleness([{ date: '2026-09-11' }], now);
  assert.equal(s.newest, '2026-09-11');
  assert.equal(s.ageHours, 28);
  assert.equal(s.stale, false, 'one night of data is still acceptable');
  assert.equal(SCAN_HOUR_UTC, 5);
  assert.equal(STALE_AFTER_HOURS, 36);
});

test('staleness flags the missed-night case that froze the dataset for 10 days', () => {
  // the previous nightly died -> the newest row is two days old at check time
  const s = staleness([{ date: '2026-09-10' }], Date.parse('2026-09-12T09:00:00Z'));
  assert.equal(s.ageHours, 52);
  assert.equal(s.stale, true);
});

test('staleness boundary is exclusive and empty history is not "stale"', () => {
  const now = Date.parse('2026-09-12T09:00:00Z');
  assert.equal(staleness([{ date: '2026-09-11' }], now, 28).stale, false, 'exactly at the limit is fresh');
  assert.equal(staleness([{ date: '2026-09-11' }], now, 27.9).stale, true);
  const empty = staleness([], now);
  assert.deepEqual(empty, { newest: null, ageHours: null, stale: false });
});

test('the committed history.csv parses and yields a usable scan date', () => {
  const rows = toHistoryRows(historyText);
  assert.ok(rows.length > 100, 'history has rows');
  const newest = newestScanDate(rows);
  assert.match(newest, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(newest, rows.map(r => r.date).sort().at(-1), 'newest is the max scan date');
});


// --- expected-margin shortlist (mirror of ebay-search-skill/shortlist.py) ----
// The report (Python) and the page (JS) must agree: the same fixtures and
// expectations are asserted in tests/test_shortlist.py, and the two
// implementations were diffed field-by-field on the real CSVs (max numeric
// difference 0.0) when this was built. These tests keep them from drifting.

const SL_DATES = Array.from({ length: 11 }, (_, i) => `2026-09-${String(i + 1).padStart(2, '0')}`);
const SL_NEWEST = SL_DATES[SL_DATES.length - 1];

function slDeal(query, price) {
  return { query, price: String(price), title: 'listing', seller: 'seller',
           condition: 'Gebraucht', marketplace: 'EBAY_DE',
           url: `https://example.test/${query}/${price}` };
}
function slTracked(query, first, last, url) {
  return { url, query, marketplace: 'EBAY_DE', first_seen: first, last_seen: last,
           first_price: '100.00', last_price: '100.00' };
}
/** `aged` listings first seen on day 1; the first `gone` of them left. */
function slHist(query, aged, gone, prefix = 'h') {
  return Array.from({ length: aged }, (_, i) =>
    slTracked(query, SL_DATES[0], i < gone ? SL_DATES[1] : SL_NEWEST, `${prefix}${i}`));
}
const slPriced = (query, prices) => prices.map(p => slDeal(query, p));

test('scanDatesFrom collects sorted unique scan dates', () => {
  assert.deepEqual(scanDatesFrom([slTracked('RAM', '2026-09-05', '2026-09-07', 'a'),
                                  slTracked('RAM', '2026-09-01', '2026-09-07', 'b')]),
                   ['2026-09-01', '2026-09-05', '2026-09-07']);
});

test('marketChurn counts aged listings and those that left the market', () => {
  const rows = [slTracked('RAM', SL_DATES[0], SL_NEWEST, 'a'),   // aged 10, still listed
                slTracked('RAM', SL_DATES[0], SL_DATES[3], 'b'), // aged 10, gone
                slTracked('RAM', SL_DATES[8], SL_NEWEST, 'c')];  // aged 2 -> ignored
  const out = marketChurn(rows, SL_DATES);
  assert.equal(out.overall.aged, 2);
  assert.equal(out.overall.gone, 1);
  assert.equal(out.overall.rate, 0.5);
  assert.equal(out.byKey['EBAY_DE · RAM'].aged, 2);
  assert.equal(marketChurn([], SL_DATES).overall.rate, null, 'no history -> no rate');
});

test('estimateResale prefers a usable sold anchor and labels the fallback', () => {
  assert.deepEqual(estimateResale('RTX 3090', { 'RTX 3090': { median_sold: 1500, sample_size: 12 } }, 1200),
                   { price: 1500, source: 'sold median', sample: 12 });
  // an anchor without samples is not evidence
  assert.deepEqual(estimateResale('RTX 3090', { 'RTX 3090': { median_sold: 1500, sample_size: 0 } }, 1200),
                   { price: 1200, source: 'asking median', sample: 0 });
  assert.deepEqual(estimateResale('X', {}, null), { price: null, source: null, sample: 0 });
});

test('shortlist skips thin categories and never lists a negative margin', () => {
  const rows = slPriced('Thin', [10, 10, 10, 10]).concat(slPriced('Fat', [10, 100, 100, 100, 100]));
  const out = buildShortlist(rows, { listingRows: slHist('Fat', 10, 5), scanDates: SL_DATES, limit: 10 });
  assert.deepEqual(out.items.map(i => i.query), ['Fat']);
  assert.deepEqual(out.skipped.thinCategories, ['EBAY_DE · Thin']);

  const neg = buildShortlist(slPriced('Fat', [100, 100, 100, 100, 90]),
                             { listingRows: slHist('Fat', 10, 5), scanDates: SL_DATES });
  assert.deepEqual(neg.items, []);
  assert.equal(neg.skipped.negativeMargin, 5);
});

test('shortlist margin applies the fee to the resale estimate', () => {
  const out = buildShortlist(slPriced('Fat', [100, 200, 300, 400, 50]),
                             { listingRows: slHist('Fat', 10, 5), scanDates: SL_DATES, feeRate: 0.13, limit: 1 });
  const item = out.items[0];
  assert.equal(item.estResale, 200);           // median of 50..400
  assert.equal(item.price, 50);
  assert.ok(Math.abs(item.net - (200 * 0.87 - 50)) < 1e-9);
});

test('shortlist ranking is risk-adjusted, not just margin', () => {
  const rows = slPriced('Dead', [10, 100, 100, 100, 100]).concat(slPriced('Alive', [80, 100, 100, 100, 100]));
  const history = slHist('Dead', 10, 0, 'd').concat(slHist('Alive', 10, 9, 'a'));
  const out = buildShortlist(rows, { listingRows: history, scanDates: SL_DATES, limit: 2 });
  const byQuery = Object.fromEntries(out.items.map(i => [i.query, i]));
  assert.equal(byQuery.Dead.churn, 0);         // nothing ever leaves
  assert.equal(byQuery.Alive.churn, 0.9);      // its stock actually moves
  assert.ok(byQuery.Dead.net > byQuery.Alive.net, 'Dead has the bigger raw margin');
  assert.deepEqual(out.items.map(i => i.query), ['Alive', 'Dead']);
  assert.equal(out.items[0].rank, 1);
});

test('shortlist separates unproven categories from ranked ones', () => {
  const rows = slPriced('Fat', [10, 100, 100, 100, 100]);
  const history = slHist('Fat', 10, 0).concat(slHist('Other', 1, 1, 'o'));
  // minAged above both samples -> only the global rate is available -> unproven
  const out = buildShortlist(rows, { listingRows: history, scanDates: SL_DATES, minAged: 11, limit: 5 });
  assert.deepEqual(out.items, []);
  assert.deepEqual(out.unproven.map(u => u.query), ['Fat']);
  assert.equal(out.unproven[0].churnSource, 'global');
  assert.equal(out.unproven[0].rank, undefined, 'unproven entries are not ranked');

  const ranked = buildShortlist(rows, { listingRows: history, scanDates: SL_DATES, minAged: 5, limit: 5 });
  assert.deepEqual(ranked.items.map(i => i.query), ['Fat']);
  assert.equal(ranked.items[0].churnSource, 'category');
});

test('shortlist caps: two per category, and the limit and ranks hold', () => {
  const out = buildShortlist(slPriced('Fat', [10, 20, 30, 100, 100, 100]),
                             { listingRows: slHist('Fat', 10, 5), scanDates: SL_DATES, limit: 10 });
  assert.deepEqual(out.items.map(i => i.price), [10, 20]);

  const rows = [];
  let history = [];
  for (const name of ['A', 'B', 'C']) {
    rows.push(...slPriced(name, [10, 100, 100, 100, 100]));
    history = history.concat(slHist(name, 10, 5, name));
  }
  const limited = buildShortlist(rows, { listingRows: history, scanDates: SL_DATES, limit: 2 });
  assert.equal(limited.items.length, 2);
  assert.deepEqual(limited.items.map(i => i.rank), [1, 2]);
});

test('shortlist is safe with no rows and no history', () => {
  const out = buildShortlist([], {});
  assert.deepEqual(out.items, []);
  assert.deepEqual(out.unproven, []);
  assert.equal(out.skipped.negativeMargin, 0);
  assert.equal(SHORTLIST.DEFAULT_FEE_RATE, 0.13);
});

test('shortlist on the committed scan returns ranked, positive-margin items', () => {
  const rows = toRows(text);
  const out = buildShortlist(rows, { listingRows, feeRate: 0.13, limit: 10 });
  assert.ok(out.items.length > 0, 'the real scan yields a shortlist');
  out.items.forEach((item, i) => {
    assert.equal(item.rank, i + 1, 'ranks are sequential');
    assert.ok(item.net > 0, 'only positive margins are listed');
    assert.ok(item.estResale > 0);
    assert.equal(item.churnSource, 'category', 'ranked items have a measured churn rate');
  });
  for (let i = 1; i < out.items.length; i++) {
    assert.ok(out.items[i - 1].score >= out.items[i].score, 'sorted by risk-adjusted score');
  }
  const perCategory = {};
  for (const item of out.items) perCategory[item.query] = (perCategory[item.query] || 0) + 1;
  assert.ok(Object.values(perCategory).every(n => n <= SHORTLIST.MAX_PER_CATEGORY),
            'at most two items per category');
  out.unproven.forEach(u => assert.equal(u.rank, undefined));
});

// --- repo hygiene: generated data must be parseable, never conflicted ------
// Regression: a merge into main left "\u003c\u003c\u003c\u003c\u003c\u003c\u003c HEAD" markers inside
// site/data/deals/index.json (and two Marketplace sheets) and pushed them. The
// deployed page silently fell back to the single CSV and the €/GB map stopped
// hydrating from the manifest — no test noticed, because nothing parsed it.

test('no unresolved merge conflict markers anywhere under site/', () => {
  const offenders = [];
  const walk = dir => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) { walk(full); continue; }
      const text = readFileSync(full, 'utf8');
      text.split('\n').forEach((line, i) => {
        if (/^(\u003c{7}|={7}|\u003e{7})(\s|$)/.test(line)) {
          offenders.push(path.relative(siteDir, full) + ':' + (i + 1));
        }
      });
    }
  };
  walk(siteDir);
  assert.deepEqual(offenders, [], 'conflict markers found in: ' + offenders.join(', '));
});

test('the per-category chunk manifest parses and matches the files on disk', () => {
  const raw = readFileSync(path.join(dataDir, 'deals', 'index.json'), 'utf8');
  let manifest;
  assert.doesNotThrow(() => { manifest = JSON.parse(raw); }, 'index.json is not valid JSON');
  assert.ok(Array.isArray(manifest) && manifest.length > 0, 'manifest is empty');
  for (const entry of manifest) {
    assert.ok(entry.query && entry.file, 'manifest entry needs query + file');
    assert.ok(existsSync(path.join(dataDir, 'deals', entry.file)),
      'manifest lists a missing chunk: ' + entry.file);
    assert.ok(entry.rows == null || entry.rows >= 0, 'rows must be a count');
  }
});

// --- human-readable sanity summary (node --test shows it in the report) ---
{
  const { groups, flagged, total, queries } = analyze(toRows(text));
  console.log(`\n[summary] ${total} items across ${queries.length} categories, ${flagged.length} flagged deal(s)`);
  for (const g of groups) {
    console.log(`  ${g.query.padEnd(24)} n=${g.count.toString().padStart(3)}  median=${euro(g.median).padStart(12)}  cheapest=${euro(g.cheapest.price).padStart(12)}  atTarget=${g.atTargetCount}`);
  }
}
