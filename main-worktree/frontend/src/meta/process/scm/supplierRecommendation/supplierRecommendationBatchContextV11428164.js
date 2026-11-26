import { executePriceApprovalSupplierRecommendationHandoffV11428161,
  priceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'

export const SUPPLIER_RECOMMENDATION_BATCH_CONTEXT_VERSION_V11428164 = 'V1.14.2.8.18.16.4'
export const SUPPLIER_RECOMMENDATION_BATCH_STORAGE_KEY_V11428164 =
  'pce.scm.supplier-recommendation.batch-context.v11428164'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryBatches = []

export function createSupplierRecommendationBatchContextV11428164(entries = [],
  now = new Date().toISOString()) {
  if (!entries.length) throw new Error('SUPPLIER_RECOMMENDATION_BATCH_EMPTY')
  const inquiryNos = [...new Set(entries.map(item => text(item.sourceInquiryNo)))]
  if (inquiryNos.length !== 1 || !inquiryNos[0]) {
    throw new Error('SUPPLIER_RECOMMENDATION_BATCH_INQUIRY_MIXED')
  }
  const runtimeContextIds = entries.map(item => text(item.runtimeContext?.runtimeContextNo))
  const materialCodes = entries.map(item => text(item.materialCode))
  if (runtimeContextIds.some(value => !value) || new Set(runtimeContextIds).size !== entries.length
    || materialCodes.some(value => !value) || new Set(materialCodes).size !== entries.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_BATCH_INSTANCE_NOT_UNIQUE')
  }
  const supplierCandidates = entries.flatMap(item => (item.supplierCandidates || []).map(candidate => freeze({
    materialCode: text(item.materialCode), supplierCode: text(candidate.supplierCode),
    supplierName: text(candidate.supplierName), quotePrice: candidate.quotePrice,
  })))
  const identity = entries.map(item => `${text(item.priceApprovalId)}-${text(item.materialCode)}`).join('_')
  return freeze({
    objectType: 'SupplierRecommendationBatchContext',
    batchId: `SRB-${inquiryNos[0]}-${identity}`,
    sourceInquiryNo: inquiryNos[0],
    priceApprovalIds: freeze([...new Set(entries.map(item => text(item.priceApprovalId)))]),
    quoteComparisonIds: freeze([...new Set(entries.map(item => text(item.quoteComparisonId)))]),
    materialCodes: freeze(materialCodes),
    supplierCandidates: freeze(supplierCandidates),
    runtimeContextIds: freeze(runtimeContextIds),
    recommendationContextCount: entries.length,
    createdAt: now,
    factScope: 'real_price_approval_handoff',
    productionDataWritten: false,
    purchaseOrderCreated: false,
  })
}

export function createSupplierRecommendationBatchStoreV11428164({ storage = browserStorage(),
  storageKey = SUPPLIER_RECOMMENDATION_BATCH_STORAGE_KEY_V11428164 } = {}) {
  const read = () => {
    if (!storage) return clone(memoryBatches)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryBatches.splice(0, memoryBatches.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  return freeze({
    list: read,
    findById: batchId => read().find(item => item.batchId === text(batchId)) || null,
    save(value) {
      const values = read()
      const index = values.findIndex(item => item.batchId === value.batchId)
      if (index < 0) values.push(clone(value)); else values.splice(index, 1, clone(value))
      return write(values).find(item => item.batchId === value.batchId)
    },
    clear: () => write([]),
  })
}

export const supplierRecommendationBatchStoreV11428164 =
  createSupplierRecommendationBatchStoreV11428164()

export function executeSupplierRecommendationBatchHandoffV11428164(inputs = [], {
  handoffStore = priceApprovalSupplierRecommendationHandoffStoreV11428161,
  batchStore = supplierRecommendationBatchStoreV11428164,
  qualificationProvider,
} = {}) {
  try {
    const uniqueInputs = [...new Map(inputs.map(input => [
      `${text(input.priceApprovalId)}::${text(input.quoteComparisonId)}::${text(input.materialCode)}`, input,
    ])).values()]
    if (!uniqueInputs.length) throw new Error('SUPPLIER_RECOMMENDATION_BATCH_EMPTY')
    const completed = uniqueInputs.map(input => {
      const result = executePriceApprovalSupplierRecommendationHandoffV11428161(
        input, handoffStore, qualificationProvider)
      if (result.result !== 'PASS') throw new Error(result.error || 'SUPPLIER_RECOMMENDATION_HANDOFF_FAILED')
      return result.handoff
    })
    const grouped = completed.reduce((result, item) => {
      const inquiryNo = text(item.preparation?.sourceInquiryNo)
      if (!result.has(inquiryNo)) result.set(inquiryNo, [])
      result.get(inquiryNo).push(item)
      return result
    }, new Map())
    const groups = [...grouped.values()]
    const batches = groups.map(group => batchStore.save(createSupplierRecommendationBatchContextV11428164(
      group.map(handoff => ({ ...handoff, sourceInquiryNo: handoff.preparation.sourceInquiryNo })),
    )))
    return freeze({ result: 'PASS', batches: freeze(batches),
      navigationTarget: '/scm/supplier-recommendations', productionDataWritten: false,
      purchaseOrderCreated: false })
  } catch (error) {
    return freeze({ result: 'FAIL', error: error.message, batches: freeze([]),
      productionDataWritten: false, purchaseOrderCreated: false })
  }
}
