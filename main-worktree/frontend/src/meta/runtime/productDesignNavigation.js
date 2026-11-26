// Navigation carries identity only; server facts still validate every object and source.
const identityKeys = ['companyId', 'salesOrderId', 'salesOrderItemId', 'orderEngineeringInstanceId', 'sourceRecordId', 'sourceVersion', 'authorizationId']
export function designOrderQuery(query, orderNo) {
  const result = {}
  if (orderNo) result.orderNo = String(orderNo)
  if (orderNo && String(query.orderNo || '') === String(orderNo)) {
    for (const key of identityKeys) if (query[key] != null && query[key] !== '') result[key] = query[key]
  }
  return result
}
export function designNavigationTarget(moduleId, query, target) {
  if (!['pde-product-definitions', 'pde-product-versions'].includes(moduleId) || !target.pageUrl) return target
  const [path] = target.pageUrl.split('?')
  if (!['/pde/product-definitions', '/pde/product-versions'].includes(path)) return target
  const params = new URLSearchParams(designOrderQuery(query, query.orderNo))
  return { ...target, pageUrl: path + (params.size ? '?' + params : '') }
}
