# Formal Import Actor Negative Tests

Gate: `npm run verify:pce-formal-import-actor-context`

| # | Scenario | Expected | Result |
|---:|---|---|---|
| 1 | User only, no Employee | DENY | PASS |
| 2 | Employee inactive | DENY | PASS |
| 3 | No Position | DENY | PASS |
| 4 | Position disabled | DENY | PASS |
| 5 | Position expired | DENY | PASS |
| 6 | No Responsibility | DENY | PASS |
| 7 | Responsibility expired | DENY | PASS |
| 8 | Missing Import Permission | DENY | PASS |
| 9 | Read-only actor Preview then Commit | Preview ALLOW; Commit 403 | PASS |
| 10 | Valid maintenance actor | ALLOW | PASS |
| 11 | Valid actor with wrong organization scope | DENY | PASS |
| 12 | Actor invalidated after Preview | Commit DENY | PASS |
| 13 | Successful Commit audit | complete actor/source fields | PASS |

Combined backend regression: 19/19 PASS. Nine real XLSX objects: 9/9 Template, parse, Preview, Commit, formal readback and Replay PASS using a human-like chain. Second-row rollback and read-only denial also PASS. Production database was not used.
