export const LATEST_BASE_DATA_TEMPLATE_VERSION = 'PCE-LATEST-BASE-DATA-TEMPLATE-V1.0'

export const LATEST_BASE_DATA_TEMPLATE_AUTHORITY = Object.freeze({
  authorityType: 'COMPOSED_CAPABILITY_CONTRACT',
  version: LATEST_BASE_DATA_TEMPLATE_VERSION,
  shell: 'src/meta/components/PceListPageShell.vue',
  metadataList: 'src/meta/components/FoundationMetadataList.vue',
  listRuntime: 'src/meta/components/PceEnterpriseListTable.vue',
  toolbar: 'src/meta/components/StandardListToolbar.vue',
  importExtension: 'src/meta/components/LatestBaseDataImportToolbarExtension.vue',
  advancedFilter: 'src/meta/components/PceEnterpriseAdvancedFilter.vue',
  runtimeContract: 'src/meta/runtime/pceEnterpriseListContract.js',
  scopeRegistry: 'src/meta/master-data/foundationEntryUnificationRegistry.js',
  rejectedLegacyAuthority: 'src/meta/pages/ManufacturingFoundationPage.vue',
})

export const LATEST_BASE_DATA_CAPABILITY_CONTRACT = Object.freeze({
  pageIdentity: 'REQUIRED',
  processNavigation: 'REQUIRED',
  formalDbApiUiAuthority: 'REQUIRED',
  quickSearch: 'REQUIRED',
  advancedFilter: 'REQUIRED',
  sort: 'REQUIRED',
  exportCurrentResult: 'REQUIRED',
  selection: 'REQUIRED',
  rowSelection: 'REQUIRED',
  selectAll: 'REQUIRED',
  selectionCount: 'REQUIRED',
  batchContext: 'REQUIRED',
  pagination: 'REQUIRED',
  fixedColumns: 'REQUIRED',
  horizontalScroll: 'REQUIRED',
  actionColumn: 'REQUIRED_WHEN_ACTIONABLE',
  importTemplate: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  importTemplateLocalization: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  importData: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  importValidation: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  visibleImportPreview: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  visibleImportDecisions: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  explicitImportConfirmation: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  userVisibleIdempotency: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  importResultReadback: 'REQUIRED_WHEN_FORMAL_BULK_IMPORT_APPLICABLE',
  providerState: 'REQUIRED',
  refresh: 'REQUIRED',
})

export const LATEST_BASE_DATA_IMPORT_CHAIN = Object.freeze([
  'download-template', 'upload', 'validate', 'error-report', 'preview',
  'human-confirm', 'controlled-formal-write', 'reload-formal-facts',
])

export const LATEST_BASE_DATA_FORBIDDEN_FALLBACKS = Object.freeze([
  'Generic Shell', 'second base-data template', 'localStorage formal facts',
  'browser storage formal writes', 'frontend-only import success',
])

export function assertLatestBaseDataTemplateContract(contract = LATEST_BASE_DATA_CAPABILITY_CONTRACT) {
  const missing = Object.keys(LATEST_BASE_DATA_CAPABILITY_CONTRACT).filter(key => !contract[key])
  if (missing.length) throw new Error(`LATEST BASE DATA TEMPLATE CONTRACT missing: ${missing.join(', ')}`)
  if (LATEST_BASE_DATA_TEMPLATE_AUTHORITY.authorityType !== 'COMPOSED_CAPABILITY_CONTRACT') {
    throw new Error('LATEST BASE DATA TEMPLATE authority must remain a composed capability contract')
  }
  return true
}
