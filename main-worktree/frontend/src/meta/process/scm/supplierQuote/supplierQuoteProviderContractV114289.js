export const SUPPLIER_QUOTE_PROVIDER_CONTRACT_VERSION = 'V1.14.2.8.18.9'

export const SUPPLIER_QUOTE_PROVIDER_CONTRACT = Object.freeze({
  providerCode: 'SCM_SUPPLIER_QUOTE_PROVIDER',
  factOwner: 'SupplierQuoteRuntimeStore',
  factSource: 'supplier_quote_runtime_store',
  inputObjects: Object.freeze(['SupplierQuoteContext', 'SupplierQuote']),
  outputRecords: 'supplierQuotePreparationList',
  supports: Object.freeze(['firstLoad', 'refresh', 'reopen', 'emptyState', 'deduplicate']),
  forbiddenSources: Object.freeze(['legacyMock', 'pageTemporaryState', 'urlParameterAssembly']),
})

export function validateSupplierQuoteProviderContract() {
  const contract = SUPPLIER_QUOTE_PROVIDER_CONTRACT
  const valid = contract.providerCode === 'SCM_SUPPLIER_QUOTE_PROVIDER'
    && contract.factOwner === 'SupplierQuoteRuntimeStore'
    && contract.forbiddenSources.length === 3
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL' })
}
