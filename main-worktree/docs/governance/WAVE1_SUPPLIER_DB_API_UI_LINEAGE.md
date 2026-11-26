# Wave 1 Supplier DB → API → UI Lineage

`supplier` → `procurement.Supplier` → `/api/masterdata/enterprise/suppliers/facts/` → `enterpriseMasterDataApi` → `EnterpriseMasterDataPage` → `PceEnterpriseListTable`.

DB/API/UI = **121/121/121**. HTTP 200; provider `LOADED_WITH_DATA`; sample supplier code `SUP001` is visible; identity match PASS. UI total is the full formal result total, not a page-size count. No reimport, recovery, hard-coded count, demo fallback, or localStorage supplier authority was used.
