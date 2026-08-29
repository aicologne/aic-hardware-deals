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

// Capacity in GB per scan category. Only unambiguous categories get a value;
// mixed-capacity categories (e.g. Quadro RTX 8/16/24 GB) stay null.
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
