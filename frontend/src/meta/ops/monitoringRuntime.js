import {
  getProductionEvents,
  getProductionHealth,
  recordFailure,
  recordLatency,
  recordModuleHealth,
  recordTenantLoad,
} from '../saas/monitoring/productionMonitor.js'
import { getOpsState } from '../saas/ops/opsControlCenter.js'
import { getUsage } from '../saas/billing/billingEngine.js'
import { listTenants } from '../tenant/tenantManager.js'

function resolveTenantId(context = {}) {
  return context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'commercial_demo'
}

export function trackPerformance(context = {}) {
  const tenantId = resolveTenantId(context)
  const latency = recordLatency({
    tenantId,
    module: context.module || 'dashboard',
    action: context.action || 'commercial_dashboard',
    latency: context.latency || 96,
    status: 'HEALTHY',
  })
  const load = recordTenantLoad({
    tenantId,
    requests: context.requests || 42,
    status: 'ACTIVE',
  })
  const moduleHealth = recordModuleHealth({
    tenantId,
    module: context.module || 'dashboard',
    status: 'HEALTHY',
  })

  return {
    mode: 'COMMERCIAL_PERFORMANCE_TRACKING',
    latency,
    load,
    moduleHealth,
  }
}

export function monitorErrors(context = {}) {
  if (!context.error) {
    return {
      mode: 'COMMERCIAL_ERROR_MONITORING',
      status: 'CLEAR',
      error: null,
    }
  }

  return {
    mode: 'COMMERCIAL_ERROR_MONITORING',
    status: 'RECORDED',
    error: recordFailure({
      tenantId: resolveTenantId(context),
      module: context.module || 'dashboard',
      error: context.error,
    }),
  }
}

export function analyzeTenantUsage(context = {}) {
  const tenantId = resolveTenantId(context)
  const usage = getUsage(tenantId)

  return {
    mode: 'COMMERCIAL_TENANT_USAGE_ANALYTICS',
    tenantId,
    tenantCount: listTenants().length,
    usageRecords: usage.length,
    apiCalls: usage.filter((entry) => entry.type === 'api').reduce((sum, entry) => sum + entry.units, 0),
    executions: usage.filter((entry) => entry.type === 'execution').reduce((sum, entry) => sum + entry.units, 0),
    aiDecisions: usage.filter((entry) => entry.type === 'aiDecision').reduce((sum, entry) => sum + entry.units, 0),
  }
}

export function initMonitoringSystem(context = {}) {
  const performance = trackPerformance(context)
  const errors = monitorErrors(context)
  const health = getProductionHealth()
  const tenantUsage = analyzeTenantUsage(context)
  const ops = getOpsState()

  return {
    mode: 'COMMERCIAL_MONITORING_RUNTIME',
    status: health.status,
    health,
    performance,
    errors,
    tenantUsage,
    ops,
    events: getProductionEvents().slice(-10),
  }
}
