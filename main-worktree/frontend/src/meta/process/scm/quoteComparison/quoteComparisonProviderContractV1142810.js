export const QUOTE_COMPARISON_PROVIDER_CONTRACT_V1142810 = Object.freeze({
  version: 'V1.14.2.8.18.10', providerCode: 'SCM_QUOTE_COMPARISON_PROVIDER',
  sourceProviderCode: 'SCM_SUPPLIER_QUOTE_PROVIDER', factSource: 'SupplierQuoteProvider',
  output: 'comparisonPreparationList', firstLoad: true, refreshRecovery: true,
  legacyMockAllowed: false, pageTemporaryStateAllowed: false,
})

export function validateQuoteComparisonProviderContractV1142810() {
  const value = QUOTE_COMPARISON_PROVIDER_CONTRACT_V1142810
  const valid = value.factSource === 'SupplierQuoteProvider' && value.legacyMockAllowed === false
    && value.pageTemporaryStateAllowed === false && value.firstLoad && value.refreshRecovery
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', contract: value })
}
