# Wave 1 Server Context Root Cause

- Instruction: `WAVE1-LATEST-TEMPLATE-DATA-PROVIDER-CONTINUITY-CORRECTIVE-20260911-001`
- User evidence ruling: `WAVE1 USER MANUAL VALIDATION = FAIL`; `REPORT VS USER REALITY CONFLICT = YES`.
- Frontend under review: `http://127.0.0.1:5174`.
- Actual backend: Vite same-origin `/api` proxy to `http://127.0.0.1:8000` (default because `PCE_API_PROXY_TARGET` was not overridden).
- API base URL: empty/same-origin because `VITE_API_BASE_URL` was not set.
- Backend reachability: PASS. Protected endpoints returned `401 not_authenticated` without a valid browser identity and `200` under the authenticated read-only runner.
- Identity/scope: the failed browser session had no usable server JWT; authenticated evidence resolves company scope `1` for PDE and the established enterprise-master scope for Customer/Supplier.

## Exact source and chain

`server-context-unavailable` is created by `frontend/src/meta/runtime/pceFactLoadContract.js` when no successful server response has populated `lastServerFactContext`. The old startup contract allowed an unauthenticated browser to open formal master-data routes. The request then received HTTP 401, and the failure formatter had no remembered tenant/batch context, so the UI surfaced `server-context-unavailable`. This is an authentication/context lifecycle defect, not evidence that the backend or database is absent.

Page → latest-template shell → formal provider → Axios adapter → server-context contract → same-origin `/api` → Vite proxy `8000` → missing browser authentication → backend 401 → database not queried.

## A–J classification

| Candidate | Result | Evidence |
|---|---|---|
| A Backend not running | REJECTED | Port 8000 responded; authenticated formal GETs returned 200. |
| B Frontend 5174 points to wrong backend | REJECTED | Vite default proxy target is 127.0.0.1:8000 and that backend owns the verified DB. |
| C API base URL missing | REJECTED | Same-origin base URL is intentional and proxy-backed. |
| D Vite proxy/runtime config invalid | REJECTED | `/api` requests reached 8000; controlled 5175→8001 copy also passed. |
| E Server Context Provider not initialized | CONFIRMED (secondary) | Context is remembered only after a successful authenticated response; the failed session never reached that point. |
| F Identity/org context missing | CONFIRMED (primary) | Unauthenticated calls returned 401; valid JWT resolved tenant/company and loaded rows. |
| G Page meta lacks formal provider | REJECTED | All 27 registry mappings pass entity/model/route checks. |
| H API adapter not connected | REJECTED | Customer/Supplier enterprise adapters and PDE A1 adapter returned formal responses. |
| I Formal endpoint absent | REJECTED | All in-scope endpoints returned 200 when authenticated. |
| J Other | CONFIRMED | Formal routes previously had no authentication guard, allowing an invalid runtime to look like a data-empty page. |

## Corrective behavior

The router now redirects canonical formal master-data routes to `/login` when no usable server JWT exists. Shared request authentication recognizes only usable JWTs. The two formal page shells retain their full table/capability structure during failure and expose one of seven explicit provider states. PDE A1 successful GETs now carry tenant, batch and fact-load context.

This resolves the shared technical root cause. Overall Wave 1 remains blocked until the user repeats manual validation and explicitly records PASS.
