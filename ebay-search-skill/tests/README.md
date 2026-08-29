# Skill unit tests

Zero-dependency unit tests (Python stdlib `unittest` — no pytest needed) for
the `ebay-search-skill` modules. They cover the pure logic: deal-window math,
alert/message building, report helpers, price parsing, item normalization,
CSV writers and the history trackers.

## Run

From the skill directory (`ebay-search-skill/`):

```bash
python -m unittest discover -s tests -v        # all tests
python tests/test_windows.py                   # single file
```

Everything is offline: network calls (`fetch_sold_prices`, `http_post`,
`search`) and the HTTP relay handler are not exercised; the modules under test
are imported with no credentials required.

## Coverage

| File | What it pins |
|---|---|
| `test_windows.py` | `num`, `percentile` (linear interpolation), `adaptive_window` (floor/ceil/spike guard), `load_recent_medians`, `window_for_query` |
| `test_notify.py` | buy-low flag rule, state JSON roundtrip, `build_message`/`build_drop_message` layout + MAX_ITEMS cap, `drop_rows` detection/sorting/threshold |
| `test_render_report.py` | German `euro`/`pct` formatting, net price after fee, flag rules, €/GB capacity map, history/trend/movers math, sold anchors, repriced notes |
| `test_render_feed.py` | `xmlesc`, euro formatting, repriced notes |
| `test_sold_anchors.py` | price-cell normalization and `parse_price` (German/US/UK formats, foreign-currency rejection) |
| `test_ebay_search.py` | realm auto-detection, `parse_item` (condition object/string/missing), client-side filters, env-file loading, CSV writer, demo scan |
| `test_render_history.py` | `main()` end-to-end: medians, idempotent same-date reruns, MAX_DAYS prune |
| `test_render_listing_history.py` | `main()` end-to-end: first/last price tracking, repricing count, stale prune, MAX_ROWS cap |
| `test_ebay_relay.py` | env candidate discovery, token cache fetch/reuse/expiry, sandbox URL selection |

## CI

Add a step to the workflow of your choice, e.g.:

```yaml
- name: Skill unit tests
  run: |
    cd ebay-search-skill
    python -m unittest discover -s tests -v
```
