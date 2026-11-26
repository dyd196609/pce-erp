# Formal Import File-Type Dispatch

Supported types are `.xlsx` and `.csv` under one shared import service.

The frontend sends the original filename, browser-declared content type and bytes. The backend combines extension, content signature and declared MIME as supporting evidence; MIME alone is never authoritative.

| Input | Dispatch/result |
|---|---|
| `.xlsx` + ZIP magic `PK\x03\x04` | XLSX parser (`openpyxl`) |
| `.csv` without ZIP magic | CSV parser, then UTF-8 validation |
| `.xlsx` without ZIP magic | `IMPORT_FILE_SIGNATURE_INVALID` |
| `.csv` containing XLSX ZIP bytes | `IMPORT_FILE_SIGNATURE_INVALID` |
| Unsupported extension | `IMPORT_FILE_TYPE_UNSUPPORTED` |

Preview returns `fileType`; XLSX preview additionally returns the canonical `worksheetName`. Commit uses the preview fingerprint and the same dispatch contract. The gate `verify:pce-formal-import-file-type-dispatch` traverses the formal Preview View and confirms zero business/audit writes.

`XLSX ENTERS CSV UTF-8 DECODE = NO`  
`SUPPORTED_IMPORT_FILE_TYPES = XLSX, CSV`
