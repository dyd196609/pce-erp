# Real HTTP Import Actor Trace

## Latest automated closure supplement — 2026-09-11

The earlier historical-attribution limits below remain true. New evidence resolves closure without rewriting those logs: CLOSURE_REPLAY_RESULTS.json links each original file SHA, first-write audit fingerprint, original target PK, actor/DB binding, zero-create preview, real HTTP201 commit and unchanged data/counts. CLOSURE_ACTUAL_HTTP_TRACE.jsonl holds three new actual server Commit traces; they are AUTOMATED CLOSURE SUPPLEMENT, not additional human operations. A4/B4/C4 totals91/271/4 and identities remain unique. Identity cleanup then made original password, JWT and Session unusable; the isolated service is stopped. See FINAL_CONSOLIDATED for remaining build/adoption gate conditions.

## Final closure correction — current evidence

The historical attribution below is not reliable for individual files: audit 2446 links 20:12:19 to A3, audit 2447 links 20:20:29 to A4. The 20:13:18 request cannot be A4 replay because it precedes A4 creation. The earlier assertion that the final-context entries identify an automated check and two A4 user actions is withdrawn. Actor-level PASS does not provide file/result-level correlation.

New actual traces show materials PASS at 20:34:03 and 20:34:39 and workshops PASS at 20:35:31 and 20:35:42. First audits are 2448/2449; business identities each exist once. Trace records contain no file fingerprint or Commit created/matched/readbackCount, so the second requests alone do not prove the required same-file replay result. All three user manual PASS decisions are preserved. See the final-closure raw JSONL and readback evidence, not the historical trace-count summary below.

## Historical report (superseded attribution, preserved for review)

Instruction: `WAVE1-MANUAL-ACTOR-IDENTITY-BINDING-CORRECTIVE-20260911-001`  
Run: `W1FI-A4-MANUAL-20260911-001`

## Historical A3 failure

The A3 browser request occurred before request-level tracing existed. Its exact `request.user` username, login-time database path and JWT database identity cannot be reconstructed and are recorded as **UNKNOWN**, not inferred from a fixture.

## A4 real user trace and decision

The sanitized trace contains actual HTTP Customer Commit records for the A4 maintenance actor. The authoritative user decision confirms first Commit and replay Commit PASS.

- Source: `ACTUAL_HTTP_REQUEST`
- Entity / phase / outcome: `customers` / `COMMIT` / `PASS`
- Request/JWT/session user: 14 / 14 / 14
- Username: `wave1_import_maintenance_a4`
- Database context for final manual run: `6a95418e89efd1a05526252787ea36cb8990f69280ec1b9325245108a881bce0`
- Organization: 1
- Employee: 109 (`W1AC-A4-E1`, active)
- Position: 36 (`W1AC-A4-20260911`, enabled)
- Responsibility: 57 (`W1AC-A4-20260911-RESP`, effective)
- Permission: `masterdata.customer.maintain`
- First visible result: 89 → 90; `W1-A4-CUST-20260911` searchable
- Replay visible result: CREATE=0/MATCH=1; count remains 90

The trace file is `D:\Dev-PCE\work\wave1_actor_binding_manual_a4_20260911_001.actual-http-trace.jsonl`. It contains no full JWT. Four sanitized Customer Commit entries exist in total across preflight and final contexts; the final context has three entries, including the automated final-context check and the two user-confirmed Commit actions. Context IDs keep these records unambiguous.

`CUSTOMER A4 ACTUAL HTTP ACTOR TRACE = PASS`
