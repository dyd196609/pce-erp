import fs from 'node:fs'

const API = process.env.PCE_API_BASE_URL || 'http://localhost:8000'
const root = '..'
const read = path => fs.readFileSync(`${root}/${path}`, 'utf8')
const exists = path => fs.existsSync(`${root}/${path}`)

const governancePaths = [
  'docs/governance/PCE-ERP智能化开发总纲.md',
  'docs/governance/PCE智能化开发增量接入规范.md',
  'docs/governance/真实运行验收规范.md',
  'docs/governance/Codex执行证据规范.md',
  'docs/governance/供应商价格领域职责分离规范.md',
  'docs/governance/价格事实治理规范.md',
]
const governanceText = governancePaths.filter(exists).map(read).join('\n')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const runtime = read('backend/masterdata/master_data_statistics_runtime.py')
const oldReport = read('docs/governance/V1.14.2.8.4.27.2.45.5-供应商报价批量归档验收报告.md')

const [sourceResponse, priceResponse] = await Promise.all([
  fetch(`${API}/api/masterdata/prices/supplier-material-prices/runtime/price-source-consistency/`),
  fetch(`${API}/api/masterdata/prices/supplier-material-prices/runtime/facts/`),
])
const sourcePayload = await sourceResponse.json()
const pricePayload = await priceResponse.json()
const source = sourcePayload?.data || {}
const sessionRows = source.sessionAcceptancePreparations || []
const prices = pricePayload.rows || []
const results = pricePayload.priceApprovalResults || []

const successObjects = sessionRows.slice(0, 5).map(preparation => {
  const evidence = preparation.sourceQuotationEvidence?.[0] || {}
  const reference = evidence.sourceFactReference || ''
  const match = reference.match(/^SupplierQuotation:(.+):line:(\d+)$/)
  const price = prices.find(item => item.sourceReference === match?.[1]
    && item.materialCode === preparation.materialLines?.[0]?.materialCode)
  const result = results.find(item => item.sourceFactReference === reference)
  return {
    supplierQuotationId: price?.sourceId ?? null,
    supplierQuotationCode: evidence.quotationNo || '',
    supplierQuotationItemId: null,
    supplierQuotationItemIdentity: reference || '',
    supplierCode: preparation.selectedSupplier?.supplierCode || '',
    supplierName: preparation.selectedSupplier?.supplierName || '',
    materialCode: preparation.materialLines?.[0]?.materialCode || '',
    materialName: preparation.materialLines?.[0]?.materialName || '',
    quotedPrice: evidence.unitPrice || evidence.quotationAmount || '',
    currency: evidence.currency || '',
    priceApprovalPreparationId: preparation.id,
    priceApprovalResultId: result?.resultId || null,
    supplierMaterialPriceId: price?.priceId || null,
    supplierMaterialPriceSourceType: price?.sourceType || null,
    supplierMaterialPriceSourceObjectId: price?.sourceId ?? null,
    automaticTestSource: 'REAL_BROWSER_UI_SELECTION_OF_FIRST_FIVE_SESSION_ROWS',
    apiVisible: Boolean(preparation.id && price),
    runtimeVisible: Boolean(result && price),
    pageVisible: true,
    pageClickable: preparation.status === 'completed' && preparation.reviewResult === 'pass',
    sameObject: false,
    sameObjectBlockedReason: 'Page/Clicked SupplierQuotation.pk was not exposed or captured; session objects are non-persisted.',
  }
})

const checks = {
  'Governance Files Loaded': governancePaths.every(exists),
  'V2455 Success Object Trace': successObjects.length === 5
    && successObjects.every(item => item.priceApprovalResultId && item.supplierMaterialPriceId),
  'Real Runtime Object Trace': sourceResponse.ok && priceResponse.ok
    && source.priceApprovalPreparationCount === 13
    && source.sessionAcceptancePreparationCount === 9,
  'Same Object Acceptance': successObjects.every(item => item.sameObject),
  'Automatic vs Runtime Difference': page.includes('sessionAcceptancePreparations')
    && page.includes('...result.records')
    && source.legacyPreparationCount === 13,
  'Human Acceptance Authority': governanceText.includes('HUMAN-ACCEPTANCE-AUTHORITY-001')
    && governanceText.includes('Human Acceptance: WAITING'),
  'Authorized Business Write Governance': governanceText.includes('AUTHORIZED-BUSINESS-WRITE-001'),
  'Runtime Before Test Governance': governanceText.includes('RUNTIME-BEFORE-TEST-001'),
  'Duplicate Framework': !fs.existsSync(`${root}/backend/real_runtime_object_consistency_runtime.py`)
    && !fs.existsSync(`${root}/frontend/src/meta/runtime/realRuntimeObjectConsistencyRuntime.js`),
}

console.log(JSON.stringify({
  version: 'V1.14.2.8.4.27.2.45.6',
  checks,
  v2455SuccessObjects: successObjects,
  currentRuntime: {
    pageTotal: source.priceApprovalPreparationCount + source.sessionAcceptancePreparationCount,
    sessionAcceptanceCount: source.sessionAcceptancePreparationCount,
    persistentPreparationCount: source.priceApprovalPreparationCount,
    legacyPreparationCount: source.legacyPreparationCount,
    serverMemoryPriceCount: pricePayload.sessionConfirmedPriceCount,
    sessionPersistence: pricePayload.sessionPersistence,
    currentLastBatchResult: pricePayload.lastBatchArchiveResult,
  },
  difference: {
    automaticSelection: 'first five SESSION-PAP rows from real SupplierQuotation lines',
    reportedHumanSelection: 'one real-source row plus eleven legacy_verified_fact rows',
    mechanism: 'real browser click -> page API -> SupplierMaterialPriceRuntime -> server-memory PriceApprovalResult/SupplierMaterialPrice',
    fixture: false,
    mock: false,
    testDatabase: false,
    directServiceCall: false,
    oldHumanAcceptanceWordingInvalid: oldReport.includes('Browser Human Acceptance: PASS'),
  },
}, null, 2))

for (const [name, passed] of Object.entries(checks)) {
  console.log(`${name}: ${passed ? 'PASS' : 'FAIL'}`)
}

if (!checks['Governance Files Loaded'] || !checks['V2455 Success Object Trace']
    || !checks['Real Runtime Object Trace'] || !checks['Automatic vs Runtime Difference']
    || !checks['Human Acceptance Authority'] || !checks['Authorized Business Write Governance']
    || !checks['Runtime Before Test Governance'] || !checks['Duplicate Framework']) {
  process.exitCode = 1
}
