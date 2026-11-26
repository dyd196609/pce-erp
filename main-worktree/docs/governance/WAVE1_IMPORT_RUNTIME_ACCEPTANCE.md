# Wave 1 Formal Import Runtime Acceptance

Run: `WAVE1-FORMAL-IMPORT-20260911-001`  
Database: `D:\Dev-PCE\work\wave1_formal_import_manual_20260911.sqlite3`  
Production database used: NO

| Entity | Template | Upload/Validation | Error Report | Preview zero-write | Confirmation/Commit | Audit/Readback | Replay MATCH |
|---|---|---|---|---|---|---|---|
| Customer | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Supplier | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Material | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Product Definition | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Workshop | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Operation | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| WorkCenter | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Equipment | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| Standard Capacity | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

Coverage also passed: invalid required field, invalid type/enum, duplicate-in-file, existing-identity REVIEW, mixed non-committable preview, changed-file fingerprint rejection, missing confirmation rejection, read-only commit denial, and injected second-row failure with complete batch rollback.

The repository's empty-test-database bootstrap is independently blocked by pre-existing migration `pde.0021_group3a_operation_executor_authority`, which assumes a seeded role. The authoritative runtime suite therefore ran against a fresh byte-for-byte Production copy outside `Source`; it did not migrate or write Production.

Automated result: PASS. User browser import result: PENDING.
