# Base Data Row Selection Acceptance

Gate: `npm run verify:pce-base-data-row-selection` = PASS.

| Check | Result |
|---|---|
| Single row select | 1, PASS |
| Second row select | 2, PASS |
| Single row deselect | 1, PASS |
| Header select all | current visible page/scope, PASS |
| Header clear all | 0, PASS |
| Filtered selection scope | PASS |
| Missing generic `id`, primary identity fallback | PASS |
| Business writes | 0 |

Browser verification on Supplier (122 total, 20 rows/page) observed `1 → 2 → 1 → 20 → 0`. Only the header checkbox produced 20 selected rows.
