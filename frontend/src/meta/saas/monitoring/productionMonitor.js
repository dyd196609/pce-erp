const productionEvents = []

function now() {
  return Date.now()
}

function normalizeTenantId(event = {}) {
  return event.tenantId || event.tenant?.id || 'demo_company'
}

export function recordProductionEvent(event = {}) {
  const entry = {
    ...event,
    tenantId: normalizeTenantId(event),
    timestamp: now(),
  }

  productionEvents.push(entry)
  return entry
}

export function recordLatency(event = {}) {
  return recordProductionEvent({
    ...event,
    type: 'LATENCY',
    latency: Number(event.latency || event.ms || 0),
  })
}

export function recordFailure(event = {}) {
  return recordProductionEvent({
    ...event,
    type: 'FAILURE',
    message: event.message || event.error || 'unknown failure',
  })
}

export function recordTenantLoad(event = {}) {
  return recordProductionEvent({
    ...event,
    type: 'TENANT_LOAD',
    load: Number(event.load || event.requests || 1),
  })
}

export function recordModuleHealth(event = {}) {
  return recordProductionEvent({
    ...event,
    type: 'MODULE_HEALTH',
    module: event.module || 'dashboard',
    status: event.status || 'HEALTHY',
  })
}

export function getProductionEvents() {
  return productionEvents
}

export function clearProductionEvents() {
  productionEvents.length = 0
}

export function getProductionHealth() {
  const latencyEvents = productionEvents.filter((event) => event.type === 'LATENCY')
  const failureEvents = productionEvents.filter((event) => event.type === 'FAILURE')
  const tenantLoad = productionEvents.reduce((map, event) => {
    const tenantId = normalizeTenantId(event)
    map[tenantId] = (map[tenantId] || 0) + 1
    return map
  }, {})
  const moduleHealth = productionEvents
    .filter((event) => event.module)
    .reduce((map, event) => {
      map[event.module] = event.status || (event.type === 'FAILURE' ? 'DEGRADED' : 'HEALTHY')
      return map
    }, {})
  const averageLatency = latencyEvents.length === 0
    ? 0
    : latencyEvents.reduce((sum, event) => sum + Number(event.latency || 0), 0) / latencyEvents.length
  const failureRate = productionEvents.length === 0 ? 0 : failureEvents.length / productionEvents.length

  return {
    mode: 'V16_PRODUCTION_MONITOR',
    status: failureRate > 0.2 ? 'ATTENTION' : 'HEALTHY',
    latency: {
      average: Number(averageLatency.toFixed(2)),
      max: latencyEvents.reduce((max, event) => Math.max(max, Number(event.latency || 0)), 0),
      samples: latencyEvents.length,
    },
    failureRate: Number(failureRate.toFixed(4)),
    tenantLoad: {
      activeTenants: Object.keys(tenantLoad).length,
      byTenant: tenantLoad,
    },
    moduleHealth,
    totalEvents: productionEvents.length,
    lastEvents: productionEvents.slice(-10),
  }
}

export function getSystemHealthIndex() {
  const health = getProductionHealth()
  const latencyPenalty = Math.min(25, health.latency.average / 40)
  const failurePenalty = Math.min(40, health.failureRate * 100)

  return Math.max(0, Math.round(100 - latencyPenalty - failurePenalty))
}

export function getApiLatencySnapshot() {
  const health = getProductionHealth()

  return {
    average: health.latency.average,
    max: health.latency.max,
    samples: health.latency.samples,
    status: health.latency.average > 800 ? 'ATTENTION' : 'HEALTHY',
  }
}

export function getTenantLoadSnapshot() {
  return getProductionHealth().tenantLoad
}

export function getModuleUsageSnapshot() {
  const usage = productionEvents.reduce((map, event) => {
    const module = event.module || 'platform'
    map[module] = (map[module] || 0) + 1
    return map
  }, {})

  return usage
}

export function getMonitoringCenterSnapshot() {
  const health = getProductionHealth()

  return {
    monitoring: 'ACTIVE',
    health,
    systemHealthIndex: getSystemHealthIndex(),
    apiLatency: getApiLatencySnapshot(),
    tenantLoad: getTenantLoadSnapshot(),
    moduleUsage: getModuleUsageSnapshot(),
  }
}
