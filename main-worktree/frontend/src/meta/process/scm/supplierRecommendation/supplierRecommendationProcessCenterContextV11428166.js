import { priceApprovalSupplierRecommendationHandoffStoreV11428161 } from '../priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js'

export const SUPPLIER_RECOMMENDATION_PROCESS_CENTER_CONTEXT_VERSION_V11428166 = 'V1.14.2.8.18.16.6'
export const SUPPLIER_RECOMMENDATION_PROCESS_CENTER_ACTIVE_KEY_V11428166 =
  'pce.scm.supplier-recommendation.process-center.active-runtime-context.v11428166'

const text = value => String(value ?? '').trim()
const browserStorage = () => typeof window !== 'undefined' ? window.localStorage : null

export function createSupplierRecommendationProcessCenterContextProviderV11428166({
  storage = browserStorage(),
  runtimeContextLoader = () => priceApprovalSupplierRecommendationHandoffStoreV11428161.listRuntimeContexts(),
  storageKey = SUPPLIER_RECOMMENDATION_PROCESS_CENTER_ACTIVE_KEY_V11428166,
} = {}) {
  const listRealContexts = () => (runtimeContextLoader() || []).filter(item => item?.factScope
    === 'real_price_approval_handoff' && text(item.runtimeContextNo))
  const readActiveId = () => {
    try { return text(storage?.getItem(storageKey)) } catch { return '' }
  }
  const resolveContext = () => {
    const contexts = listRealContexts()
    const activeId = readActiveId()
    const active = contexts.find(item => item.runtimeContextNo === activeId)
    if (active) return active
    return contexts.slice().sort((left, right) => String(left.createdAt)
      .localeCompare(String(right.createdAt))).at(-1) || null
  }
  return Object.freeze({
    resolveRuntimeContext: resolveContext,
    resolveRuntimeContextId: () => text(resolveContext()?.runtimeContextNo),
    buildPageUrl() {
      const runtimeContextId = text(resolveContext()?.runtimeContextNo)
      return runtimeContextId
        ? `/scm/supplier-recommendations?runtimeContextId=${encodeURIComponent(runtimeContextId)}` : ''
    },
    markActive(runtimeContextId) {
      const expected = text(runtimeContextId)
      if (!expected || !listRealContexts().some(item => item.runtimeContextNo === expected)) {
        return Object.freeze({ result: 'FAIL', error: 'RUNTIME_CONTEXT_NOT_REAL_OR_NOT_FOUND' })
      }
      storage?.setItem(storageKey, expected)
      return Object.freeze({ result: 'PASS', runtimeContextId: expected })
    },
  })
}

export const supplierRecommendationProcessCenterContextProviderV11428166 =
  createSupplierRecommendationProcessCenterContextProviderV11428166()
