# LATEST BASE DATA TEMPLATE AUTHORITY

- Authority version: `PCE-LATEST-BASE-DATA-TEMPLATE-V1.0`
- Status: `FORMAL AUTHORITY ESTABLISHED`
- Authority type: composed capability contract, not a copied page.

## Authority stack

1. `PceListPageShell.vue`: page identity, main-process context and process navigation.
2. `FoundationMetadataList.vue`: registry-driven columns, filters, actions and export runtime.
3. `PceEnterpriseListTable.vue`: `PCE-ENTERPRISE-LIST-CONTRACT-V1.1`, selection, pagination, frozen columns and scrolling.
4. `StandardListToolbar.vue`: search, refresh, advanced-filter toggle, filter/sort reset and current-result export.
5. `LatestBaseDataImportToolbarExtension.vue`: shared import-template/import surface for pages whose formal import chain is ready.
6. `PceEnterpriseAdvancedFilter.vue`: schema-driven advanced filters.
7. `pceEnterpriseListContract.js`: machine-readable list capability contract.
8. `foundationEntryUnificationRegistry.js`: canonical page, route, model and API scope.

## Evidence and rejection

The authority is the only current composition that joins the latest shared list runtime, metadata registry and process shell. `ManufacturingFoundationPage.vue` is explicitly rejected: its import completion text says data was written to `localStorage`, which cannot be formal business authority. It is evidence of a legacy capability, not a template authority.

No Generic Shell, second template or Supplier/Procurement recovery work is authorized by this decision.
