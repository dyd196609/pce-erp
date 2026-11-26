# Formal Import Actor Context Root Cause

Instruction: `WAVE1-FORMAL-IMPORT-ACTOR-CONTEXT-CORRECTIVE-20260911-001`  
Review level: C  
Date: 2026-09-11

## User-observed fact

The user confirmed Template, Chinese localization, XLSX reading and Preview. Customer, Material and Workshop each reached `READY=1 / CREATE=1 / MATCH=0`, but Confirm Import returned `企业基础资料维护账户必须关联在职员工、启用岗位和有效职责。` Therefore the user-visible Commit and Replay gates did not pass.

## Trace of the former manual account

Read-only inspection of `wave1_formal_import_gate` in the retained former manual database found:

| Layer | Result | Identity/evidence |
|---|---|---|
| User | YES | user ID 14, active, non-staff, non-superuser, company 1 |
| Employee link | YES | employee ID 109, `W1FIBC-E1` |
| Employee active | YES | status `active` |
| Position link | YES | position ID 36, `W1FIBC-POS` |
| Position enabled | YES | status `active`, company 1 |
| Responsibility link | YES | mapping ID 175, responsibility ID 57 |
| Responsibility valid | YES | `W1FIBC-RESP`, `ACTIVE`, active, no expired date |
| Import permission | YES | role `W1FIBC-ROLE`, organization scope 1, all seven Wave 1 permissions allowed |

This is the present retained-state trace, not proof that the same rows/session/database were active at the instant of the user's failure. The former guard collapsed missing Employee, inactive employment, missing/disabled Position and missing/invalid Responsibility into one message. Consequently the exact historical failing sublayer is not recoverable and is recorded as **indeterminate**, rather than guessed.

## Proven root cause class

The mismatch was delivery-state identity drift across browser session and isolated database copies:

1. the former manual identity name was reused across isolated database copies;
2. the browser could retain an earlier JWT/session across a database switch;
3. the JWT authentication implementation carries numeric `user_id` and resolves that ID in whichever database is currently connected;
4. the former failure message did not identify which actor-chain sublayer failed;
5. the fresh actor bootstrap removed 166 copied sessions, proving the isolated copy contained stale session state.

This explains why current database inspection can show a complete chain while the earlier user Commit still failed. The corrective does not add privilege to the old account. It creates a fresh, run-marked identity in a fresh isolated database and makes Commit re-resolve every actor layer.

## Corrective

`FormalImportService.commit` now requires the formal User → Employee → active Employment → enabled/effective Position → valid/effective Responsibility → assigned Role/Permission → Organization Scope chain. Each failed layer has a distinct `FORMAL_IMPORT_ACTOR_*` denial and maps to HTTP 403. No `staff`, `superuser`, `AllowAny`, skip guard, hard-coded actor or production identity change is used.

Current disposition: automated and live-HTTP actor preconditions PASS; user-visible A3/B3/C3 Commit and Replay remain pending, so applicable pages remain `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED`.
