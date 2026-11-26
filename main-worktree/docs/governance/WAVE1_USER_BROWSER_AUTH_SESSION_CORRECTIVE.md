# Wave 1 User Browser Auth Session Corrective — Final Consolidated

Date: 2026-09-11

Instruction ID: `WAVE1-USER-BROWSER-AUTH-SESSION-CORRECTIVE-20260911-001`

Review Level: C

## 1. Decision

`USER MANUAL WAVE1 DATA CONTINUITY VALIDATION = PASS`

`WAITING_FOR_USER_MANUAL_ACCEPTANCE = NO`

The user explicitly accepted the fresh isolated authenticated run. The earlier user-visible FAIL remains historical evidence and is superseded for the nine listed modules by the 2026-09-11 manual PASS. Import Backend remains pending, so no module is promoted to `ADOPTED`.

## 2. Root cause disposition

| Investigation item | Result | Evidence / conclusion |
|---|---|---|
| Automated identity existed only in the Headless context | CONFIRMED | The prior runner authenticated its own isolated Browser Context. Browser storage is not shared across browser profiles. |
| User browser never completed formal Login | CONFIRMED | User-visible requests were anonymous and returned 401; the ordinary browser had no valid principal. |
| JWT existed only in automated Browser Storage | CONFIRMED | JWT is stored under the current origin's `localStorage.token`; storage is profile/context scoped. |
| Session Cookie was bound to the automated browser profile | CONFIRMED | Django `sessionid` is a browser-profile cookie and was absent from the user's failed context. |
| localhost host/port cookie scope caused the failure | REJECTED | The corrected run uses `127.0.0.1:5174` with same-origin `/api` proxying to `127.0.0.1:8000`; the formal login issued a usable session cookie. |
| Token/session expiry caused the failure | REJECTED | The failed user context had no established credential. The new JWT has the configured 24-hour validity window. |
| rehearsal reader had not established a user browser session | CONFIRMED | The prior credential was never entered through the user's browser Login page. |
| Authentication Bootstrap was absent | REJECTED AS ROOT CAUSE | The canonical-route guard, Login endpoint, JWT persistence and request interceptor are present and passed. Direct Login lands on Dashboard; explicit menu navigation is therefore supplied. |

## 3. Formal authentication mechanism

- Login entry: `http://127.0.0.1:5174/#/login`.
- Login endpoint: `POST /api/auth/login/` through the frontend same-origin proxy.
- Principal: Django custom `system.User` in the isolated rehearsal database.
- API authentication: server-signed JWT in `Authorization: Bearer ...`.
- Browser bootstrap storage: JWT in `localStorage.token` for origin `http://127.0.0.1:5174`.
- Session authentication: Django `sessionid` Cookie in the same visible browser profile.
- Manual token, Cookie, DevTools, JavaScript or CDP identity injection: none.

## 4. Fresh run inventory

- Run ID: `WAVE1-AUTH-20260911-120000-CST`.
- Frontend URL: `http://127.0.0.1:5174/`.
- Backend URL: `http://127.0.0.1:8000/`.
- Rehearsal DB: `C:\Users\DAODA\Documents\Codex\pce-runtime\WAVE1-AUTH-20260911-120000-CST\wave1-auth-isolated.sqlite3`.
- Rehearsal user: `wave1_rehearsal_reader_20260911`.
- Password/token: intentionally omitted from Git and governance evidence; supplied only in the current user handoff.
- Session validity: 24 hours from formal Login; the delivered JWT expires at 2026-09-12 12:50:39 CST.
- Frontend listening PID: `18292`.
- Backend listening PID: `40004`.
- Browser profile: isolated under the Run directory; it is not the user's Production browser profile.
- Backend check: PASS.
- Frontend HTTP 200: PASS.

## 5. Identity and permission gate

The rehearsal identity is active, non-staff and non-superuser. It has zero Django groups, zero direct permissions and zero role-scope assignments.

| Gate | Result | Evidence |
|---|---|---|
| Login Endpoint | PASS | Formal login returned HTTP 200. |
| Rehearsal User | VALID | Django user ID 14; active; not staff; not superuser. |
| Read Permissions | PASS | All nine required formal read endpoints returned HTTP 200 after formal Login. |
| Write/Execute Permissions | DENY | `SAVE_DEPARTMENT` against the formal organization maintenance boundary returned HTTP 403 / `PERMISSION_DENIED`; DB hash was unchanged across the denial. |
| Browser Authentication Bootstrap | PASS | Visible Chrome had both a JWT in the origin storage and a Django Session Cookie after form Login. |
| Authenticated `/api` Call | PASS | Required target endpoints returned HTTP 200. |
| Unauthenticated `/api` Call | PASS | Customer facts returned HTTP 401 before Login. |
| Session/JWT Expiry | PASS | Configured 24-hour JWT window; valid for the manual acceptance window. |
| Frontend 5174 | PASS | HTTP 200 and runtime identity endpoint HTTP 200. |
| Backend | HEALTHY | Django system check: zero issues; port 8000 listening. |

