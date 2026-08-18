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

/** Build a chronological, date-deduped median series for one query (history.csv rows). */
export function historySeries(rows, query) {
  const pts = rows
    .filter(r => r.query === query && num(r.median) != null)
    .map(r => ({ date: r.date, median: num(r.median) }))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  const byDate = new Map();
  for (const p of pts) byDate.set(p.date, p.median);
  return [...byDate].map(([date, median]) => ({ date, median }));
}

/** Group rows by query and compute per-category stats + the flagged shortlist. */
export function analyze(rows) {
  const valid = rows.filter(r => num(r.price) != null);
  const byQuery = new Map();
  for (const r of valid) {
    if (!byQuery.has(r.query)) byQuery.set(r.query, []);
    byQuery.get(r.query).push(r);
  }
  const queries = [...byQuery.keys()].sort();
  const groups = queries.map(q => {
    const qrows = byQuery.get(q).slice().sort((a, b) => num(a.price) - num(b.price));
    const prices = qrows.map(r => num(r.price));
    const wmin = num(qrows[0].win_min);
    const wmax = num(qrows[0].win_max);
    return {
      query: q,
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
  return { rows: valid, queries, groups, flagged, total: valid.length };
}
