import { recordProductionEvent } from '../monitoring/productionMonitor.js'

const rateLimits = {}
const circuitBreakers = {}
const disabledTenants = {}
const disabledModules = {}
const rollbackLog = []

function moduleKey(tenantId, module) {
  return `${tenantId || 'demo_company'}:${module || 'dashboard'}`
}

export function setRateLimit(scope = 'global', limit = 1000) {
  rateLimits[scope] = Number(limit)
  recordProductionEvent({
    type: 'OPS_RATE_LIMIT',
    scope,
    limit: rateLimits[scope],
    status: 'UPDATED',
  })
  return {
    scope,
    limit: rateLimits[scope],
  }
}

export function openCircuit(scope = 'global', reason = 'manual ops control') {
  circuitBreakers[scope] = {
    open: true,
    reason,
    updatedAt: Date.now(),
  }
  recordProductionEvent({
    type: 'OPS_CIRCUIT_OPEN',
    scope,
    reason,
    status: 'ACTIVE',
  })
  return circuitBreakers[scope]
}

export function closeCircuit(scope = 'global') {
  circuitBreakers[scope] = {
    open: false,
    reason: 'closed',
    updatedAt: Date.now(),
  }
  recordProductionEvent({
    type: 'OPS_CIRCUIT_CLOSE',
    scope,
    status: 'CLOSED',
  })
  return circuitBreakers[scope]
}

export function rollbackModule(tenantId = 'demo_company', module = 'dashboard', version = 'previous') {
  const entry = {
    tenantId,
    module,
    version,
    status: 'ROLLBACK_SIMULATED',
    timestamp: Date.now(),
  }

  rollbackLog.push(entry)
  recordProductionEvent({
    type: 'OPS_ROLLBACK',
    tenantId,
    module,
    version,
    status: 'SIMULATED',
  })
  return entry
}

export function disableTenant(tenantId = 'demo_company', reason = 'manual ops disable') {
  disabledTenants[tenantId] = {
    disabled: true,
    reason,
    updatedAt: Date.now(),
  }
  recordProductionEvent({
    type: 'OPS_DISABLE_TENANT',
    tenantId,
    reason,
    status: 'DISABLED',
  })
  return disabledTenants[tenantId]
}

export function enableTenant(tenantId = 'demo_company') {
  delete disabledTenants[tenantId]
  recordProductionEvent({
    type: 'OPS_ENABLE_TENANT',
    tenantId,
    status: 'ENABLED',
  })
  return {
    tenantId,
    disabled: false,
  }
}

export function disableModule(tenantId = 'demo_company', module = 'dashboard', reason = 'manual ops disable') {
  disabledModules[moduleKey(tenantId, module)] = {
    tenantId,
    module,
    disabled: true,
    reason,
    updatedAt: Date.now(),
  }
  recordProductionEvent({
    type: 'OPS_DISABLE_MODULE',
    tenantId,
    module,
    reason,
    status: 'DISABLED',
  })
  return disabledModules[moduleKey(tenantId, module)]
}

export function enableModule(tenantId = 'demo_company', module = 'dashboard') {
  delete disabledModules[moduleKey(tenantId, module)]
  recordProductionEvent({
    type: 'OPS_ENABLE_MODULE',
    tenantId,
    module,
    status: 'ENABLED',
  })
  return {
    tenantId,
    module,
    disabled: false,
  }
}

export function canRunModule(tenantId = 'demo_company', module = 'dashboard') {
  const disabledTenant = disabledTenants[tenantId]
  const disabledModule = disabledModules[moduleKey(tenantId, module)]
  const globalCircuit = circuitBreakers.global?.open
  const moduleCircuit = circuitBreakers[moduleKey(tenantId, module)]?.open

  return {
    allowed: !disabledTenant && !disabledModule && !globalCircuit && !moduleCircuit,
    tenantDisabled: Boolean(disabledTenant),
    moduleDisabled: Boolean(disabledModule),
    circuitOpen: Boolean(globalCircuit || moduleCircuit),
  }
}

export function getOpsState() {
  return {
    mode: 'V16_OPS_CONTROL_CENTER',
    rateLimits: {
      ...rateLimits,
    },
    circuitBreakers: {
      ...circuitBreakers,
    },
    disabledTenants: {
      ...disabledTenants,
    },
    disabledModules: {
      ...disabledModules,
    },
    rollbackLog: [...rollbackLog],
  }
}
