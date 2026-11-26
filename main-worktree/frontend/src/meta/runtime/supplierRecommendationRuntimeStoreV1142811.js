export const SUPPLIER_RECOMMENDATION_RUNTIME_STORE_VERSION_V1142811 = 'V1.14.2.8.18.11'
export const SUPPLIER_RECOMMENDATION_RUNTIME_STORAGE_KEY_V1142811 = 'pce.scm.supplier-recommendation.runtime.v1142811'

const memoryState = { contexts: [], approvalContexts: [], decisions: [], handoffs: [] }
const clone = value => JSON.parse(JSON.stringify(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const emptyState = () => ({ contexts: [], approvalContexts: [], decisions: [], handoffs: [] })

export function createSupplierRecommendationRuntimeStoreV1142811({ storage = browserStorage(),
  storageKey = SUPPLIER_RECOMMENDATION_RUNTIME_STORAGE_KEY_V1142811 } = {}) {
  const read = () => {
    if (!storage) return clone(memoryState)
    try {
      const value = JSON.parse(storage.getItem(storageKey) || 'null')
      return value && Array.isArray(value.contexts) && Array.isArray(value.decisions)
        ? { ...emptyState(), ...value } : emptyState()
    } catch { return emptyState() }
  }
  const write = state => {
    const value = { ...emptyState(), ...clone(state) }
    for (const key of Object.keys(memoryState)) memoryState[key].splice(0, memoryState[key].length, ...value[key])
    storage?.setItem(storageKey, JSON.stringify(value))
    return clone(value)
  }
  const save = (collection, identity, value) => {
    const state = read()
    const index = state[collection].findIndex(item => item[identity] === value[identity])
    if (index < 0) state[collection].push(clone(value)); else state[collection].splice(index, 1, clone(value))
    return write(state)[collection].find(item => item[identity] === value[identity])
  }
  return Object.freeze({
    reload: read,
    listContexts: () => read().contexts,
    listApprovalContexts: () => read().approvalContexts,
    listDecisions: () => read().decisions,
    listHandoffs: () => read().handoffs,
    findContextBySourceId: sourceObjectId => read().contexts.find(item => item.sourceObjectId === sourceObjectId) || null,
    saveContext: value => save('contexts', 'decisionContextNo', value),
    saveApprovalContext: value => save('approvalContexts', 'approvalContextNo', value),
    saveDecision: value => save('decisions', 'decisionNo', value),
    saveHandoff: value => save('handoffs', 'sourceObjectId', value),
    clear: () => write(emptyState()),
  })
}

export const supplierRecommendationRuntimeStoreV1142811 = createSupplierRecommendationRuntimeStoreV1142811()
