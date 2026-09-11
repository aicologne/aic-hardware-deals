// csv.js — pure CSV parsing + report statistics (no DOM).
// Shared by app.js (browser) and tests/stats.test.mjs (Node).
// Mirrors the logic of render_report.py so the HTML report and LATEST.md stay consistent.

/** RFC-4180-style parser: quoted fields, escaped quotes (""), CRLF. */
export function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  const s = String(text);
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inQuotes) {
      if (c === '"') {
        if (s[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ',') {
      row.push(field); field = '';
    } else if (c === '\n') {
      row.push(field); field = '';
      rows.push(row); row = [];
    } else if (c === '\r') {
      // ignore CR; the following \n terminates the record
    } else {
      field += c;
    }
  }
  if (field.length > 0 || row.length > 0) { row.push(field); rows.push(row); }
  return rows.filter(r => r.some(c => c.trim() !== ''));
}

/** First record = header; rest become objects keyed by header name. */
export function toRows(text) {
  const table = parseCSV(text);
  if (!table.length) return [];
  const headers = table[0].map(h => h.trim());
  return table.slice(1)
    .map(cells => {
      const o = {};
      headers.forEach((h, i) => { o[h] = (cells[i] ?? '').trim(); });
      return o;
    })
    .filter(r => r.query && r.title);
}

/** Like toRows, but for schemas without a title column (e.g. data/history.csv). */
export function toHistoryRows(text) {
  const table = parseCSV(text);
  if (!table.length) return [];
  const headers = table[0].map(h => h.trim());
  return table.slice(1)
    .map(cells => {
      const o = {};
      headers.forEach((h, i) => { o[h] = (cells[i] ?? '').trim(); });
      return o;
    })
    .filter(r => r.date && r.query);
}

/** Parse any CSV into objects with no required columns (e.g. listing_history.csv). */
export function toAnyRows(text) {
  const table = parseCSV(text);
  if (!table.length) return [];
  const headers = table[0].map(h => h.trim());
  return table.slice(1)
    .map(cells => {
      const o = {};
      headers.forEach((h, i) => { o[h] = (cells[i] ?? '').trim(); });
      return o;
    })
    .filter(r => Object.values(r).some(v => v !== ''));
}

export function num(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : null;
}

/** German-style price: €1.234,56 (same formatting as render_report.py). */
export function euro(v) {
  const n = num(v);
  if (n == null) return '—';
  return '€' + n.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function median(values) {
  const a = values.filter(v => num(v) != null).map(num).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

export function flagFor(r) {
  const price = num(r.price);
  const wmin = num(r.win_min);
  const wmax = num(r.win_max);
  if (price == null) return 'ok';
  if (wmin != null && price <= wmin * 1.15) return '🔥 at/near buy-low target';
  if (wmax != null && price > wmax) return '⚠️ above scan window';
  return 'ok';
}

// --- marketplace + composite grouping --------------------------------------

export const DEFAULT_MARKETPLACE = 'EBAY_DE';

export function marketplaceOf(r) {
  const mp = (r.marketplace || '').trim();
  return mp || DEFAULT_MARKETPLACE;
}

/** Composite group key: "EBAY_DE · DDR4 RDIMM 32GB" (marketplace · query). */
export function groupKey(r) {
  return `${marketplaceOf(r)} · ${r.query}`;
}

// --- €/GB value metric ------------------------------------------------------

// Capacity in GB per scan category. Single source of truth: queries.py
// (`capacity_gb` field) -> split_deals.py writes it into data/deals/index.json,
// and app.js hydrates this map at runtime. The entries below are only a
// FALLBACK for the single-CSV mode and unit tests; new products need no
// front-end edit. Mixed-capacity categories (e.g. Quadro RTX 8/16/24 GB)
// stay absent and render "—".
export const CAPACITY_GB = {
  'RTX 3090': 24,
  'RTX 3090 Ti': 24,
  'RTX 4070 Ti Super': 16,
  'RTX 4080 Super': 16,
  'RTX 5070 16GB': 16,
  'Tesla P40': 24,
  'DDR4 RDIMM 32GB': 32,
  'DDR4 RDIMM 64GB': 64,
  'DDR5 32GB': 32,
};

export function euroPerGb(price, query) {
  const cap = CAPACITY_GB[query];
  if (cap == null) return null;
  const n = num(price);
  return n == null ? null : n / cap;
}

// --- data freshness ---------------------------------------------------------
// Mirror of ebay-search-skill/check_freshness.py. The newest scan date in
// data/history.csv is anchored to the hour the nightly cron runs (05:00 UTC)
// before its age is computed, so a date-only column cannot look up to a day
// fresher than it actually is. The workflow guard fails the build past its own
// limit; the page shows a warning past STALE_AFTER_HOURS.

export const SCAN_HOUR_UTC = 5;
export const STALE_AFTER_HOURS = 36;

/** Newest "YYYY-MM-DD" among history rows (null when there is none). */
export function newestScanDate(rows) {
  let newest = null;
  for (const r of rows || []) {
    const d = String((r && r.date) || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) continue;   // ISO dates sort lexicographically
    if (newest === null || d > newest) newest = d;
  }
  return newest;
}

/** { newest, ageHours, stale } for the newest scan date (ageHours null if none). */
export function staleness(rows, nowMs = Date.now(), maxAgeHours = STALE_AFTER_HOURS) {
  const newest = newestScanDate(rows);
  if (!newest) return { newest: null, ageHours: null, stale: false };
  const [y, m, d] = newest.split('-').map(Number);
  const ageHours = (nowMs - Date.UTC(y, m - 1, d, SCAN_HOUR_UTC)) / 3600000;
  return { newest, ageHours, stale: ageHours > maxAgeHours };
}

// --- history + movers -------------------------------------------------------

function parseDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}

/** Build a chronological, date-deduped median series for one composite key. */
export function historySeries(rows, key) {
  const pts = rows
    .filter(r => groupKey(r) === key && num(r.median) != null)
    .map(r => ({ date: r.date, median: num(r.median) }))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const byDate = new Map();
  for (const p of pts) byDate.set(p.date, p.median);
  return [...byDate].map(([date, median]) => ({ date, median }));
}

/**
 * Recent median movers: [{key, latest, ref, refDate, delta}] sorted by
 * |delta| desc. Reference = the earliest scan at-or-after 7 days before the
 * latest scan (falls back to the previous scan for fresh history).
 */
export function movers(history) {
  const out = [];
  for (const key of Object.keys(history)) {
    const pts = history[key];
    if (!pts || pts.length < 2) continue;
    const latest = pts[pts.length - 1].median;
    const latestDate = parseDate(pts[pts.length - 1].date) || new Date();
    const threshold = new Date(latestDate.getTime() - 7 * 86400000);
    let ref = null;
    let refDate = null;
    for (let i = 0; i < pts.length - 1; i++) {
      const d = parseDate(pts[i].date);
      if (d && d >= threshold) { ref = pts[i].median; refDate = pts[i].date; break; }
    }
    if (ref == null) { ref = pts[pts.length - 2].median; refDate = pts[pts.length - 2].date; }
    if (ref == null || ref <= 0) continue;
    out.push({ key, latest, ref, refDate, delta: ((latest - ref) / ref) * 100 });
  }
  out.sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
  return out;
}

/** Aggregate index: mean of per-key median deltas (null when no movers). */
export function indexPct(moversArr) {
  if (!moversArr || !moversArr.length) return null;
  return moversArr.reduce((sum, m) => sum + m.delta, 0) / moversArr.length;
}

// --- grouping ---------------------------------------------------------------

/** Group rows by composite key and compute per-category stats + the flagged shortlist. */
export function analyze(rows) {  const valid = rows.filter(r => num(r.price) != null);
  const marketplaces = [...new Set(valid.map(marketplaceOf))].sort();
  const single = marketplaces.length <= 1;
  const byKey = new Map();
  for (const r of valid) {
    const key = groupKey(r);
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(r);
  }
  const keys = [...byKey.keys()].sort();
  const groups = keys.map(key => {
    const qrows = byKey.get(key).slice().sort((a, b) => num(a.price) - num(b.price));
    const prices = qrows.map(r => num(r.price));
    const wmin = num(qrows[0].win_min);
    const wmax = num(qrows[0].win_max);
    const first = qrows[0] || {};
    return {
      key,
      mp: marketplaceOf(first),
      query: first.query || key,        // base query name (filter + single-marketplace display)
      display: single ? (first.query || key) : key,
      rows: qrows,
      count: qrows.length,
      median: median(prices),
      cheapest: qrows[0],
      wmin,
      wmax,
      atTargetCount: qrows.filter(r => flagFor(r) === '🔥 at/near buy-low target').length,
    };
  });
  const flagged = valid
    .filter(r => flagFor(r) === '🔥 at/near buy-low target')
    .sort((a, b) => num(a.price) - num(b.price));
  return { rows: valid, marketplaces, single, queries: keys, groups, flagged, total: valid.length };
}

/**
 * Cap the deal-highlights shortlist: at most `max` rows total, but always
 * at least ONE row per category (the cheapest flagged deal of each category
 * is guaranteed a slot; the remaining slots are the next cheapest flagged
 * deals overall).
 */
export function topDeals(flagged, max = 20) {
  const byQuery = new Map();
  for (const r of flagged) {
    if (!byQuery.has(r.query)) byQuery.set(r.query, []);
    byQuery.get(r.query).push(r);
  }
  const picks = [];
  for (const rows of byQuery.values()) picks.push(rows[0]); // one per category (cheapest, since flagged is price-sorted)
  const seen = new Set(picks);
  for (const r of flagged) {
    if (picks.length >= max) break;
    if (!seen.has(r)) { seen.add(r); picks.push(r); }
  }
  return picks;
}

// --- expected-margin shortlist ---------------------------------------------
// Mirror of ebay-search-skill/shortlist.py: same constants, same arithmetic
// order, so the report and the page agree to the cent (pinned by
// tests/test_shortlist.py and tests/stats.test.mjs on both sides).
//
// Why: the 🔥 flag marks anything within 15 % of an adaptive buy-low target —
// 85 of 603 listings (14 %) across 20 of 25 categories on 2026-09-11, which is
// not a shortlist. What matters is
//
//     margin = resale estimate * (1 - feeRate) - asking
//
// weighted by **market churn**: the share of that category's tracked listings
// that left the market. "Left" means sold *or* withdrawn — the tool cannot tell
// them apart, so it is a rate, not a probability, and every margin here is a
// ceiling rather than a promise.

export const SHORTLIST = {
  MIN_LISTINGS: 5,       // below this a category median is noise, not a market
  MIN_AGE_SCANS: 5,      // a listing must be observable this long to count as aged
  MIN_AGED: 8,           // below this the global churn rate is used instead
  DEFAULT_LIMIT: 10,
  MAX_PER_CATEGORY: 2,
  UNPROVEN_LIMIT: 3,
  DEFAULT_FEE_RATE: 0.13,
};

/** Sorted unique scan dates seen in the per-listing history. */
export function scanDatesFrom(listingRows) {
  const dates = new Set();
  for (const r of listingRows || []) {
    for (const field of ['first_seen', 'last_seen']) {
      const value = String((r && r[field]) || '').trim();
      if (value) dates.add(value);
    }
  }
  return [...dates].sort();
}

/** How often tracked listings leave the market — overall and per category. */
export function marketChurn(listingRows, scanDates, minAgeScans = SHORTLIST.MIN_AGE_SCANS) {
  const dates = scanDates || scanDatesFrom(listingRows);
  const index = new Map(dates.map((d, i) => [d, i]));
  const newestIndex = dates.length - 1;
  const newest = dates[newestIndex];
  const overall = { aged: 0, gone: 0, rate: null };
  const byKey = {};
  for (const r of listingRows || []) {
    const first = String((r && r.first_seen) || '').trim();
    const last = String((r && r.last_seen) || '').trim();
    if (!index.has(first) || !last) continue;
    if (newestIndex - index.get(first) < minAgeScans) continue;
    const key = groupKey(r);
    const bucket = byKey[key] || (byKey[key] = { aged: 0, gone: 0, rate: null });
    for (const target of [bucket, overall]) {
      target.aged += 1;
      if (last !== newest) target.gone += 1;
    }
  }
  for (const bucket of [...Object.values(byKey), overall]) {
    if (bucket.aged) bucket.rate = bucket.gone / bucket.aged;
  }
  return { overall, byKey };
}

/** Resale estimate for one category: sold anchor if usable, else asking median. */
export function estimateResale(query, soldAnchors, categoryMedian, minSample = 1) {
  const anchor = soldAnchors ? soldAnchors[query] : null;
  if (anchor) {
    const medianSold = num(anchor.median_sold);
    const sample = Number.isFinite(+anchor.sample_size) ? Math.trunc(+anchor.sample_size) : 0;
    if (medianSold != null && sample >= minSample) {
      return { price: medianSold, source: 'sold median', sample };
    }
  }
  if (categoryMedian == null) return { price: null, source: null, sample: 0 };
  return { price: categoryMedian, source: 'asking median', sample: 0 };
}

/**
 * Rank listings by margin * market churn.
 * -> { items: [...] (ranked, own churn measurement),
 *      unproven: [...] (positive margin, liquidity not measurable yet),
 *      skipped: { thinCategories, negativeMargin },
 *      churn, estimatedFrom: { sold, asking } }
 */
export function buildShortlist(rows, options = {}) {
  const {
    soldAnchors = null, listingRows = [], scanDates = null,
    feeRate = SHORTLIST.DEFAULT_FEE_RATE, limit = SHORTLIST.DEFAULT_LIMIT,
    minListings = SHORTLIST.MIN_LISTINGS, minAged = SHORTLIST.MIN_AGED,
    maxPerCategory = SHORTLIST.MAX_PER_CATEGORY, unprovenLimit = SHORTLIST.UNPROVEN_LIMIT,
  } = options;

  const churn = marketChurn(listingRows, scanDates);
  const overall = churn.overall;

  const groups = new Map();
  for (const r of rows || []) {
    if (num(r.price) == null) continue;
    const key = groupKey(r);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  }

  const thinCategories = [];
  const candidates = [];
  const estimatedFrom = { sold: 0, asking: 0 };
  let negativeMargin = 0;

  for (const [key, group] of groups) {
    const prices = group.map(r => num(r.price)).sort((a, b) => a - b);
    if (prices.length < minListings) { thinCategories.push(key); continue; }
    const categoryMedian = median(prices);
    const query = group[0].query || '';
    const est = estimateResale(query, soldAnchors, categoryMedian);

    const bucket = churn.byKey[key] || { aged: 0, gone: 0, rate: null };
    let weight, weightSource;
    if (bucket.aged >= minAged && bucket.rate != null) { weight = bucket.rate; weightSource = 'category'; }
    else if (overall.rate != null && overall.aged >= minAged) { weight = overall.rate; weightSource = 'global'; }
    else { weight = 1.0; weightSource = 'unknown'; }

    for (const r of group) {
      const price = num(r.price);
      const net = est.price * (1 - feeRate) - price;
      if (!(net > 0)) { negativeMargin += 1; continue; }
      candidates.push({
        query,
        marketplace: marketplaceOf(r),
        price,
        estResale: est.price,
        estSource: est.source,
        estSample: est.sample,
        net,
        churn: weight,
        churnSource: weightSource,
        aged: bucket.aged,
        score: net * weight,
        title: r.title || '',
        url: r.url || '',
        seller: r.seller || '',
        condition: r.condition || '',
      });
    }
  }

  candidates.sort((a, b) =>
    (b.score - a.score) || (b.net - a.net) || (a.price - b.price) ||
    (a.query < b.query ? -1 : a.query > b.query ? 1 : 0));

  // Only categories whose own listings have been watched long enough to read a
  // churn rate are ranked; the rest are real but unproven and cannot compete
  // for the top slot (e.g. Mac Studio Ultra: n=6, one aged listing, a median
  // that swings 27 % on a single row).
  const items = [];
  const unproven = [];
  const perCategory = new Map();
  for (const c of candidates) {
    const used = perCategory.get(c.query) || 0;
    if (used >= maxPerCategory) continue;
    if (c.churnSource !== 'category') {
      if (unproven.length < unprovenLimit) { unproven.push({ ...c }); perCategory.set(c.query, used + 1); }
      continue;
    }
    if (items.length >= limit) continue;
    perCategory.set(c.query, used + 1);
    if (c.estSource === 'sold median') estimatedFrom.sold += 1;
    else if (c.estSource === 'asking median') estimatedFrom.asking += 1;
    items.push({ ...c, rank: items.length + 1 });
  }

  return {
    items,
    unproven,
    skipped: { thinCategories: thinCategories.sort(), negativeMargin },
    churn,
    estimatedFrom,
    feeRate,
  };
}

