import { supplierRecommendationTaskStoreV11428167 } from './supplierRecommendationTaskRuntimeV11428167.js'
import { supplierRecommendationDecisionBatchStoreV11428169 } from './supplierRecommendationDecisionBatchV11428169.js'

export const SUPPLIER_RECOMMENDATION_ROUTE_CONTEXT_VERSION_V11428171 = 'V1.14.2.8.18.17.1'
export const SUPPLIER_RECOMMENDATION_PAGE_ROUTE_V11428171 = '/scm/supplier-recommendation'
export const SUPPLIER_RECOMMENDATION_PAGE_CONTEXT_KEY_V11428171 =
  'pce.scm.supplier-recommendation.page-context.v11428171'

const text = value => String(value ?? '').trim()
const freeze = value => Object.freeze(value)
const frozen = value => freeze(JSON.parse(JSON.stringify(value)))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null

export function createSupplierRecommendationRouteContextResolverV11428171({
  storage = browserStorage(), decisionBatchStore = supplierRecommendationDecisionBatchStoreV11428169,
  taskStore = supplierRecommendationTaskStoreV11428167,
  storageKey = SUPPLIER_RECOMMENDATION_PAGE_CONTEXT_KEY_V11428171,
} = {}) {
  const readActiveBatchId = () => {
    try { return text(storage?.getItem(storageKey)) || text(decisionBatchStore.activeBatchId()) } catch {
      return text(decisionBatchStore.activeBatchId())
    }
  }
  const resolveBatch = batchId => {
    const decisionBatch = decisionBatchStore.findById(batchId)
    if (!decisionBatch) return freeze({ result: 'FAIL', error: 'DECISION_BATCH_CONTEXT_NOT_FOUND' })
    const bindings = decisionBatchStore.listBindings(decisionBatch.batchId)
    const tasks = bindings.map(binding => taskStore.findById(binding.taskId))
    if (!bindings.length || tasks.some(task => !task)) {
      return freeze({ result: 'FAIL', error: 'TASK_CONTEXT_NOT_FOUND' })
    }
    if (!decisionBatch.items.length || bindings.some(binding =>
      !decisionBatch.items.some(item => item.materialCode === binding.materialCode))) {
      return freeze({ result: 'FAIL', error: 'DECISION_ITEM_CONTEXT_NOT_FOUND' })
    }
    return freeze({ result: 'PASS', pageRoute: SUPPLIER_RECOMMENDATION_PAGE_ROUTE_V11428171,
      task: frozen(tasks[0]), tasks: frozen(tasks), decisionBatch: frozen(decisionBatch),
      decisionItems: frozen(decisionBatch.items), providerTaskId: decisionBatch.batchId })
  }
  return freeze({
    pageRoute: SUPPLIER_RECOMMENDATION_PAGE_ROUTE_V11428171,
    activate(batchId) {
      const resolved = resolveBatch(text(batchId))
      if (resolved.result !== 'PASS') return resolved
      storage?.setItem(storageKey, resolved.decisionBatch.batchId)
      decisionBatchStore.markActive(resolved.decisionBatch.batchId)
      return resolved
    },
    resolve() {
      const batchId = readActiveBatchId()
      return batchId ? resolveBatch(batchId)
        : freeze({ result: 'FAIL', error: 'SUPPLIER_RECOMMENDATION_CONTEXT_NOT_FOUND' })
    },
    buildPageRoute: () => SUPPLIER_RECOMMENDATION_PAGE_ROUTE_V11428171,
  })
}

export const supplierRecommendationRouteContextResolverV11428171 =
  createSupplierRecommendationRouteContextResolverV11428171()
