import { executePriceApprovalSupplierRecommendationHandoffV11428161,
  priceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'
import { executeSupplierRecommendationBatchSplitV11428165 } from './supplierRecommendationBatchContextV11428165.js'
import { createSupplierRecommendationEntryKeyV11428163 } from './supplierRecommendationRuntimeContextV11428163.js'

export const SUPPLIER_RECOMMENDATION_TASK_RUNTIME_VERSION_V11428167 = 'V1.14.2.8.18.16.7'
export const SUPPLIER_RECOMMENDATION_TASK_STORAGE_KEY_V11428167 =
  'pce.scm.supplier-recommendation.task-runtime.v11428167'

const text = value => String(value ?? '').trim()
const clone = value => JSON.parse(JSON.stringify(value))
const freeze = value => Object.freeze(value)
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const memoryTasks = []

export function createSupplierRecommendationTaskV11428167(runtimeContext = {}) {
  const entryKey = createSupplierRecommendationEntryKeyV11428163(runtimeContext)
  const runtimeContextId = text(runtimeContext.runtimeContextNo)
  if (!entryKey || !runtimeContextId || runtimeContext.factScope !== 'real_price_approval_handoff') {
    throw new Error('SUPPLIER_RECOMMENDATION_TASK_RUNTIME_CONTEXT_INVALID')
  }
  return freeze({
    taskId: `SRT-${entryKey.replaceAll('::', '-')}`,
    sourcePriceApprovalIds: freeze([text(runtimeContext.priceApprovalId)]),
    runtimeContextId,
    status: 'pending_manual_decision',
    currentAssignee: 'unassigned',
  })
}

export function createSupplierRecommendationTaskStoreV11428167({ storage = browserStorage(),
  storageKey = SUPPLIER_RECOMMENDATION_TASK_STORAGE_KEY_V11428167 } = {}) {
  const read = () => {
    if (!storage) return clone(memoryTasks)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || '[]')
      return Array.isArray(value) ? value : []
    } catch { return [] }
  }
  const write = values => {
    memoryTasks.splice(0, memoryTasks.length, ...clone(values))
    storage?.setItem(storageKey, JSON.stringify(values))
    return clone(values)
  }
  const save = task => {
    const values = read()
    const index = values.findIndex(item => item.taskId === task.taskId)
    if (index < 0) values.push(clone(task)); else values.splice(index, 1, clone(task))
    return write(values).find(item => item.taskId === task.taskId)
  }
  return freeze({
    list: read,
    findById: taskId => read().find(item => item.taskId === text(taskId)) || null,
    findByRuntimeContextId: runtimeContextId => read().find(
      item => item.runtimeContextId === text(runtimeContextId)) || null,
    ensure(runtimeContext) {
      const proposed = createSupplierRecommendationTaskV11428167(runtimeContext)
      return this.findById(proposed.taskId) || save(proposed)
    },
    update(taskId, { status, currentAssignee } = {}) {
      const current = this.findById(taskId)
      if (!current) throw new Error('SUPPLIER_RECOMMENDATION_TASK_NOT_FOUND')
      return save(freeze({ ...current, status: text(status || current.status),
        currentAssignee: text(currentAssignee || current.currentAssignee) }))
    },
    clear: () => write([]),
  })
}

export const supplierRecommendationTaskStoreV11428167 =
  createSupplierRecommendationTaskStoreV11428167()

export function executeSupplierRecommendationTaskEntryV11428167(input = {}, {
  handoffStore = priceApprovalSupplierRecommendationHandoffStoreV11428161,
  taskStore = supplierRecommendationTaskStoreV11428167,
  qualificationProvider,
} = {}) {
  const handoffResult = executePriceApprovalSupplierRecommendationHandoffV11428161(
    input, handoffStore, qualificationProvider)
  if (handoffResult.result !== 'PASS') return freeze({ ...handoffResult, task: null })
  const task = taskStore.ensure(handoffResult.handoff.runtimeContext)
  return freeze({ result: 'PASS', handoff: handoffResult.handoff, task,
    navigationTarget: '/scm/supplier-recommendations', productionDataWritten: false,
    purchaseOrderCreated: false })
}

export function executeSupplierRecommendationBatchTaskEntryV11428167(inputs = [], options = {}) {
  const taskStore = options.taskStore || supplierRecommendationTaskStoreV11428167
  const result = executeSupplierRecommendationBatchSplitV11428165(inputs, options)
  if (result.result !== 'PASS') return freeze({ ...result, recommendationTasks: freeze([]) })
  const recommendationTasks = result.batches.flatMap(batch => batch.tasks.map(taskIndex => {
    const runtimeContext = (options.handoffStore
      || priceApprovalSupplierRecommendationHandoffStoreV11428161).listRuntimeContexts()
      .find(item => item.runtimeContextNo === taskIndex.runtimeContextId)
    if (!runtimeContext) throw new Error('SUPPLIER_RECOMMENDATION_BATCH_TASK_RUNTIME_CONTEXT_NOT_FOUND')
    return taskStore.ensure(runtimeContext)
  }))
  return freeze({ ...result, recommendationTasks: freeze(recommendationTasks) })
}
