# Formal Import Maintenance Actor Contract

Contract version: `WAVE1-FORMAL-IMPORT-ACTOR-CONTEXT-V1.0`  
Run ID: `W1FIAC-20260911-001`  
Database: `D:\Dev-PCE\work\wave1_actor_manual_20260911_001.sqlite3` (fresh isolated copy)

## Required chain

Commit must re-resolve and pass all of:

`User → Employee → active Employment → enabled/effective Position → active/effective Responsibility → Role/Permission → Organization Scope → Formal Write`

Fresh maintenance identities:

- User: ID 14, `wave1_import_maintenance_a3`, active, non-staff, non-superuser.
- Employee: ID 109, `W1AC-A3-E1`, active.
- Position: ID 36, `W1AC-A3-20260911`, enabled/effective, company 1, department 17.
- Responsibility: ID 57, `W1AC-A3-20260911-RESP`, active from 2026-09-11, mapped to position.
- Role: ID 18, `W1AC-A3-20260911-ROLE`, position default role and organization-scope assignment.
- Organization/company scope: organization 1 / company 1.

Minimal permission set:

- `production.master_data.view`
- `masterdata.customer.maintain`
- `masterdata.supplier.maintain`
- `production.master_data.material.maintain`
- `production.master_data.product.maintain`
- `production.master_data.resource.maintain`
- `production.master_data.capacity.maintain`

The contract grants no Purchase Approval, Putaway, Payment, Production Execution, Bank Send, Admin or Superuser capability. The separate read-only actor has view permission and may Preview, but Commit is denied.

## Lifecycle and cleanup

Bootstrap and cleanup are provided by `backend/scripts/bootstrap_wave1_formal_import_actor.py`. Cleanup is intentionally deferred until the user reports A3/B3/C3 PASS; it then deactivates role scopes, employee and users, invalidates passwords, disables responsibility/position, deletes sessions and stops the isolated services. It refuses production-database operation.
