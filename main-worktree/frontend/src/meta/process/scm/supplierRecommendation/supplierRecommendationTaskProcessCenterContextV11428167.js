import { supplierRecommendationTaskStoreV11428167 } from './supplierRecommendationTaskRuntimeV11428167.js'

export const SUPPLIER_RECOMMENDATION_TASK_PROCESS_CENTER_VERSION_V11428167 = 'V1.14.2.8.18.16.7'
export const SUPPLIER_RECOMMENDATION_ACTIVE_TASK_KEY_V11428167 =
  'pce.scm.supplier-recommendation.process-center.active-task.v11428167'

const text = value => String(value ?? '').trim()
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null

export function createSupplierRecommendationTaskProcessCenterProviderV11428167({
  storage = browserStorage(), taskStore = supplierRecommendationTaskStoreV11428167,
  storageKey = SUPPLIER_RECOMMENDATION_ACTIVE_TASK_KEY_V11428167,
} = {}) {
  const activeId = () => {
    try { return text(storage?.getItem(storageKey)) } catch { return '' }
  }
  const resolveTask = () => taskStore.findById(activeId()) || taskStore.list().at(-1) || null
  return Object.freeze({
    resolveTask,
    resolveTaskId: () => text(resolveTask()?.taskId),
    buildPageUrl() {
      const taskId = text(resolveTask()?.taskId)
      return taskId ? `/scm/supplier-recommendations?taskId=${encodeURIComponent(taskId)}` : ''
    },
    markActive(taskId) {
      const task = taskStore.findById(taskId)
      if (!task) return Object.freeze({ result: 'FAIL', error: 'SUPPLIER_RECOMMENDATION_TASK_NOT_FOUND' })
      storage?.setItem(storageKey, task.taskId)
      return Object.freeze({ result: 'PASS', taskId: task.taskId, runtimeContextId: task.runtimeContextId })
    },
  })
}

export const supplierRecommendationTaskProcessCenterProviderV11428167 =
  createSupplierRecommendationTaskProcessCenterProviderV11428167()
