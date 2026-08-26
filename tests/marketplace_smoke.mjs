// marketplace_smoke.mjs — executes the board's render functions against a
// stub DOM to catch runtime errors (ReferenceError etc.) that a syntax check
// cannot. Run from the repo root:  node tests/marketplace_smoke.mjs
//
// The regression it guards: `openCell(r.url)` was called immediately (r
// undefined) instead of being wrapped as `r => openCell(r.url)` — the board
// crashed on any rendered search/watchlist row.

// --- stub DOM / browser globals (must exist before importing the module) ---
function makeEl() {
  const node = { children: [], _attrs: {}, _text: '', _html: '' };
  return new Proxy(node, {
    get(t, k) {
      if (k === 'appendChild') return c => { t.children.push(c); return c; };
      if (k === 'append') return (...cs) => { t.children.push(...cs); };
      if (k === 'setAttribute') return (name, val) => { t._attrs[name] = val; };
      if (k === 'textContent') return t._text;
      if (k === 'innerHTML') return t._html;
      return t[k];
    },
    set(t, k, v) {
      if (k === 'textContent') t._text = String(v);
      else if (k === 'innerHTML') t._html = String(v);
      else t[k] = v;
      return true;
    },
  });
}

global.document = {
  createElement: () => makeEl(),
  createTextNode: text => ({ nodeType: 3, textContent: String(text) }),
  getElementById: () => makeEl(),
};
// Note: Node 21+ provides its own read-only global navigator (language en-US),
// which is what marketplace.js reads when localStorage has no stored lang.
global.localStorage = { getItem: () => null, setItem: () => {} };
global.window = global;
// main() fetches the board CSVs; in Node these are relative URLs, so stub
// fetch to return "not found" — main() then exits early with empty data.
global.fetch = async () => ({ ok: false });
process.on('unhandledRejection', () => {});

const { renderWatchlist, renderSearches } = await import('../site/marketplace.js');

let failures = 0;
function check(name, fn) {
  try {
    fn();
    console.log(`  ok   ${name}`);
  } catch (err) {
    failures++;
    console.error(`  FAIL ${name}: ${err.message}`);
  }
}

const searchRow = {
  query: 'RTX 3090', country: 'DE', country_name: 'Germany', currency: 'EUR',
  city: 'cologne', url: 'https://www.facebook.com/marketplace/cologne/search/?query=RTX+3090&max=1100',
};
const itemRow = {
  type: 'item', item_id: '1234567890', url: 'https://www.facebook.com/marketplace/item/1234567890/',
  note: 'GPU seller', first_seen: '2026-08-26', last_seen: '2026-08-26',
};

check('renderSearches with rows (the regression)', () => renderSearches(makeEl(), [searchRow]));
check('renderSearches empty', () => renderSearches(makeEl(), []));
check('renderWatchlist items + searches', () => renderWatchlist(makeEl(), [itemRow, { ...searchRow, type: 'search', keyword: 'RTX 3090', location: 'cologne' }]));
check('renderWatchlist empty', () => renderWatchlist(makeEl(), []));

if (failures) {
  console.error(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nAll marketplace render checks passed');
