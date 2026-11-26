# Wave 1 Customer DB → API → UI Lineage

`sales_customer` → `sales.Customer` → `/api/masterdata/enterprise/customers/facts/` → `enterpriseMasterDataApi` → `EnterpriseMasterDataPage` → `PceEnterpriseListTable`.

| Check | Result |
|---|---|
| DB count | 89 |
| API status / total | 200 / 89 |
| UI total | 89 |
| Provider | `LOADED_WITH_DATA` |
| Sample identity | `CUST-PCE-ACCEPT-001`, visible match PASS |
| Business writes during read acceptance | 0 |

The earlier page existed but showed failed facts because it could be opened without a valid server identity. Its list shell was also conditionally removed on read failure. The authentication guard and unconditional latest-template list shell correct both defects.
