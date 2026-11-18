export const QUOTE_COMPARISON_PRODUCTION_ACCEPTANCE_ADAPTER_VERSION = 'V1.14.2.8.4.23-R2'

export function adaptQuoteComparisonProductionFacts(facts = {}, { expectedCount = 13 } = {}) {
  const rows = Array.isArray(facts.rows) ? facts.rows : []
  const resultCount = Number(facts.resultCount)
  const source = String(facts.source || '')
  const dataMode = String(facts.dataMode || '')
  const factLoadStatus = String(facts.factLoadStatus || '')
  const contractAligned = Number.isInteger(resultCount)
    && resultCount === rows.length
    && source === 'production'
    && dataMode === 'production'
    && factLoadStatus === 'loaded'
  return Object.freeze({
    version: QUOTE_COMPARISON_PRODUCTION_ACCEPTANCE_ADAPTER_VERSION,
    source,
    dataMode,
    factLoadStatus,
    resultCount,
    rows,
    expectedCount,
    contractAligned,
    productionDataConsistent: contractAligned && resultCount === expectedCount,
    productionUserDataWritten: false,
  })
}
