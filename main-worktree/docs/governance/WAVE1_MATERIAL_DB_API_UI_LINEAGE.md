# Wave 1 Material DB → API → UI Lineage

`material` → `masterdata.Material` → `/api/pde/a1-foundation/materials/` → `pdeApi.productionFoundationA1` → `ProductionFoundationMaintenance` → latest-template runtime → `PceEnterpriseListTable`.

DB/API/UI = **270/270/270**. HTTP 200; provider `LOADED_WITH_DATA`; sample material code `MT001` is visible; identity match PASS. Search, advanced filter, sort, export, pagination and process/module navigation remain present. Import Template and Import controls remain visible but disabled because the formal import backend is still pending.
