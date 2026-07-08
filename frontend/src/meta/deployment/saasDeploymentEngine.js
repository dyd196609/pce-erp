import { getAllSchemas } from '../core/schemaRegistry.js'
import { freezeArchitecture } from '../core/systemConvergenceFreeze.js'
import { standardizeModulesForProduction } from '../product/moduleStandardizationCore.js'
import { onboardTenant } from '../saas/onboarding/userOnboardingEngine.js'
import { enableModule, getEnabledModules } from '../saas/market/moduleMarketplace.js'
import { calculateSaasBill } from '../saas/billing/billingEngine.js'
import { getProductionHealth, recordProductionEvent } from '../saas/monitoring/productionMonitor.js'

export function packageProductionBuild(context = {}) {
  const schemas = context.schemas || getAllSchemas()
  const registry = standardizeModulesForProduction(schemas, context)

  return {
    mode: 'PRODUCTION_BUILD_PACKAGING',
    packageName: context.packageName || 'profitos-enterprise-saas',
    bundleFormat: 'PROFITOS_PRODUCTION_SAAS_PACKAGE',
    moduleCount: registry.moduleCount,
    registry,
    buildProfile: {
      debugHooks: false,
      experimentalLayers: 'DISABLED',
      apiStrictMode: true,
      frozenRuntimeOnly: true,
    },
  }
}

export function provisionTenantForDeployment(context = {}) {
  const tenant = context.tenant || onboardTenant({
    tenantId: context.tenantId || 'production_customer',
    companyName: context.companyName || 'Production Customer',
    email: context.email || 'owner@customer.local',
    plan: context.plan || 'enterprise',
    source: 'production_cut',
  })

  return {
    mode: 'PRODUCTION_TENANT_PROVISIONING',
    tenant,
    tenantId: tenant.tenant?.id || tenant.id,
    status: tenant.status || 'TENANT_READY',
  }
}

export function enableDeploymentModules(context = {}) {
  const tenantId = context.tenantId || context.tenant?.tenant?.id || context.tenant?.id || 'production_customer'
  const plan = context.plan || context.tenant?.tenant?.plan || context.tenant?.plan || 'enterprise'
  const modules = context.modules || ['dashboard', 'orders', 'profit-analysis', 'inventory', 'customers', 'system-health']
  const enabled = modules.map((moduleKey) => enableModule({ tenantId, plan }, moduleKey))

  return {
    mode: 'PRODUCTION_MODULE_ENABLEMENT',
    tenantId,
    requestedModules: modules,
    enabled,
    activeModules: getEnabledModules({ tenantId, plan }),
  }
}

export function activateBilling(context = {}) {
  const tenantId = context.tenantId || context.tenant?.tenant?.id || context.tenant?.id || 'production_customer'
  const plan = context.plan || context.tenant?.tenant?.plan || context.tenant?.plan || 'enterprise'
  const enabledModules = context.enabledModules || getEnabledModules({ tenantId, plan })

  return {
    mode: 'PRODUCTION_BILLING_ACTIVATION',
    status: 'ACTIVE',
    billing: calculateSaasBill({
      tenantId,
      plan,
      enabledModules,
    }),
  }
}

export function deploySaasProduct(context = {}) {
  const packaging = packageProductionBuild(context)
  const architecture = freezeArchitecture({
    ...context,
    schemas: packaging.registry.modules.map((module) => ({
      name: module.moduleName,
      api: {
        module: module.moduleName,
      },
    })),
  })
  const tenant = provisionTenantForDeployment(context)
  const moduleEnablement = enableDeploymentModules({
    ...context,
    tenant,
  })
  const billing = activateBilling({
    ...context,
    tenant,
    enabledModules: moduleEnablement.activeModules,
  })

  recordProductionEvent({
    type: 'SAAS_DEPLOYMENT',
    tenantId: tenant.tenantId,
    packageName: packaging.packageName,
    status: 'SUCCESS',
  })

  return {
    mode: 'PRODUCTION_SAAS_DEPLOYMENT_ENGINE',
    status: 'DEPLOYABLE',
    packaging,
    architecture,
    tenant,
    moduleEnablement,
    billing,
    health: getProductionHealth(),
    metrics: {
      deploymentReadiness: architecture.metrics.deployability,
      moduleCount: packaging.moduleCount,
      enabledModules: moduleEnablement.activeModules.length,
      billingTotal: billing.billing.total,
    },
  }
}
