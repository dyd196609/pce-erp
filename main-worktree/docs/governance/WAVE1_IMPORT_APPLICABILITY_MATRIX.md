# Wave 1 Formal Import Applicability Matrix

Date: 2026-09-11  
Instruction: `WAVE1-FORMAL-IMPORT-BACKEND-CLOSURE-20260911-001`  
Decision authority: formal model + existing `ProductionFoundationService` + latest base-data template contract

| Business Object | Chinese Name | Route | Formal Model | Formal Schema / Identity | Import Applicable | Business Reason | Template Download Applicable | Existing Backend Capability | Gap | Target Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Customer | 客户 / 经销商 | `/master-data/customers` | `sales.Customer` | company + code; name; active | YES | Stable enterprise master maintained in batches | YES | Unified formal write service, validation, authorization, audit, identity ledger | Shared import binding and confirmation flow | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Supplier | 供应商 | `/master-data/suppliers` | `procurement.Supplier` | company_id + globally unique code; name; governed attributes | YES | Stable procurement master maintained in batches | YES | Same formal write chain | Shared import binding and confirmation flow | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Material | 物料档案 | `/foundation/master-data/materials` | `masterdata.Material` | company + code; name; UOM/type attributes | YES | High-volume stable material master | YES | Same formal write chain, CodeRule, UOM/reference validation | Shared import binding and confirmation flow | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Product Definition | 产品定义 | `/foundation/master-data/products` | `pde.ProductDefinition` | company + product_code; product_name; EMD material identity | YES | Long-lived product master; batch setup is a formal maintenance need | YES | Same formal write chain and product validation | Import schema must expose required EMD identity and optional references | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Workshop | 车间 / 生产区域 | `/foundation/master-data/workshops` | `system.Workshop` | company + code; name; optional department | YES | Stable manufacturing resource master | YES | Same formal write chain and CodeRule | Shared import binding and reference resolution | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Operation | 工序 | `/foundation/master-data/operations` | `system.Process` | company + code; name; protected routing semantics | YES | Stable reusable operation master; legitimate controlled batch maintenance | YES | Same formal write chain, CodeRule and audit | Must preserve protected identity, existing 33 records and routing semantics | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Work Center | 工作中心 | `/foundation/master-data/work-centers` | `pde.WorkCenter` | company + code; name; required department | YES | Stable capacity/resource master commonly established in batches | YES | Same formal write chain and reference validation | Required department identity resolution | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Equipment | 设备资料 | `/foundation/master-data/equipment` | `pde.Equipment` | work center + code; name | YES | Stable resource master associated with a work center | YES | Same formal write chain and reference validation | Required work-center identity resolution | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |
| Standard Capacity | 标准产能 | `/foundation/master-data/standard-capacities` | `pde.StandardCapacity` | company + code; resource scope/reference; measurement semantics | YES | Governed master fact maintained by resource scope, not a derived runtime result | YES | Same formal write chain and model validation | Conditional resource reference validation | `MANUAL_IMPORT_VALIDATION_PENDING` after automated PASS |

## Decision

All nine objects are formal maintained master/foundation data, not derived runtime facts, transactional outcomes or read-only diagnostics. The existing canonical write architecture covers all nine, so none requires a second importer, a new business model or a Production migration.

`IMPORT_APPLICABILITY_MATRIX = PASS`

`IMPORT_APPLICABLE_YES = 9`

`IMPORT_APPLICABLE_NO = 0`

`PRODUCTION IMPORT AUTHORIZED = NO`
