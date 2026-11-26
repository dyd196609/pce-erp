export const SUPPLIER_RECOMMENDATION_ENTRY_ROUTE_VERSION_V1142817 = 'V1.14.2.8.18.17'
export const SUPPLIER_RECOMMENDATION_ENTRY_ROUTE_NAME_V1142817 = 'ScmSupplierRecommendationTask'
export const SUPPLIER_RECOMMENDATION_ENTRY_ROUTE_BASE_V1142817 = '/scm/supplier-recommendation-task'

const text = value => String(value ?? '').trim()

export function buildSupplierRecommendationEntryRouteV1142817(taskId) {
  const value = text(taskId)
  return value ? `${SUPPLIER_RECOMMENDATION_ENTRY_ROUTE_BASE_V1142817}/${encodeURIComponent(value)}` : ''
}

export function resolveSupplierRecommendationEntryTaskIdV1142817(route = {}) {
  return text(route.params?.taskId)
}
