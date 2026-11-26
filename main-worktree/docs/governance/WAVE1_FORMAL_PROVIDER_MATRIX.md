# Wave 1 Formal Provider Matrix

Authority remains `PCE-LATEST-BASE-DATA-TEMPLATE-V1.0`. No legacy page, demo store, or localStorage data authority is permitted.

| Area | Formal model/table | Endpoint / adapter | Runtime result | Adoption status |
|---|---|---|---|---|
| Customer | `sales.Customer` / `sales_customer` | `/api/masterdata/enterprise/customers/facts/` | 89/89 API/UI and user PASS, `LOADED_WITH_DATA` | `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |
| Supplier | `procurement.Supplier` / `supplier` | `/api/masterdata/enterprise/suppliers/facts/` | 121/121 and user PASS, `LOADED_WITH_DATA` | `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |
| Material | `masterdata.Material` / `material` | `/api/pde/a1-foundation/materials/` | 270/270 and user PASS, `LOADED_WITH_DATA` | `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |
| Product Definition | `pde.ProductDefinition` / `pde_product_definition` | `/api/pde/a1-foundation/products/` | 0/0 and user PASS, `LOADED_EMPTY` | `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |
| Product Engineering | Domain container; formal child models | PDE A1 entity endpoints | Product Definition user PASS; other child-module manual status not inferred | mixed; no module `ADOPTED` |
| Manufacturing Resource | Workshop/WorkCenter/Process/Equipment/StandardCapacity | PDE A1 entity endpoints | 3/0/33/0/0 API/UI and user PASS | `ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED` |

Provider state contract: `LOADING`, `LOADED_EMPTY`, `LOADED_WITH_DATA`, `AUTH_FAILED`, `SERVER_CONTEXT_UNAVAILABLE`, `API_FAILED`, `SCHEMA_FAILED`.

Gate command: `npm run verify:pce-latest-base-data-provider-continuity`. It checks every adoption mapping and requires DB/API/UI runtime evidence before any row can be marked `ADOPTED`. Current adopted-runtime checks remain zero because user-visible actor-context Commit/Replay is pending.
