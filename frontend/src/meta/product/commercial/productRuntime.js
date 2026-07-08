import { initAuthSystem } from './authRuntime.js'
import { initBillingSystem } from '../../saas/billing/billingRuntime.js'
import { initTenantSystem } from '../../saas/tenant/tenantRuntime.js'
import { initDeploymentSystem } from '../../deployment/deploymentRuntime.js'
import { initMonitoringSystem } from '../../ops/monitoringRuntime.js'

const bootCache = {}

function resolveTenantId(context = {}) {
  return context.tenantId || context.runtimeState?.tenant?.id || 'commercial_demo'
}

function resolvePlan(context = {}) {
  return context.plan || context.runtimeState?.plan || 'enterprise'
}

export function startCommercialSystem(context = {}) {
  const tenantId = resolveTenantId(context)
  const cacheKey = `${tenantId}:${resolvePlan(context)}`

  if (bootCache[cacheKey] && context.refresh !== true) {
    return bootCache[cacheKey]
  }

  const commercialContext = {
    ...context,
    tenantId,
    plan: resolvePlan(context),
    companyName: context.companyName || context.runtimeState?.tenant?.name || 'Commercial Demo',
    email: context.email || 'owner@profitos.local',
    role: context.role || context.runtimeState?.role || 'admin',
  }
  const auth = initAuthSystem(commercialContext)
  const tenant = initTenantSystem(commercialContext)
  const billing = initBillingSystem({
    ...commercialContext,
    tenant: tenant.tenant,
    enabledModules: tenant.modules.activeModules,
  })
  const deployment = initDeploymentSystem({
    ...commercialContext,
    tenant: tenant.tenant,
    modules: tenant.modules.activeModules,
  })
  const monitoring = initMonitoringSystem(commercialContext)
  const result = {
    mode: 'COMMERCIAL_RELEASE_V1',
    commercialMode: 'ON',
    productionReady: true,
    billingActive: 'ENABLED',
    tenantSystem: 'ACTIVE',
    auth,
    billing,
    tenant,
    deployment,
    monitoring,
    metrics: {
      registeredUsers: auth.registeredUsers.length,
      activeTenants: tenant.tenants.length,
      billingTotal: billing.enterprise.bill.total,
      deploymentReady: deployment.status === 'DEPLOYABLE',
      systemHealth: monitoring.health.status,
    },
  }

  bootCache[cacheKey] = result
  return result
}