## 6. DB/API/visible-browser readback

| Module | API | Visible Chrome | Provider state | Ready result |
|---|---:|---:|---|---|
| Customer | 89 | 89 | `LOADED_WITH_DATA` | PASS |
| Supplier | 121 | 121 | `LOADED_WITH_DATA` | PASS |
| Material | 270 | 270 | `LOADED_WITH_DATA` | PASS |
| Product Definition | 0 | 0 | `LOADED_EMPTY` | PASS |
| Workshop | 3 | 3 | `LOADED_WITH_DATA` | PASS |
| Operation | 33 | 33 | `LOADED_WITH_DATA` | PASS |
| Work Center | 0 | 0 | `LOADED_EMPTY` | PASS |
| Equipment | 0 | 0 | `LOADED_EMPTY` | PASS |
| Standard Capacity | 0 | 0 | `LOADED_EMPTY` | PASS |

The visible browser contained none of these failure strings on any target page: `server-context-unavailable`, `身份认证失败`, `请重新登录后读取正式数据`, `企业基础资料服务端事实读取失败`.

## 7. User manual navigation and expected values

1. Login: `http://127.0.0.1:5174/#/login` → enter the supplied rehearsal credentials → `Enter ProfitOS`.
2. Customer: 企业基础资料 → 物料与供应 → 客户 / 经销商. Direct URL: `http://127.0.0.1:5174/#/master-data/customers`. Expected: 89.
3. Supplier: 企业基础资料 → 物料与供应 → 供应商. Direct URL: `http://127.0.0.1:5174/#/master-data/suppliers`. Expected: 121.
4. Material: 企业基础资料 → 物料与供应 → 物料档案. Direct URL: `http://127.0.0.1:5174/#/foundation/master-data/materials`. Expected: 270.
5. Product Definition: 企业基础资料 → 产品工程 → 产品定义. Direct URL: `http://127.0.0.1:5174/#/foundation/master-data/products`. Expected: 0 and `LOADED_EMPTY / 暂无正式数据`.
6. Workshop: 企业基础资料 → 制造资源 → 车间 / 生产区域. Direct URL: `http://127.0.0.1:5174/#/foundation/master-data/workshops`. Expected: 3.
7. Operation: 企业基础资料 → 制造资源 → 工序. Direct URL: `http://127.0.0.1:5174/#/foundation/master-data/operations`. Expected: 33.
8. Work Center: 企业基础资料 → 制造资源 → 工作中心. Direct URL: `http://127.0.0.1:5174/#/foundation/master-data/work-centers`. Expected: 0 and `LOADED_EMPTY / 暂无正式数据`.
9. Equipment: 企业基础资料 → 制造资源 → 设备资料. Direct URL: `http://127.0.0.1:5174/#/foundation/master-data/equipment`. Expected: 0 and `LOADED_EMPTY / 暂无正式数据`.
10. Standard Capacity: 企业基础资料 → 制造资源 → 标准产能. Direct URL: `http://127.0.0.1:5174/#/foundation/master-data/standard-capacities`. Expected: 0 and `LOADED_EMPTY / 暂无正式数据`.

## 8. Template capability state

- Static capability non-regression gate: PASS.
- Latest template authority: `PCE-LATEST-BASE-DATA-TEMPLATE-V1.0`, scope 27, PASS.
- Provider-continuity mappings: 27, PASS.
- Preserved capabilities: search, advanced filter, sorting, export, pagination, process navigation, governed table columns and single horizontal-scroll ownership.
- Import Template: preserved where applicable; no separate user PASS is asserted.
- Import: remains disabled where backend implementation is pending.
- Import-related adoption state: `ADOPTING_IMPORT_BACKEND_PENDING`; not `ADOPTED`.
- Final capability acceptance: user PASS for Search, Advanced Filter, Sort, Pagination, Process Navigation, Table/Horizontal Scroll, Customer export and Material export.

## 9. Production and data protection

