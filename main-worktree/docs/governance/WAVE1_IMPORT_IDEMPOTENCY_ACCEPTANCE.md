# Wave 1 Import Idempotency Acceptance

Identity is the formal business identity (`company + code`, `company + product_code`, or `work_center + equipment code`), never the spreadsheet row number. CREATE rows receive a batch-key/business-identity source identity and are persisted through existing `ExternalIdentity` and `MasterDataWriteRequest` ledgers.

For each applicable object: first confirmed import Create=1; formal count increases by one; second preview is Match=1; second submission Create=0 and count unchanged. Identity conflicts are REVIEW; duplicates inside a file are BLOCKED. An injected failure on row two proved row one, its source identity, ledger and audit all roll back.

`REPLAY CREATES 0 = PASS`  
`ATOMIC BATCH ROLLBACK = PASS`
