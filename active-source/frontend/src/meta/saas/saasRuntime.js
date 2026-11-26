import { isolateTenant } from './tenant/tenantIsolationEngine.js'
import { calculateSaasBill } from './billing/billingEngine.js'
import { getQuotaStatus } from './quota/quotaManager.js'
import {
  calculateModuleAdoption,
  getEnabledModules,
  listAvailableModules,
} from './market/moduleMarketplace.js'
import { getProductionHealth } from './monitoring/productionMonitor.js'
import { getOpsState } from './ops/opsControlCenter.js'

const planFeatureRules = {
  free: {
    aiFeatures: false,
    simulation: false,
    digitalTwin: false,
  },
  basic: {
    aiFeatures: false,
    simulation: false,
    digitalTwin: false,
  },
  pro: {
    aiFeatures: false,
    simulation: true,
    digitalTwin: false,
  },
  enterprise: {
    aiFeatures: true,
    simulation: true,
    digitalTwin: true,
  },
}

function resolvePlan(context = {}) {
  return context.plan || context.runtimeState?.plan || context.tenant?.plan || 'free'
}

export function getFeatureAccess(context = {}) {
  const plan = resolvePlan(context)
  return {
    plan,
    ...(planFeatureRules[plan] || planFeatureRules.free),
  }
}

export function runSaasRuntime(context = {}) {
  const plan = resolvePlan(context)
  const isolation = isolateTenant(context)
  const enabledModules = getEnabledModules({
    ...context,
    plan,
  })
  const billing = calculateSaasBill({
    ...context,
    plan,
    enabledModules,
  })
  const quota = getQuotaStatus({
    ...context,
    plan,
  })
  const marketplace = {
    availableModules: listAvailableModules({
      ...context,
      plan,
    }),
    enabledModules,
    adoption: calculateModuleAdoption({
      ...context,
      plan,
    }),
  }
  const featureAccess = getFeatureAccess({
    ...context,
    plan,
  })
  const monitoring = getProductionHealth()
  const ops = getOpsState()

  return {
    mode: 'V16_SAAS_PRODUCTION_LAUNCH',
    saasMode: 'ON',
    productionMode: 'LIVE',
    onboardingEnabled: 'ACTIVE',
    opsControl: 'ENABLED',
    tenantIsolation: 'ACTIVE',
    billingEngine: 'ENABLED',
    quotaManager: 'ACTIVE',
    plan,
    isolation,
    billing,
    quota,
    marketplace,
    featureAccess,
    monitoring,
    ops,
  }
}
