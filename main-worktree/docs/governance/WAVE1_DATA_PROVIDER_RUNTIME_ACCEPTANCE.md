# Wave 1 Data Provider Runtime Acceptance

## Environments

- Actual user runtime: frontend `http://127.0.0.1:5174`, same-origin API, Vite proxy → backend `http://127.0.0.1:8000`.
- Controlled acceptance: frontend `http://127.0.0.1:5175`, Vite proxy → backend `http://127.0.0.1:8001`, using a fresh isolated copy of the current formal SQLite database.
- Browser automation used the repository's established authentication runner; credentials are omitted. Login/session metadata was confined to the isolated copy.
- After authentication and before/after all formal GETs, the isolated DB SHA-256 was unchanged. Business write request count: 0.

During earlier diagnosis against 5174, the normal login endpoint created authentication/session metadata in the current database, so the whole SQLite file hash changed from `CE84DCFE...` to `CF6054C8...`. No master/business table count changed, and no recovery/import/migration write occurred. The final controlled evidence moved authentication to the isolated copy precisely to keep the formal business read phase write-free.

## Results

`npm run verify:pce-wave1-provider-runtime` passed the unauthenticated formal-route login guard and 23 latest-template list pages. Key counts: Customer 89; Supplier 121; Material 270; Product Definition 0; Product Category 3; Manufacturing Process Type 14; Routing 42; Routing Version 42; Routing Step 1137; Engineering Source Record 1; Workshop 3; Work Center 0; Operation 33; Equipment 0; Standard Capacity 0. Every positive collection was `LOADED_WITH_DATA`; every zero collection was `LOADED_EMPTY`; all API/UI totals and available sample identities matched.

The direct in-app-browser readback of the controlled origin was blocked by the user's saved browser permission and was not bypassed. Headless Chrome runtime evidence is retained in `WAVE1_PROVIDER_UI_RUNTIME.json`. The user's prior five screenshots remain controlling manual evidence and keep the overall result FAIL until explicit revalidation.

## Manual validation handoff

`MANUAL WAVE1 DATA CONTINUITY VALIDATION READY` is a technical handoff, not a PASS declaration.

| Page / menu path | URL | Expected total / identity | Expected capabilities | Import |
|---|---|---|---|---|
| Customer | `http://127.0.0.1:5174/#/master-data/customers` | 89 / `CUST-PCE-ACCEPT-001` | Search, advanced filter, sort, export, pagination, process navigation | Disabled/pending |
| Supplier | `http://127.0.0.1:5174/#/master-data/suppliers` | 121 / `SUP001` | Same latest-template toolbar set | Disabled/pending |
| Material | `http://127.0.0.1:5174/#/foundation/master-data/materials` | 270 / `MT001` | Same latest-template toolbar set | Template/import visible; disabled/pending |
| Product Definition | `http://127.0.0.1:5174/#/foundation/master-data/products` | 0, `LOADED_EMPTY` | Full structure remains visible | Disabled/pending |
| Product Engineering children | `/foundation/master-data/product-categories`, `/manufacturing-process-types`, `/routings` | 3, 14, 42 (Routing Step 1137) | Full latest-template list shell | Backend pending where shown |
| Manufacturing Resource | `/foundation/master-data/workshops`, `/work-centers`, `/operations`, `/equipment`, `/standard-capacities` | 3/0/33/0/0 | Full latest-template list shell | Disabled/pending |

Expected successful pages show API, tenant/company and batch facts. A login prompt is expected when the browser has no usable server identity; a failed provider must show an explicit failure state, never a misleading zero total.
