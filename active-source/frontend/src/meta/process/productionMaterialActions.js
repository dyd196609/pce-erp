// This contract consumes current server authorization; reading is never execution permission.
export const PRODUCTION_MATERIAL_ACTIONS = Object.freeze({
  register: Object.freeze({ actionCode: 'planning.demand.create', actionName: '登记生产用料需求', moduleCode: 'PLAN', requiredPermission: 'planning.demand.create', role: 'server-original-assignment', organizationScope: 'server-production-plan', serverValidator: '/api/planning/demands/' }),
  confirm: Object.freeze({ actionCode: 'planning.production_plan.confirm', actionName: '确认生产用料需求', moduleCode: 'PLAN', requiredPermission: 'planning.production_plan.confirm', role: 'server-original-assignment', organizationScope: 'server-production-plan', serverValidator: '/api/planning/demands/' }),
  allocate: Object.freeze({ actionCode: 'warehouse.material.allocate', actionName: '确认本次原料分配', moduleCode: 'WMS', requiredPermission: 'warehouse.material.allocate', role: 'server-original-assignment', organizationScope: 'server-demand-and-stock', serverValidator: '/api/procurement/material-stock-allocations/' }),
  prepare: Object.freeze({ actionCode: 'warehouse.material.prepare', actionName: '确认本次实物备料', moduleCode: 'WMS', requiredPermission: 'warehouse.material.prepare', role: 'server-original-assignment', organizationScope: 'server-original-allocation-and-location', serverValidator: '/api/procurement/material-preparations/' }),
  issue: Object.freeze({ actionCode: 'warehouse.material.issue', actionName: '确认实际发料', moduleCode: 'WMS', serverValidator: '/api/procurement/material-issues/' }),
  receive: Object.freeze({ actionCode: 'production.material.receive', actionName: '提交本笔收讫核对', moduleCode: 'MES', serverValidator: '/api/procurement/material-receipts/' }),
  allocationPage: Object.freeze({ actionCode: 'OPEN_PRODUCTION_MATERIAL_ALLOCATION', actionName: '查看原料来源及分配', nextRoute: '/wms/inventory-balances' }),
})
export function materialActionAuthorization(facts, action) {
  if (action === 'issue' || action === 'receive') {
    const projected = facts?.actionAuthorization?.[action]
    return { enabled: projected?.allowed === true, reason: projected?.blockingReason?.message || projected?.reason || '尚未取得当前办理资格。' }
  }
  if (action === 'prepare') {
    const selected = facts?.selected
    return { enabled: selected?.canConfirm === true, reason: selected?.blockingReason?.message || selected?.statusLabel || '' }
  }
  const projected = facts?.actionAuthorization?.[action] || facts?.availableActions?.find(item => item.actionCode === PRODUCTION_MATERIAL_ACTIONS[action]?.actionCode)
  if (projected) return { enabled: projected.allowed === true || projected.enabled === true, reason: projected.reason || projected.blockingReason?.message || '' }
  // The allocation GET itself performs the exact execution permission, formal-node and scope checks.
  if (action === 'allocate' && facts?.sourceStatus === 'VERIFIED') return { enabled: true, reason: '当前来源已由分配服务核验；提交时再次校验准确版本、单位和数量。' }
  return { enabled: false, reason: facts?.blockingReason?.message || '当前服务尚未提供本动作资格；读取成功不代表允许办理。' }
}
