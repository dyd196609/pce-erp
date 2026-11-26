# Material B4 / Workshop C4 Same-Actor Manual Handoff

## Latest minimal closure (supersedes earlier READY/PENDING/cleanup status)

Human B4/C4 PASS retained. On 2026-09-11 22:10:19 +08, each original file received exactly one AUTOMATED CLOSURE SUPPLEMENT formal HTTP replay under the original A4 actor/database. Each Preview CREATE0/MATCH1; Commit HTTP201 created0/matched1; API original identity readback PASS; whole-table fields/counts unchanged (Material271, Workshop4). This is not claimed as a historical human Replay. Maintenance14/readonly15 and credentials are now disabled; services stopped; no further manual action is requested. Original files, first audits, correlations and cleanup are preserved in existing CLOSURE_* evidence. Current full Build Exit1 and static adoption-gate conflict prevent CLOSED, not missing B4/C4 human acceptance.

## Latest user decision — 2026-09-11 final closure

`MATERIAL B4 USER MANUAL IMPORT = PASS`; `WORKSHOP C4 USER MANUAL IMPORT = PASS`.

Read-only evidence: original B4/C4 file fingerprints match creation audits 2448/2449 under A4 User 14, Employee 109, Position 36, Responsibility 57. Current unfiltered totals: Material 271; Workshop 4. Each original identity exists once. Each entity has two successful HTTP Commit traces, but the second trace does not contain file fingerprint, business identity or returned create/match counts. No automated replay supplement was performed because the current Run Manifest/ownership was not established. User PASS is preserved; technical closure and cleanup are blocked on the specific evidence listed in `FINAL_CONSOLIDATED.md`.

## Historical handoff (before the manual operations)

Use the existing A4 login/session and the same isolated database. Do not bootstrap another identity.

- Frontend: `http://127.0.0.1:5174`
- Backend: `http://127.0.0.1:8000`
- Database: `D:\Dev-PCE\work\wave1_actor_binding_manual_a4_20260911_001.sqlite3`
- Username: `wave1_import_maintenance_a4`
- Actor: User 14 / Employee 109 / Position 36 / Responsibility 57 / organization 1
- Actor DB context: `6a95418e89efd1a05526252787ea36cb8990f69280ec1b9325245108a881bce0`

## Material B4

- File: `D:\Dev-PCE\Source\samples\B4-物料人工导入样例.xlsx`
- Identity: `W1-B4-MAT-20260911`
- Read-only readiness: Preview CREATE=1 / MATCH=0, PASS
- Permission: `production.master_data.material.maintain` ALLOWED
- Expected first Commit: 270 → 271; search identity succeeds
- Expected replay: Preview CREATE=0 / MATCH=1; Commit succeeds; count remains 271

## Workshop C4

- File: `D:\Dev-PCE\Source\samples\C4-车间人工导入样例.xlsx`
- Identity: `W1-C4-WS-20260911`
- Department code: `W1AC-A4-20260911`
- Read-only readiness: Preview CREATE=1 / MATCH=0, PASS
- Permission: `production.master_data.resource.maintain` ALLOWED
- Expected first Commit: 3 → 4; search identity succeeds
- Expected replay: Preview CREATE=0 / MATCH=1; Commit succeeds; count remains 4

The readiness check left Material at 270 and Workshop at 3 and produced zero business/audit writes. Do not clean up A4 identity or session until both B4 and C4 are manually complete. Any actor/permission error is a stop condition; do not add another actor, role, or permission.

`B4 C4 SAME ACTOR READINESS = PASS`  
`B4 C4 USER MANUAL VALIDATION = PENDING`
