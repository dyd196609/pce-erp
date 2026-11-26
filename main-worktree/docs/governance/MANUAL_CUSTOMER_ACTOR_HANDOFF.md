# Customer A4 Manual Acceptance Record

## Latest minimal closure (supersedes earlier cleanup/evidence status)

Human A4 PASS retained. On 2026-09-11 22:10:18 +08, one AUTOMATED CLOSURE SUPPLEMENT used the unchanged original A4 file through formal HTTP login/Preview/Commit: CREATE0/MATCH1; HTTP201; total91→91; PK91 identity and all Customer fields unchanged. Current total includes separate A3 PK90; historical user89→90→90 remains an observation, not current server total. Actor14 and readonly15 are now inactive with unusable passwords; old JWT/Session/password rejected; owned services stopped. Do not attempt further manual import with these retired credentials. Final build Exit1 and hardcoded adoption gate remain the only closure conditions; see FINAL_CONSOLIDATED and CLOSURE_* evidence.

## Final-closure evidence annotation

The user's A4 PASS below remains the authoritative manual decision. Current read-only database evidence has A4 once (PK 91, audit 2447, 20:20:29) and a separate A3 row (PK 90, audit 2446, 20:12:19), making the current unfiltered total 91. The 20:13 Customer request predates the A4 creation and cannot be attributed to A4 Replay. No post-creation A4 Commit trace was found. The previous 89→90→90 user record is preserved verbatim; it is not substituted for the current server total. No data was altered to reconcile the difference. Cleanup remains unexecuted at the final-closure exception stop, now due to missing Run ownership/evidence rather than missing B4/C4 user PASS.

Decision received: `USER MANUAL CUSTOMER A4 ACTOR VALIDATION = PASS`.

- Run: `W1FI-A4-MANUAL-20260911-001`
- Actor: `wave1_import_maintenance_a4`
- Identity chain: User 14 → Employee 109 (`W1AC-A4-E1`) → Position 36 (`W1AC-A4-20260911`) → Responsibility 57 (`W1AC-A4-20260911-RESP`) → organization 1
- Permission: `masterdata.customer.maintain` ALLOWED
- Before: 89
- First Preview: CREATE=1 / MATCH=0, PASS
- First Commit: PASS
- After first Commit: 90
- Imported identity: `W1-A4-CUST-20260911`, user-visible search PASS
- Replay Preview: CREATE=0 / MATCH=1, PASS
- Replay Commit: PASS
- After replay: 90, no duplicate
- User-visible Import Commit: PASS
- User-visible idempotency: PASS
- Production Import: 0

The A4 actor and its current session remain active by instruction. Cleanup is deferred until Material B4 and Workshop C4 manual validation and replay are both complete.

`FORMAL IMPORT ACTOR CONTEXT = CUSTOMER MANUAL PASS`
