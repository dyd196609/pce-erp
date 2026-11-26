# BASE DATA TEMPLATE NON-REGRESSION GATES

Two build-blocking commands are registered in `frontend/package.json` and run at the start of `npm run build`:

- `npm run verify:pce-latest-base-data-template-adoption`
- `npm run verify:pce-base-data-capability-non-regression`

The adoption gate verifies authority files, exact canonical scope parity, version declarations, adoption statuses, formal model/API/route evidence and the prohibition on legacy fallback.

The capability gate verifies export, advanced-filter toggle, shared import-template/import extension, fixed header, pagination, advanced filter, process navigation, page identity, formal import-chain closure and production-write prohibition. It also keeps the rejected `localStorage` legacy evidence visible so any attempted authority reassessment fails closed.

Historical routing and operation modules remain `ADOPTING_PROTECTED_BASELINE`; this change does not alter their data, routes, mode semantics or actions. Supplier/Procurement recovery is excluded.
