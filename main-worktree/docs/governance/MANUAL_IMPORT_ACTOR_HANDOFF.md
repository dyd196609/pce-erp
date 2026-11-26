# Manual Import Actor Handoff

Manual environment: `http://127.0.0.1:5174/`  
Isolated database: `D:\Dev-PCE\work\wave1_actor_manual_20260911_001.sqlite3`

## Use this identity for Commit

- Import Maintenance Account: `wave1_import_maintenance_a3`
- Password: `Wave1.Actor#20260911`

Do not use the read-only account for Commit. The separate read-only identity is `wave1_import_readonly_a3`; it is intentionally permitted to read/Preview and denied Commit with HTTP 403.

## Samples

- `A3-客户人工导入样例.xlsx`
- `B3-物料人工导入样例.xlsx`
- `C3-车间人工导入样例.xlsx`

Only verify Confirm Import and same-file Replay; Chinese template/header checks do not need repeating.

| Object | Before | First preview | First Commit | Replay preview | Replay Commit |
|---|---:|---|---|---|---|
| Customer | 89 | CREATE=1 / MATCH=0 | PASS; count 90; search imported identity | CREATE=0 / MATCH=1 | count remains 90 |
| Material | 270 | CREATE=1 / MATCH=0 | PASS; count 271; search imported identity | CREATE=0 / MATCH=1 | count remains 271 |
| Workshop | 3 | CREATE=1 / MATCH=0 | PASS; count 4; search imported identity | CREATE=0 / MATCH=1 | count remains 4 |

The samples have already been independently previewed in the fresh isolated database with zero business/audit writes. After you report all six Commit/Replay results PASS, cleanup will disable/invalidate the rehearsal identities and sessions, disable/delete rehearsal position/responsibility as allowed by the formal test contract, deactivate the employee, stop services and record isolated-database disposition.

`MANUAL IMPORT ACTOR VALIDATION READY`
