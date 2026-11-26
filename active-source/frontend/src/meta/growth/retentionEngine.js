const retentionEvents = []

const oneDay = 24 * 60 * 60 * 1000

export function recordRetentionActivity(event = {}) {
  const entry = {
    tenantId: event.tenantId || event.tenant?.id || 'demo_company',
    module: event.module || 'dashboard',
    workflow: event.workflow || event.action || 'activity',
    timestamp: event.timestamp || Date.now(),
  }

  retentionEvents.push(entry)
  return entry
}

function uniqueTenantsSince(days) {
  const cutoff = Date.now() - days * oneDay
  return new Set(retentionEvents.filter((event) => event.timestamp >= cutoff).map((event) => event.tenantId)).size
}

export function calculateRetentionMetrics() {
  const activityFrequency = retentionEvents.reduce((map, event) => {
    map[event.tenantId] = (map[event.tenantId] || 0) + 1
    return map
  }, {})
  const workflowCounts = retentionEvents.reduce((map, event) => {
    map[event.workflow] = (map[event.workflow] || 0) + 1
    return map
  }, {})
  const recurringWorkflows = Object.values(workflowCounts).filter((count) => count > 1).length
  const workflowTotal = Object.keys(workflowCounts).length

  return {
    mode: 'V17_RETENTION',
    dau: uniqueTenantsSince(1),
    wau: uniqueTenantsSince(7),
    mau: uniqueTenantsSince(30),
    tenantActivityFrequency: activityFrequency,
    workflowRecurrenceRate: workflowTotal === 0 ? 0 : recurringWorkflows / workflowTotal,
    churnPrediction: retentionEvents.length === 0 ? 'UNKNOWN' : uniqueTenantsSince(7) === 0 ? 'HIGH' : 'LOW',
    engagementScore: Math.min(100, retentionEvents.length * 5 + recurringWorkflows * 10),
    totalEvents: retentionEvents.length,
  }
}

export function getRetentionHeatmap() {
  return retentionEvents.reduce((map, event) => {
    const key = `${event.tenantId}:${event.module}`
    map[key] = (map[key] || 0) + 1
    return map
  }, {})
}

export function getRetentionEvents() {
  return retentionEvents
}

export function clearRetentionEvents() {
  retentionEvents.length = 0
}
