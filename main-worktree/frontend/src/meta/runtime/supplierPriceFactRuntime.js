export const SUPPLIER_PRICE_FACT_RUNTIME_VERSION = 'V1.14.2.8.4.27.2.38'

export const SUPPLIER_PRICE_FACT_EXTENSION_POINTS = Object.freeze([
  'PRICE_HISTORY_ANALYSIS',
  'PRICE_TREND_ANALYSIS',
  'PRICE_ANOMALY_DETECTION',
  'SUPPLIER_PRICE_COMPARISON',
])

const REQUIRED_FIELDS = Object.freeze([
  'priceFactId', 'supplierId', 'supplierCode', 'supplierName',
  'materialId', 'materialCode', 'materialName', 'unitPrice',
  'currency', 'unit', 'taxRate', 'deliveryPeriod', 'effectiveDate',
  'expiryDate', 'sourceType', 'sourceReference', 'status', 'statusLabel',
])

function normalizeRow(row = {}) {
  for (const field of REQUIRED_FIELDS) {
    if (!Object.prototype.hasOwnProperty.call(row, field)) {
      throw new Error(`SupplierPriceFact Runtime field unavailable: ${field}`)
    }
  }
  if (row.source !== 'SupplierPriceFactRuntime') {
    throw new Error('SupplierPriceFact Runtime source mismatch')
  }
  if (!row.supplierId || !row.supplierCode || !row.materialId || !row.materialCode) {
    throw new Error('SupplierPriceFact master-data binding unavailable')
  }
  if (!(Number(row.unitPrice) > 0) || !row.effectiveDate || !row.sourceReference) {
    throw new Error('SupplierPriceFact price source contract unavailable')
  }
  return Object.freeze({
    ...row,
    supplierDisplay: `${row.supplierCode} · ${row.supplierName}`,
    materialDisplay: `${row.materialCode} · ${row.materialName}`,
    priceDisplay: `${row.unitPrice} ${row.currency || ''}`.trim(),
    effectivePeriod: row.expiryDate
      ? `${row.effectiveDate} ~ ${row.expiryDate}`
      : `${row.effectiveDate} ~ 待补`,
  })
}

function percentDisplay(value) {
  if (value === '' || value === null || value === undefined) return '—'
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : '—'
}

function normalizeAnalysis(payload = {}) {
  if (payload.analysisMode !== 'READ_ONLY_REFERENCE'
    || payload.automaticSupplierSelection !== false
    || payload.automaticPriceDecision !== false
    || payload.automaticPurchaseOrderCreation !== false
    || Number(payload.businessProgressWriteCount) !== 0) {
    throw new Error('Supplier price intelligence crossed the read-only decision boundary')
  }
  const historyRows = (payload.priceHistoryRows || []).map((row) => Object.freeze({
    ...normalizeRow(row),
    previousPriceDisplay: row.previousPrice || '—',
    changeRatioDisplay: percentDisplay(row.changeRatio),
  }))
  const analyses = (payload.historyAnalyses || []).map((row) => Object.freeze({
    ...row,
    supplierDisplay: `${row.supplierCode} / ${row.supplierName}`,
    materialDisplay: `${row.materialCode} / ${row.materialName}`,
    priceChangeDisplay: percentDisplay(row.priceChangeRatio),
    overallChangeDisplay: percentDisplay(row.overallChangeRatio),
  }))
  const comparisons = (payload.supplierComparisons || []).map((row) => Object.freeze({
    ...row,
    supplierDisplay: `${row.supplierCode} / ${row.supplierName}`,
    materialDisplay: `${row.materialCode} / ${row.materialName}`,
    deviationDisplay: percentDisplay(row.deviationRatio),
  }))
  const anomalies = (payload.anomalies || []).map((row) => Object.freeze({
    ...row,
    supplierDisplay: `${row.supplierCode} / ${row.supplierName}`,
    materialDisplay: `${row.materialCode} / ${row.materialName}`,
    changeRatioDisplay: percentDisplay(row.changeRatio),
  }))
  return Object.freeze({
    ...payload,
    quality: Object.freeze({ ...(payload.quality || {}) }),
    priceHistoryRows: Object.freeze(historyRows),
    historyAnalyses: Object.freeze(analyses),
    supplierComparisons: Object.freeze(comparisons),
    anomalyRules: Object.freeze((payload.anomalyRules || []).map(row => Object.freeze({ ...row }))),
    anomalies: Object.freeze(anomalies),
  })
}

