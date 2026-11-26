# Import Template Real-File Localization Acceptance

Instruction: `WAVE1-FORMAL-IMPORT-XLSX-CONTRACT-CORRECTIVE-20260911-001`  
Date: 2026-09-11

## User-reality conflict

The user's downloaded files are authoritative evidence. The earlier localization PASS is revoked as a user-acceptance conclusion and marked `SUPERSEDED BY USER REALITY FAILURE`. Before restart, the live endpoint returned `text/csv`, filename `customers-formal-import.csv`, and bytes beginning with UTF-8 BOM + `code,`, proving the discrepancy.

## Root-cause matrix

| Candidate | Decision | Evidence |
|---|---|---|
| A. Gate checked schema/generator, not the real downloaded file | CONFIRMED | Old gate called `FormalImportService.template_bytes` directly rather than the Template Download view. |
| B. Test workbook and user download used different effective runtime | CONFIRMED | Test used current source; the user-facing port was served by an old process. |
| C. Effective live generator wrote field keys | CONFIRMED | Captured live response started with `code,name,is_active`. |
| D. Chinese labels existed only outside actual Excel cells | CONFIRMED for old live runtime | Current schema had labels, but old live response exposed keys. |
| E. Gate did not test current browser runtime response | CONFIRMED | It did not traverse `FormalImportTemplateView` or capture its response. |
| F. Cache/stale runtime | CONFIRMED | Restarting the listener on current source changed the response to XLSX ZIP magic and Chinese headers. |
| G. A second frontend template generator | REJECTED | Latest Template calls the shared `pdeApi.formalImportTemplate` route; no parallel generator was found in this path. |

## Corrected acceptance

`verify:pce-import-template-localization` now invokes `FormalImportTemplateView`, obtains the exact response bytes, writes them to a temporary file, opens them with the Excel parser, and verifies content type, `PK\x03\x04` magic, worksheet, first-row headers, examples, validations and parser round-trip for all nine entities.

Automated result: 9/9 PASS. User-visible final acceptance remains pending A2/B2/C2 revalidation.

`TESTED FILE == USER DOWNLOADED FILE GENERATION PATH = YES`  
`REPORT VS USER REALITY CONFLICT = YES`
