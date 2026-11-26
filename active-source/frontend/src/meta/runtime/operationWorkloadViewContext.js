// Same-tab navigation hints only. Never persist facts, draft values or eligibility.
export const OPERATION_WORKLOAD_VIEW_KEY = 'pce_operation_workload_view_context_v1'
const id = value => /^[1-9]\d*$/.test(String(value ?? '')) ? String(value) : ''
const scopeKey = scope => {
  const actor = id(scope?.userId), company = id(scope?.companyId)
  return actor && company && Number.isSafeInteger(scope?.authEpoch) && scope.authEpoch >= 0
    ? JSON.stringify([actor, company, scope.authEpoch]) : ''
}
const uniqueIds = values => [...new Set((Array.isArray(values) ? values : []).map(id).filter(Boolean))].slice(0, 200)
function navigation(value = {}) {
  return {
    selectedOperationId: id(value.selectedOperationId), selectedPlanId: id(value.selectedPlanId),
    selectedRoutingStepId: id(value.selectedRoutingStepId), selectedRoutePlanId: id(value.selectedRoutePlanId),
    routeExpandedStepIds: uniqueIds(value.routeExpandedStepIds),
    expandedTraceKeys: [...new Set((Array.isArray(value.expandedTraceKeys) ? value.expandedTraceKeys : [])
      .filter(key => typeof key === 'string' && key.length > 0 && key.length <= 300))].slice(0, 200),
    scrollTop: Number.isFinite(value.scrollTop) ? Math.max(0, value.scrollTop) : 0,
  }
}
export function createOperationWorkloadViewMemory({ scope, storage = () => {
  try { return typeof window === 'undefined' ? null : window.sessionStorage } catch { return null }
} }) {
  return {
    read() {
      try {
        const key = scopeKey(scope()), saved = JSON.parse(storage()?.getItem(OPERATION_WORKLOAD_VIEW_KEY) || 'null')
        return key && saved?.scope === key ? navigation(saved.navigation) : null
      } catch { return null }
    },
    write(value) {
      try {
        const key = scopeKey(scope())
        if (key) storage()?.setItem(OPERATION_WORKLOAD_VIEW_KEY, JSON.stringify({ scope: key, navigation: navigation(value) }))
      } catch { /* Storage denial must not prevent authoritative reads. */ }
    },
  }
}
export function reconcileOperationWorkloadView(value, facts, expectedCompanyId) {
  if (!id(expectedCompanyId) || String(facts?.catalog?.companyId) !== String(expectedCompanyId)) {
    throw new Error('正式目录所属公司与当前身份不一致；未恢复选择，也未展示当前事实。')
  }
  const result = navigation(value), reasons = []
  const plans = facts.catalog.productionPlans || [], operations = facts.operations || []
  const active = row => row.is_active !== false && row.isActive !== false && row.currentlyActive !== false && row.active !== false
  const has = (rows, key) => rows.some(row => String(row.id) === key && active(row))
  if (result.selectedRoutePlanId && !has(plans, result.selectedRoutePlanId)) {
    result.selectedRoutePlanId = ''; result.routeExpandedStepIds = []
    reasons.push('路线总览计划已删除、失效或不在当前公司及读取权限目录中，已仅清除该总览计划。')
  }
  if (result.selectedOperationId && !has(operations, result.selectedOperationId)) {
    result.selectedOperationId = ''; result.selectedRoutingStepId = ''
    reasons.push('详情工序已删除、失效或不在当前公司及读取权限目录中，已清除该工序及其步骤。')
  }
  if (result.selectedPlanId && !has(plans, result.selectedPlanId)) {
    result.selectedPlanId = ''; result.selectedRoutingStepId = ''
    reasons.push('详情生产计划已删除、失效或不在当前公司及读取权限目录中，已清除该详情计划及其步骤。')
  }
  const plan = plans.find(row => String(row.id) === result.selectedPlanId)
  if (result.selectedRoutingStepId && !(plan?.routingSteps || []).some(step =>
    String(step.id) === result.selectedRoutingStepId && String(step.operationId) === result.selectedOperationId && active(step))) {
    result.selectedRoutingStepId = ''
    reasons.push('原详情步骤已失效或不属于当前计划与工序，已仅清除该步骤；计划及工序选择继续保留。')
  }
  const routePlan = plans.find(row => String(row.id) === result.selectedRoutePlanId)
  const routeIds = new Set((routePlan?.allRoutingSteps || routePlan?.routingSteps || []).filter(active).map(row => String(row.id)))
  result.routeExpandedStepIds = result.routeExpandedStepIds.filter(key => routeIds.has(key))
  return { value: result, reasons }
}
