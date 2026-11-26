# XLSX Import Runtime Acceptance

Nine real XLSX files were created from the same shared formal template authority, filled using localized display values, and submitted through the formal Upload Preview/Commit API runtime against fresh isolated database `D:\Dev-PCE\work\wave1_xlsx_runtime_20260911_004.sqlite3`. The separate localization gate proves that the user-facing Template Download view returns the same authority's valid XLSX contract.

| Entity | Template | XLSX upload | Preview zero-write | Commit | Readback | Replay MATCH |
|---|---|---|---|---|---|---|
| Customer | PASS | PASS | PASS | PASS | PASS | PASS |
| Supplier | PASS | PASS | PASS | PASS | PASS | PASS |
| Material | PASS | PASS | PASS | PASS | PASS | PASS |
| Product Definition | PASS | PASS | PASS | PASS | PASS | PASS |
| Workshop | PASS | PASS | PASS | PASS | PASS | PASS |
| Operation | PASS | PASS | PASS | PASS | PASS | PASS |
| WorkCenter | PASS | PASS | PASS | PASS | PASS | PASS |
| Equipment | PASS | PASS | PASS | PASS | PASS | PASS |
| Standard Capacity | PASS | PASS | PASS | PASS | PASS | PASS |

The run made 9 formal writes and 9 audit writes in the isolated database only. Read-only authorization denial and multi-row atomic rollback also passed. Production database hash remained unchanged.

The same byte array is reused for Preview and Commit so the formal file fingerprint represents the user's selected file exactly.
