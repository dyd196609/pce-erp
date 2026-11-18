export const LEGACY_RUNTIME_EXPORT_VERSION = 'V1.14.2.8.4.23-R9'
export const LEGACY_SOURCE_KEY = 'pce.scm.supplier-quote.runtime.v114289'
export const DOWNSTREAM_KEYS = Object.freeze({
  priceApprovalHandoff: 'pce.scm.price-approval.supplier-recommendation-handoff.v11428161',
  decisionBatch: 'pce.scm.supplier-recommendation.decision-batch.v11428169',
  gateDecision: 'pce.scm.purchase-order-creation-gate.decision.v1142820',
})
export const EXPORT_FILE_NAME = 'SCM-QUOTE-COMPARISON-LEGACY-SOURCE-R9.json'

const text = value => String(value ?? '').trim()
const number = value => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}
const unique = values => [...new Set(values.filter(Boolean))].sort()
const array = value => Array.isArray(value) ? value : []

function parseStorageValue(storage, key, fallback) {
  const raw = storage.getItem(key)
  if (!raw) return fallback
  try { return JSON.parse(raw) } catch { return fallback }
}

export function readLegacyRuntimeSnapshot(storage = globalThis.localStorage) {
  if (!storage || typeof storage.getItem !== 'function') throw new Error('R9_STORAGE_READ_UNAVAILABLE')
  return Object.freeze({
    runtime: parseStorageValue(storage, LEGACY_SOURCE_KEY, null),
    priceApprovalHandoffs: parseStorageValue(storage, DOWNSTREAM_KEYS.priceApprovalHandoff, []),
    decisionBatchState: parseStorageValue(storage, DOWNSTREAM_KEYS.decisionBatch, {}),
    gateDecisions: parseStorageValue(storage, DOWNSTREAM_KEYS.gateDecision, []),
  })
}

function quoteAmount(quote) {
  return number(quote?.quotePrice ?? quote?.unitPrice ?? quote?.quotationAmount ?? quote?.price)
}

function contextPairs(context) {
  const pairs = array(context?.materialSupplierCandidates)
  if (pairs.length) return pairs
  const lines = array(context?.materialLines)
  const suppliers = array(context?.supplierCandidates)
  return lines.flatMap(line => suppliers.map(supplier => ({ ...line, ...supplier })))
}

function downstreamFor(quoteComparisonNo, snapshot) {
  const handoffs = array(snapshot.priceApprovalHandoffs).filter(item =>
    text(item.quoteComparisonId || item.sourceQuoteComparisonId || item.comparisonNo) === quoteComparisonNo)
  const state = snapshot.decisionBatchState || {}
  const bindings = array(state.bindings).filter(item => text(item.quoteComparisonId) === quoteComparisonNo)
  const batches = array(state.batches).filter(batch => array(batch.sourceQuoteComparisonBatch).map(text).includes(quoteComparisonNo)
    || array(batch.items).some(item => array(item.quoteComparisonIds).map(text).includes(quoteComparisonNo)))
  const results = array(state.results).filter(result => array(result.items)
    .some(item => array(item.quoteComparisonIds).map(text).includes(quoteComparisonNo)))
  const batchNos = unique([
    ...bindings.map(item => text(item.batchId)), ...batches.map(item => text(item.batchId)),
    ...results.map(item => text(item.batchId)),
  ])
  const gates = array(snapshot.gateDecisions).filter(gate => batchNos.includes(text(gate.sourceBatchId))
    || array(gate.items).some(item => array(item.quoteComparisonIds).map(text).includes(quoteComparisonNo)))
  return Object.freeze({
    priceApprovalPreparationNos: unique([
      ...handoffs.map(item => text(item.priceApprovalPreparationNo || item.priceApprovalNo || item.priceApprovalId)),
      ...bindings.map(item => text(item.priceApprovalId)),
    ]),
    decisionBatchNos: batchNos,
    gateNos: unique(gates.map(item => text(item.gateDecisionId || item.gateNo))),
  })
}

