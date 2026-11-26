export const SUPPLIER_RECOMMENDATION_RUNTIME_CONTEXT_VERSION_V11428163 = 'V1.14.2.8.18.16.3'

const text = value => String(value ?? '').trim()
const freeze = value => Object.freeze(value)

export function createSupplierRecommendationEntryKeyV11428163(value = {}) {
  const priceApprovalId = text(value.priceApprovalId)
  const quoteComparisonId = text(value.quoteComparisonId || value.sourceQuoteComparisonId)
  const materialCode = text(value.materialCode)
  if (!priceApprovalId || !quoteComparisonId || !materialCode) return ''
  return `${priceApprovalId}::${quoteComparisonId}::${materialCode}`
}

export function createSupplierRecommendationRuntimeContextV11428163(input = {},
  now = new Date().toISOString()) {
  const preparation = input.preparation || null
  const source = preparation || input
  const supplierCandidates = source.supplierCandidates || []
  const priceEvidence = source.priceEvidence || []
  const historicalPriceEvidence = source.historicalPriceEvidence || []
  const entryKey = createSupplierRecommendationEntryKeyV11428163(source)
  if (!entryKey || !text(source.priceApprovalNo || source.priceApprovalId)
    || !text(source.materialName) || !supplierCandidates.length || !priceEvidence.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_RUNTIME_CONTEXT_INCOMPLETE')
  }
  return freeze({
    objectType: 'SupplierRecommendationRuntimeContext',
    runtimeContextNo: `SRRC-${entryKey.replaceAll('::', '-')}`,
    entryKey,
    priceApprovalNo: text(source.priceApprovalNo || source.priceApprovalId),
    priceApprovalId: text(source.priceApprovalId),
    quoteComparisonId: text(source.quoteComparisonId || source.sourceQuoteComparisonId),
    materialCode: text(source.materialCode),
    materialName: text(source.materialName),
    supplierCandidates: freeze(supplierCandidates.map(item => freeze({ ...item }))),
    priceEvidence: freeze(priceEvidence.map(item => freeze({ ...item }))),
    historicalPriceEvidence: freeze(historicalPriceEvidence.map(item => freeze({ ...item }))),
    preparation,
    factScope: 'real_price_approval_handoff',
    createdAt: now,
    productionDataWritten: false,
    purchaseOrderCreated: false,
  })
}

export function matchesSupplierRecommendationEntryV11428163(value = {}, entry = {}) {
  const expected = createSupplierRecommendationEntryKeyV11428163(entry)
  return Boolean(expected) && createSupplierRecommendationEntryKeyV11428163(value) === expected
}

export function resolveSupplierRecommendationEntryV11428163(records = [], entry = {}) {
  const expected = createSupplierRecommendationEntryKeyV11428163(entry)
  if (!expected) return freeze({ result: 'FAIL', error: 'SUPPLIER_RECOMMENDATION_ENTRY_INCOMPLETE',
    entryKey: '', record: null })
  const matches = records.filter(record => matchesSupplierRecommendationEntryV11428163({
    priceApprovalId: record.priceApprovalId || record.runtimeContext?.priceApprovalId,
    quoteComparisonId: record.quoteComparisonId || record.runtimeContext?.quoteComparisonId,
    materialCode: record.runtimeContext?.materialCode || record.preparation?.materialCode
      || record.recommendationContext?.materialCode,
  }, entry))
  if (matches.length !== 1) return freeze({ result: 'FAIL',
    error: matches.length ? 'SUPPLIER_RECOMMENDATION_ENTRY_NOT_UNIQUE'
      : 'SUPPLIER_RECOMMENDATION_ENTRY_NOT_FOUND', entryKey: expected, record: null })
  return freeze({ result: 'PASS', entryKey: expected, record: matches[0] })
}

export function resolveSupplierRecommendationRuntimeContextIdV11428164(records = [], runtimeContextId = '') {
  const expected = text(runtimeContextId)
  if (!expected) return freeze({ result: 'FAIL', error: 'SUPPLIER_RECOMMENDATION_RUNTIME_CONTEXT_ID_REQUIRED',
    entryKey: '', runtimeContextId: '', record: null })
  const matches = records.filter(record => text(record.runtimeContext?.runtimeContextNo) === expected
    && record.runtimeContext?.factScope === 'real_price_approval_handoff')
  if (matches.length !== 1) return freeze({ result: 'FAIL',
    error: matches.length ? 'SUPPLIER_RECOMMENDATION_RUNTIME_CONTEXT_NOT_UNIQUE'
      : 'SUPPLIER_RECOMMENDATION_RUNTIME_CONTEXT_NOT_FOUND', entryKey: '',
    runtimeContextId: expected, record: null })
  return freeze({ result: 'PASS', entryKey: text(matches[0].entryKey),
    runtimeContextId: expected, record: matches[0] })
}