function normalizePriceReviewContext(context = {}) {
  const quote = normalizeRow(context.currentQuotationFact || {})
  const ruleAssist = context.ruleAssist || {}
  const decision = context.purchasePriceDecisionContext || {}
  if (context.objectType !== 'PurchasePriceReviewContext'
    || context.source !== 'SupplierPriceFactRuntime'
    || context.caseMarker !== 'TEST_CASE'
    || ruleAssist.runtimeCode !== 'PriceReviewRuleRuntime'
    || ruleAssist.resultType !== 'ASSISTIVE_PROMPT_ONLY'
    || decision.auditMode !== 'memory_session_only'
    || decision.persisted !== false
    || context.automaticPriceDecision !== false
    || context.automaticSupplierSelection !== false
    || context.automaticPriceModification !== false
    || context.automaticPurchaseOrderCreation !== false
    || Number(context.businessProgressWriteCount) !== 0) {
    throw new Error('Purchase price review context crossed the assistive-only boundary')
  }
  return Object.freeze({
    ...context,
    currentQuotationFact: quote,
    historicalPriceReference: Object.freeze({ ...(context.historicalPriceReference || {}) }),
    supplierComparison: Object.freeze({
      ...(context.supplierComparison || {}),
      currentSupplier: Object.freeze({ ...(context.supplierComparison?.currentSupplier || {}) }),
      candidates: Object.freeze((context.supplierComparison?.candidates || []).map(row => Object.freeze({
        ...row,
        supplierDisplay: `${row.supplierCode} / ${row.supplierName}`,
        materialDisplay: `${row.materialCode} / ${row.materialName}`,
        deviationDisplay: percentDisplay(row.deviationRatio),
      }))),
    }),
    supplierPerformance: Object.freeze({ ...(context.supplierPerformance || {}) }),
    ruleAssist: Object.freeze({
      ...ruleAssist,
      ruleCatalog: Object.freeze((ruleAssist.ruleCatalog || []).map(row => Object.freeze({ ...row }))),
      prompts: Object.freeze((ruleAssist.prompts || []).map(row => Object.freeze({
        ...row,
        actualDisplay: percentDisplay(row.actualValue),
      }))),
    }),
    purchasePriceDecisionContext: Object.freeze({ ...decision }),
  })
}

export function buildSupplierPriceFactRuntime(payload = {}) {
  if (payload?.factLoadFacts?.factLoadStatus !== 'success'
    || payload?.runtimeCode !== 'SupplierPriceFactRuntime'
    || payload?.runtimeModelType !== 'SupplierPriceFactModel'
    || !Array.isArray(payload?.rows)) {
    throw new Error('SupplierPriceFact Runtime facts unavailable')
  }
  const rows = Object.freeze(payload.rows.map(normalizeRow))
  if (rows.length !== Number(payload.priceFactCount)) {
    throw new Error('SupplierPriceFact Runtime count mismatch')
  }
  const keys = rows.map(row => `${row.supplierId}|${row.materialId}|${row.effectiveDate}`)
  if (new Set(keys).size !== keys.length) {
    throw new Error('SupplierPriceFact effective-period uniqueness mismatch')
  }
  if (payload.autoDecisionEnabled !== false || Number(payload.businessProgressWriteCount) !== 0) {
    throw new Error('SupplierPriceFact Runtime crossed the no-auto-decision boundary')
  }
  const intelligenceAnalysis = normalizeAnalysis(payload.intelligenceAnalysis || {})
  const purchasePriceReviewContexts = Object.freeze(
    (payload.purchasePriceReviewContexts || []).map(normalizePriceReviewContext),
  )
  if (purchasePriceReviewContexts.length !== Number(payload.purchasePriceReviewContextCount)) {
    throw new Error('Purchase price review context count mismatch')
  }
  return Object.freeze({
    rows,
    historyRows: Object.freeze([...(payload.historyRows || [])]),
    duplicateEffectivePeriodCandidates: Object.freeze([
      ...(payload.duplicateEffectivePeriodCandidates || []),
    ]),
    priceFactCount: Number(payload.priceFactCount),
    historyFactCount: Number(payload.historyFactCount),
    duplicateEffectivePeriodCount: Number(payload.duplicateEffectivePeriodCount),
    sourcePriority: Object.freeze([...(payload.sourcePriority || [])]),
    sourceCounts: Object.freeze({ ...(payload.sourceCounts || {}) }),
    intelligenceExtensionPoints: Object.freeze([
      ...(payload.intelligenceExtensionPoints || []),
    ]),
    intelligenceAnalysis,
    purchasePriceReviewContexts,
    purchasePriceReviewContextCount: Number(payload.purchasePriceReviewContextCount),
    strictFacts: Object.freeze({ ...(payload.strictFacts || {}) }),
    acceptanceFacts: Object.freeze({ ...(payload.acceptanceFacts || {}) }),
    factLoadFacts: Object.freeze({ ...(payload.factLoadFacts || {}) }),
    runtimeCode: payload.runtimeCode,
    runtimeVersion: payload.pageVersion,
    autoDecisionEnabled: false,
    businessProgressWriteCount: 0,
  })
}