export function buildLegacyQuoteComparisonExport(snapshot, { expectedCount = 13, exportedAt = new Date().toISOString() } = {}) {
  const runtime = snapshot?.runtime
  if (!runtime || !Array.isArray(runtime.contexts) || !Array.isArray(runtime.quotes)) {
    return Object.freeze({ version: LEGACY_RUNTIME_EXPORT_VERSION, exportStatus: 'blocked_source_missing',
      sourceStorageKey: LEGACY_SOURCE_KEY, expectedCount, recordCount: 0, exportedAt,
      records: Object.freeze([]), productionUserDataWritten: false })
  }
  const readyContexts = runtime.contexts.filter(context => context.quoteStatus === 'comparison_ready')
  const groups = new Map()
  for (const context of readyContexts) {
    for (const pair of contextPairs(context)) {
      const materialCode = text(pair.materialCode)
      const inquiryNo = text(context.inquiryNo)
      const quote = runtime.quotes.find(item =>
        text(item.supplierQuoteContextNo) === text(context.supplierQuoteContextNo)
        && text(item.materialCode) === materialCode
        && text(item.supplierCode) === text(pair.supplierCode))
      const amount = quoteAmount(quote)
      if (!quote || amount == null) continue
      const key = `${inquiryNo}::${materialCode}`
      if (!groups.has(key)) groups.set(key, { context, pair, quotes: [] })
      groups.get(key).quotes.push({ context, pair, quote, amount })
    }
  }
  const records = [...groups.values()].map(group => {
    const { context, pair } = group
    const supplierEvidence = group.quotes.map(({ quote, pair: sourcePair, amount }) => ({
      supplierId: text(quote.supplierId || quote.supplierCode || sourcePair.supplierId || sourcePair.supplierCode),
      supplierCode: text(quote.supplierCode || sourcePair.supplierCode),
      supplierName: text(quote.supplierName || sourcePair.supplierName),
      sourceQuotationNo: text(quote.quoteNo || quote.quoteId),
      quotationAmount: amount,
      currency: text(quote.currency || 'CNY'),
      quotationStatus: text(quote.quoteStatus || quote.status || context.quoteStatus),
      receivedAt: text(quote.receivedAt || quote.updatedAt || context.updatedAt) || null,
    })).sort((left, right) => `${left.sourceQuotationNo}:${left.supplierCode}`
      .localeCompare(`${right.sourceQuotationNo}:${right.supplierCode}`))
    const amounts = supplierEvidence.map(item => item.quotationAmount)
    const lowestPrice = amounts.length ? Math.min(...amounts) : null
    const quoteComparisonNo = `QC-${text(context.inquiryNo)}-${text(pair.materialCode)}`
    const downstreamReference = downstreamFor(quoteComparisonNo, snapshot)
    const ranks = [...new Set(amounts)].sort((a, b) => a - b)
    const record = {
      quoteComparisonNo,
      sourceType: 'runtime_fact',
      sourceInquiryNo: text(context.inquiryNo),
      sourceQuotationNo: unique(supplierEvidence.map(item => item.sourceQuotationNo)),
      supplierEvidence,
      materialCode: text(pair.materialCode),
      materialName: text(pair.materialName),
      quantity: number(pair.quantity),
      quotationAmount: amounts,
      lowestPrice,
      comparisonResult: supplierEvidence.map(item => ({ supplierCode: item.supplierCode,
        quotationAmount: item.quotationAmount, priceRank: ranks.indexOf(item.quotationAmount) + 1 })),
      generatedAt: text(context.updatedAt || context.createdAt) || null,
      purchaseRequestNo: text(context.sourceRequestNo) || null,
      downstreamReference,
    }
    const required = [record.quoteComparisonNo, record.sourceInquiryNo, record.materialCode,
      record.materialName, record.quantity, record.lowestPrice, record.generatedAt]
    const downstreamCount = downstreamReference.priceApprovalPreparationNos.length
      + downstreamReference.decisionBatchNos.length + downstreamReference.gateNos.length
    return Object.freeze({ ...record, integrityStatus: required.every(value => value != null && value !== '')
      && record.sourceQuotationNo.length && supplierEvidence.every(item => item.supplierCode && item.supplierName
        && item.sourceQuotationNo && item.quotationAmount != null) && downstreamCount ? 'PASS' : 'UNKNOWN' })
  }).sort((left, right) => left.quoteComparisonNo.localeCompare(right.quoteComparisonNo))
  const completeCount = records.filter(item => item.integrityStatus === 'PASS').length
  const exportStatus = records.length === expectedCount && completeCount === expectedCount
    ? 'exported' : 'blocked_incomplete_or_count_mismatch'
  return Object.freeze({
    version: LEGACY_RUNTIME_EXPORT_VERSION,
    exportStatus,
    sourceStorageKey: LEGACY_SOURCE_KEY,
    sourceReadMode: 'localStorage.getItem_only',
    expectedCount,
    recordCount: records.length,
    completeCount,
    exportedAt,
    records: Object.freeze(records),
    productionUserDataWritten: false,
  })
}

