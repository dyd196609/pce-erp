# Wave 1 Formal Import Architecture

Instruction: `WAVE1-FORMAL-IMPORT-XLSX-CONTRACT-CORRECTIVE-20260911-001`  
Status: automated XLSX/CSV backend closure PASS; user XLSX walkthrough pending

## Reuse decision

The implementation has one shared spreadsheet orchestration adapter, `pde.formal_import_service.FormalImportService`. It is not a second write engine. It owns only schema projection, XLSX/CSV file-type dispatch, parsing, normalization, reference resolution, preview classification and batch coordination. Every CREATE delegates to the pre-existing `ProductionFoundationService.write`, which remains the sole owner of authorization, formal validation, transaction, `ExternalIdentity`, `MasterDataWriteRequest`, code rules, audit and row readback.

The older `/api/pde/foundation-import-preview/` XLSX source-comparison endpoint remains read-only and unchanged. The new formal endpoints are template, preview and commit under `/api/pde/formal-import/<entity>/`.

Upload → extension + magic + MIME contract check → XLSX or UTF-8 CSV parser → header/schema check → typed row normalization → same-company reference resolution → model validation → READY/REVIEW/BLOCKED preview → explicit user confirmation → fingerprint recheck → canonical authorization/write → atomic batch → audit → formal list readback.

XLSX is the official template format and is identified by `.xlsx` plus ZIP magic. It never enters CSV decoding. CSV remains a compatibility path and only CSV receives UTF-8 validation. Extension/signature conflicts and unsupported extensions fail before parsing.

Preview performs zero formal writes. Commit rejects changed fingerprints, missing confirmation, REVIEW/BLOCKED rows and denied authorization. The outer commit transaction rolls back all rows when any delegated write fails.

No raw SQL, migration, localStorage authority, per-page importer, temporary business model or Production write was added.

`SECOND IMPORT FRAMEWORK = 0`  
`PRODUCTION MIGRATION = 0`
