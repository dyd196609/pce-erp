const syncState = {
  purchase: {},
  finance: {},
  crm: {},
  scm: {},
  inventory: {},
}
const syncConflicts = []

function moduleKey(source = '') {
  if (source === 'purchaseOrder') return 'purchase'
  return source
}

export function syncCrossModuleState(sourceModule, targetModule, payload = {}) {
  const source = moduleKey(sourceModule)
  const target = moduleKey(targetModule)
  const key = payload.purchaseOrderId || payload.customerId || payload.skuId || payload.supplierId || payload.id || payload.eventId || 'latest'
  const previous = syncState[target]?.[key]
  const next = {
    source,
    target,
    key,
    payload,
    updatedAt: Date.now(),
  }

  if (previous && previous.source !== source && previous.payload?.workflow_state !== payload.workflow_state) {
    syncConflicts.unshift({
      key,
      source,
      target,
      previous,
      next,
      reason: 'STATE_DESYNC_CONFLICT',
      timestamp: Date.now(),
    })
  }

  syncState[target] = {
    ...(syncState[target] || {}),
    [key]: next,
  }

  return next
}

export function getCrossModuleState() {
  return {
    state: syncState,
    conflicts: [...syncConflicts],
    consistent: syncConflicts.length === 0,
  }
}