export async function sha256Hex(value) {
  const bytes = typeof value === 'string' ? new TextEncoder().encode(value) : value
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes)
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('')
}

function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

async function inspectAndRender() {
  const status = document.querySelector('#status')
  const details = document.querySelector('#details')
  try {
    const snapshot = readLegacyRuntimeSnapshot()
    const exported = buildLegacyQuoteComparisonExport(snapshot)
    globalThis.__r9Export = exported
    status.textContent = exported.exportStatus === 'exported' ? '可导出：13条完整事实' : `已阻断：检测到${exported.recordCount}条，完整${exported.completeCount || 0}条`
    status.dataset.result = exported.exportStatus
    details.textContent = JSON.stringify({ origin: location.origin, sourceStorageKey: LEGACY_SOURCE_KEY,
      recordCount: exported.recordCount, completeCount: exported.completeCount || 0,
      exportStatus: exported.exportStatus, productionUserDataWritten: false }, null, 2)
    document.querySelector('#download').disabled = false
    document.querySelector('#save-directory').disabled = false
  } catch (error) {
    status.textContent = `读取失败：${error.message || error}`
    status.dataset.result = 'read_failed'
  }
}

async function downloadExport() {
  const exported = globalThis.__r9Export
  if (!exported) return
  const json = `${JSON.stringify(exported, null, 2)}\n`
  const sha = await sha256Hex(json)
  download(EXPORT_FILE_NAME, json, 'application/json;charset=utf-8')
  download(`${EXPORT_FILE_NAME}.sha256`, `${sha}  ${EXPORT_FILE_NAME}\n`, 'text/plain;charset=utf-8')
  document.querySelector('#sha').textContent = `SHA-256: ${sha}`
}

async function saveExportToDirectory() {
  const exported = globalThis.__r9Export
  if (!exported) return
  if (typeof globalThis.showDirectoryPicker !== 'function') {
    document.querySelector('#status').textContent = '当前浏览器不支持目录选择，请使用下载按钮。'
    return
  }
  const json = `${JSON.stringify(exported, null, 2)}\n`
  const sha = await sha256Hex(json)
  const directory = await globalThis.showDirectoryPicker({ mode: 'readwrite' })
  const jsonHandle = await directory.getFileHandle(EXPORT_FILE_NAME, { create: true })
  const jsonWriter = await jsonHandle.createWritable()
  await jsonWriter.write(json)
  await jsonWriter.close()
  const shaName = `${EXPORT_FILE_NAME}.sha256`
  const shaHandle = await directory.getFileHandle(shaName, { create: true })
  const shaWriter = await shaHandle.createWritable()
  await shaWriter.write(`${sha}  ${EXPORT_FILE_NAME}\n`)
  await shaWriter.close()
  document.querySelector('#sha').textContent = `已保存JSON和SHA-256：${sha}`
}

if (typeof document !== 'undefined') {
  document.querySelector('#inspect')?.addEventListener('click', inspectAndRender)
  document.querySelector('#download')?.addEventListener('click', downloadExport)
  document.querySelector('#save-directory')?.addEventListener('click', saveExportToDirectory)
}
