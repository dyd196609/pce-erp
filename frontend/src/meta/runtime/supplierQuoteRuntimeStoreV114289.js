export const SUPPLIER_QUOTE_RUNTIME_STORE_VERSION = 'V1.14.2.8.18.9'
export const SUPPLIER_QUOTE_RUNTIME_STORAGE_KEY = 'pce.scm.supplier-quote.runtime.v114289'

const memoryState = { contexts: [], quotes: [], comparisonPreparations: [] }
const clone = value => JSON.parse(JSON.stringify(value))
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null

function emptyState() {
  return { contexts: [], quotes: [], comparisonPreparations: [] }
}

export function createSupplierQuoteRuntimeStore({ storage = browserStorage(), storageKey = SUPPLIER_QUOTE_RUNTIME_STORAGE_KEY } = {}) {
  const read = () => {
    if (!storage) return clone(memoryState)
    try {
      const parsed = JSON.parse(storage.getItem(storageKey) || 'null')
      return parsed && Array.isArray(parsed.contexts) && Array.isArray(parsed.quotes)
        ? { ...emptyState(), ...parsed } : emptyState()
    } catch { return emptyState() }
  }
  const write = state => {
    const normalized = { ...emptyState(), ...clone(state) }
    memoryState.contexts.splice(0, memoryState.contexts.length, ...normalized.contexts)
    memoryState.quotes.splice(0, memoryState.quotes.length, ...normalized.quotes)
    memoryState.comparisonPreparations.splice(0, memoryState.comparisonPreparations.length,
      ...normalized.comparisonPreparations)
    storage?.setItem(storageKey, JSON.stringify(normalized))
    return clone(normalized)
  }
  return Object.freeze({
    reload: () => read(),
    listContexts: () => read().contexts,
    listQuotes: () => read().quotes,
    listComparisonPreparations: () => read().comparisonPreparations,
    findContextByPreparationNo: quotePreparationNo =>
      read().contexts.find(item => item.quotePreparationNo === quotePreparationNo) || null,
    saveContext(context) {
      const state = read()
      const index = state.contexts.findIndex(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo)
      if (index < 0) state.contexts.push(clone(context))
      else state.contexts.splice(index, 1, clone(context))
      return write(state).contexts.find(item => item.supplierQuoteContextNo === context.supplierQuoteContextNo)
    },
    saveQuote(quote) {
      const state = read()
      const index = state.quotes.findIndex(item => item.supplierQuoteContextNo === quote.supplierQuoteContextNo
        && item.materialCode === quote.materialCode && item.supplierCode === quote.supplierCode)
      if (index < 0) state.quotes.push(clone(quote))
      else state.quotes.splice(index, 1, clone(quote))
      write(state)
      return clone(quote)
    },
    saveComparisonPreparation(preparation) {
      const state = read()
      const index = state.comparisonPreparations.findIndex(item =>
        item.supplierQuoteContextNo === preparation.supplierQuoteContextNo)
      if (index < 0) state.comparisonPreparations.push(clone(preparation))
      else state.comparisonPreparations.splice(index, 1, clone(preparation))
      write(state)
      return clone(preparation)
    },
    clear() { return write(emptyState()) },
  })
}

export const supplierQuoteRuntimeStore = createSupplierQuoteRuntimeStore()