- Old invalid Run: frontend HTTP 200 and anonymous Customer API HTTP 401 captured; exact old listener PIDs 55368 and 52812 stopped before the fresh run.
- Production DB SHA-256 before and after the corrective: `CF6054C87C84FD07273FD6F042A195E85D2F659451208711A9407214CF9365C7`.
- Production DB LastWriteTime remained `2026-09-11T11:44:40.2155909+08:00`.
- Production Business Writes: 0.
- Production Auth/Session Writes: 0.
- Production Migration: 0.
- Rehearsal authentication/session writes: allowed and isolated.
- Business-table digest excluding user/session metadata is identical between Production and the authenticated rehearsal copy: `AE6826B9C8FDE003D47C1D626CDA7037F19F341CA40E371FD161AFCC586D0B00`, 279 tables and 13,475 rows.
- Recovery, reimport and business-data regeneration: none.

## 10. Delivered user state

- Tested user path: PASS.
- Delivered browser: visible Chrome with a persistent isolated rehearsal profile.
- Delivered Tab: the single tab created for Run `WAVE1-AUTH-20260911-120000-CST`.
- Delivered URL: `http://127.0.0.1:5174/#/master-data/customers`.
- Delivered page title: `客户 / 经销商`.
- Delivered active module: Customer.
- Delivered active mode: view.
- Delivered visible primary content: Customer list, total 89, provider state `LOADED_WITH_DATA`.
- Delivered timestamp: 2026-09-11 12:50:53 CST.
- User takes over same state: GUARANTEED by final same-Tab readback; no browser action followed it.
- User manual validation: PASS. The delivered credential and runtime were subsequently invalidated and stopped as required.

### Post-acceptance cleanup

- Rehearsal user: inactive; password unusable; role scopes 0.
- Isolated Django Sessions: 0.
- Frontend PID 18292, Backend PID 40004 and visible Chrome runner PID 5980: stopped.
- Ports 5174/8000: no listener after cleanup.
- Browser-profile recursive deletion: blocked by sandbox policy after exact-path verification. The residual profile contains no usable server credential because the account is inactive and all sessions are deleted.
- Isolated rehearsal DB remains as review evidence.

## 11. Final answers

1. Automated Browser had data because it owned its own authenticated JWT/Session context; the user's browser did not.
2. The prior user Browser was not formally logged in. The fresh visible handoff Browser was formally logged in for the accepted run; that credential and Session are now invalidated.
3. Auth mechanism: Django user + signed JWT + Django Session Cookie through the existing Login endpoint.
4. JWT location: origin-scoped `localStorage.token`; Session location: browser-profile `sessionid` Cookie.
5. Production auth/session modified: NO.
6. Customer: 89, user PASS.
7. Supplier: 121, user PASS.
8. Material: 270, user PASS.
9. Workshop: 3, user PASS.
10. Operation: 33, user PASS.
11. Product Definition: 0, `LOADED_EMPTY`, user PASS.
12. Work Center: 0, `LOADED_EMPTY`, user PASS.
13. Equipment: 0, `LOADED_EMPTY`, user PASS.
14. Standard Capacity: 0, `LOADED_EMPTY`, user PASS.
15. `server-context-unavailable`: absent in the authenticated visible-browser readback.
16. Template capabilities: automated non-regression and user manual interaction PASS for the capabilities listed in the acceptance record.
17. Import Template: preserved where applicable; no separate user PASS is asserted.
18. Import status: backend-pending pages remain disabled and `ADOPTING_IMPORT_BACKEND_PENDING`.
19. Production Business Writes: 0.
20. Production Auth/Session Writes: 0.
21. User Manual Result: PASS for Data Provider and Template Runtime.
22. Final Adoption Status: not `ADOPTED`; import-pending pages remain `ADOPTING_IMPORT_BACKEND_PENDING`.
23. Evidence SHA: calculated from this final archived file at delivery and reported in the handoff.
24. ChatGPT Reviewable: YES.

## 12. Protection status

```text
Documentation Changed = YES
Adoption Governance Code Changed = YES
Page / Template / API Business Code Changed = NO
Database Changed = ISOLATED AUTH/SESSION CREATION AND INVALIDATION ONLY
Migration Created = NO
API Created = NO
Page Created = NO
Permission Model Changed = NO
Workflow Runtime Changed = NO
Production Business Writes = 0
Production Auth/Session Writes = 0
Production Migration = 0
Unauthorized Business Writes = 0
```

`Documentation Archived = YES`

`Archive Content Readback = YES`

`ChatGPT Reviewable = YES`

`Full Content Review Required = YES`

`WAVE1 DATA PROVIDER USER VALIDATION = PASS`

`FINAL ADOPTION STATUS = ADOPTING_IMPORT_BACKEND_PENDING`

`NEXT STAGE = FORMAL IMPORT BACKEND CLOSURE CORRECTIVE ONLY`
