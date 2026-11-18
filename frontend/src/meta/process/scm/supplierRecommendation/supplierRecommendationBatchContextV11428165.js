import { executePriceApprovalSupplierRecommendationHandoffV11428161,
  priceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { createSupplierRecommendationEntryKeyV11428163 } from './supplierRecommendationRuntimeContextV11428163.js'

export const SUPPLIER_RECOMMENDATION_BATCH_CONTEXT_VERSION_V11428165 = 'V1.14.2.8.18.16.5'
export const SUPPLIER_RECOMMENDATION_BATCH_STORAGE_KEY_V11428165 =
  'pce.scm.supplier-recommendation.batch-context.v11428165'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryState = { contexts: [], tasks: [] }

export function createSupplierRecommendationBatchContextV11428165(entries = []) {
  if (!entries.length) throw new Error('SUPPLIER_RECOMMENDATION_BATCH_EMPTY')
  const sourceInquiryNos = [...new Set(entries.map(item => text(item.sourceInquiryNo)))]
  if (sourceInquiryNos.length !== 1 || !sourceInquiryNos[0]) {
    throw new Error('SUPPLIER_RECOMMENDATION_BATCH_INQUIRY_MIXED')
  }
  const keys = entries.map(createSupplierRecommendationEntryKeyV11428163)
  if (keys.some(key => !key) || new Set(keys).size !== entries.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_BATCH_TASK_NOT_UNIQUE')
  }
  const sourcePriceApprovalIds = entries.map(item => text(item.priceApprovalId))
  return freeze({
    objectType: 'SupplierRecommendationBatchContext',
    batchId: `SRB-${sourceInquiryNos[0]}-${keys.map(key => key.replaceAll('::', '-')).join('_')}`,
    sourcePriceApprovalIds: freeze(sourcePriceApprovalIds),
    taskCount: entries.length,
  })
}

export function createSupplierRecommendationBatchTasksV11428165(batchContext, handoffs = []) {
  if (batchContext.taskCount !== handoffs.length) {
    throw new Error('SUPPLIER_RECOMMENDATION_BATCH_TASK_COUNT_MISMATCH')
  }
  return freeze(handoffs.map(handoff => {
    const runtimeContext = handoff.runtimeContext
    const entryKey = createSupplierRecommendationEntryKeyV11428163(runtimeContext)
    if (!entryKey || !text(runtimeContext?.runtimeContextNo)) {
      throw new Error('SUPPLIER_RECOMMENDATION_BATCH_RUNTIME_CONTEXT_MISSING')
    }
    return freeze({
      objectType: 'SupplierRecommendationBatchTask',
      taskId: `SRT-${entryKey.replaceAll('::', '-')}`,
      batchId: batchContext.batchId,
      runtimeContextId: text(runtimeContext.runtimeContextNo),
      entryKey,
      sourcePriceApprovalId: text(runtimeContext.priceApprovalId),
      quoteComparisonId: text(runtimeContext.quoteComparisonId),
      materialCode: text(runtimeContext.materialCode),
      materialName: text(runtimeContext.materialName),
      taskStatus: 'pending_manual_decision',
    })
  }))
}

export function createSupplierRecommendationBatchStoreV11428165({ storage = browserStorage(),
  storageKey = SUPPLIER_RECOMMENDATION_BATCH_STORAGE_KEY_V11428165 } = {}) {
  const empty = () => ({ contexts: [], tasks: [] })
  const read = () => {
    if (!storage) return clone(memoryState)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || 'null')
      return value && Array.isArray(value.contexts) && Array.isArray(value.tasks) ? value : empty()
    } catch { return empty() }
  }
  const write = state => {
    memoryState.contexts.splice(0, memoryState.contexts.length, ...clone(state.contexts))
    memoryState.tasks.splice(0, memoryState.tasks.length, ...clone(state.tasks))
    storage?.setItem(storageKey, JSON.stringify(state))
    return clone(state)
  }
  return freeze({
    listContexts: () => read().contexts,
    findContextById: batchId => read().contexts.find(item => item.batchId === text(batchId)) || null,
    listTasks: batchId => read().tasks.filter(item => item.batchId === text(batchId)),
    saveBatch(batchContext, tasks) {
      const state = read()
      state.contexts = state.contexts.filter(item => item.batchId !== batchContext.batchId)
      state.tasks = state.tasks.filter(item => item.batchId !== batchContext.batchId)
      state.contexts.push(clone(batchContext))
      state.tasks.push(...clone(tasks))
      write(state)
      return freeze({ batchContext: clone(batchContext), tasks: freeze(clone(tasks)) })
    },
    clear: () => write(empty()),
  })
}

export const supplierRecommendationBatchStoreV11428165 =
  createSupplierRecommendationBatchStoreV11428165()

export function executeSupplierRecommendationBatchSplitV11428165(inputs = [], {
  handoffStore = priceApprovalSupplierRecommendationHandoffStoreV11428161,
  batchStore = supplierRecommendationBatchStoreV11428165,
  qualificationProvider,
} = {}) {
  try {
    const uniqueInputs = [...new Map(inputs.map(input => [
      createSupplierRecommendationEntryKeyV11428163(input), input,
    ])).values()]
    if (!uniqueInputs.length || uniqueInputs.some(input => !createSupplierRecommendationEntryKeyV11428163(input))) {
      throw new Error('SUPPLIER_RECOMMENDATION_BATCH_ENTRY_INCOMPLETE')
    }
    const handoffs = uniqueInputs.map(input => {
      const result = executePriceApprovalSupplierRecommendationHandoffV11428161(
        input, handoffStore, qualificationProvider)
      if (result.result !== 'PASS') throw new Error(result.error || 'SUPPLIER_RECOMMENDATION_HANDOFF_FAILED')
      return result.handoff
    })
    const grouped = handoffs.reduce((result, handoff) => {
      const inquiryNo = text(handoff.preparation?.sourceInquiryNo)
      if (!result.has(inquiryNo)) result.set(inquiryNo, [])
      result.get(inquiryNo).push(handoff)
      return result
    }, new Map())
    const batches = [...grouped.values()].map(group => {
      const entries = group.map(handoff => ({ ...handoff.runtimeContext,
        sourceInquiryNo: handoff.preparation.sourceInquiryNo }))
      const batchContext = createSupplierRecommendationBatchContextV11428165(entries)
      const tasks = createSupplierRecommendationBatchTasksV11428165(batchContext, group)
      return batchStore.saveBatch(batchContext, tasks)
    })
    return freeze({ result: 'PASS', batches: freeze(batches), taskCount: uniqueInputs.length,
      navigationTarget: '/scm/supplier-recommendations', productionDataWritten: false,
      purchaseOrderCreated: false })
  } catch (error) {
    return freeze({ result: 'FAIL', error: error.message, batches: freeze([]), taskCount: 0,
      productionDataWritten: false, purchaseOrderCreated: false })
  }
}
