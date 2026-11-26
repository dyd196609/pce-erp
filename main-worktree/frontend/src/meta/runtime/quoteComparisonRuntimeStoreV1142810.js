export const QUOTE_COMPARISON_RUNTIME_STORE_VERSION = 'V1.14.2.8.18.10'
export const QUOTE_COMPARISON_RUNTIME_STORAGE_KEY = 'pce.scm.quote-comparison.runtime.v1142810'

const memoryState = { contexts: [], comparisons: [], recommendationPreparations: [] }
const clone = value => JSON.parse(JSON.stringify(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null
const emptyState = () => ({ contexts: [], comparisons: [], recommendationPreparations: [] })

export function createQuoteComparisonRuntimeStore({ storage = browserStorage(),
  storageKey = QUOTE_COMPARISON_RUNTIME_STORAGE_KEY } = {}) {
  const read = () => {
    if (!storage) return clone(memoryState)
    try {
      const parsed = JSON.parse(storage.getItem(storageKey) || 'null')
      return parsed && Array.isArray(parsed.contexts) && Array.isArray(parsed.comparisons)
        ? { ...emptyState(), ...parsed } : emptyState()
    } catch { return emptyState() }
  }
  const write = state => {
    const value = { ...emptyState(), ...clone(state) }
    memoryState.contexts.splice(0, memoryState.contexts.length, ...value.contexts)
    memoryState.comparisons.splice(0, memoryState.comparisons.length, ...value.comparisons)
    memoryState.recommendationPreparations.splice(0, memoryState.recommendationPreparations.length,
      ...value.recommendationPreparations)
    storage?.setItem(storageKey, JSON.stringify(value))
    return clone(value)
  }
  return Object.freeze({
    reload: read,
    listContexts: () => read().contexts,
    listComparisons: () => read().comparisons,
    listRecommendationPreparations: () => read().recommendationPreparations,
    findContextByInquiryNo: inquiryNo => read().contexts.find(item => item.sourceInquiryNo === inquiryNo) || null,
    saveContext(context) {
      const state = read()
      const index = state.contexts.findIndex(item => item.comparisonPreparationNo === context.comparisonPreparationNo)
      if (index < 0) state.contexts.push(clone(context)); else state.contexts.splice(index, 1, clone(context))
      return write(state).contexts.find(item => item.comparisonPreparationNo === context.comparisonPreparationNo)
    },
    saveComparisons(comparisonPreparationNo, comparisons) {
      const state = read()
      state.comparisons = state.comparisons.filter(item => item.comparisonPreparationNo !== comparisonPreparationNo)
      state.comparisons.push(...comparisons.map(item => ({ ...clone(item), comparisonPreparationNo })))
      write(state)
      return clone(comparisons)
    },
    saveRecommendationPreparation(preparation) {
      const state = read()
      const index = state.recommendationPreparations.findIndex(item =>
        item.comparisonPreparationNo === preparation.comparisonPreparationNo)
      if (index < 0) state.recommendationPreparations.push(clone(preparation))
      else state.recommendationPreparations.splice(index, 1, clone(preparation))
      write(state)
      return clone(preparation)
    },
    clear: () => write(emptyState()),
  })
}

export const quoteComparisonRuntimeStoreV1142810 = createQuoteComparisonRuntimeStore()
