const tenantModules = {}

const marketplaceModules = [
  { key: 'dashboard', name: 'Dashboard', price: 0, plans: ['free', 'basic', 'pro', 'enterprise'] },
  { key: 'organization', name: 'Organization', price: 0, plans: ['pro', 'enterprise'] },
  { key: 'process-center', name: 'Process Center', price: 0, plans: ['basic', 'pro', 'enterprise'] },
  { key: 'work-center', name: 'Work Center', price: 0, plans: ['free', 'basic', 'pro', 'enterprise'] },
  { key: 'analytics', name: 'Analytics', price: 79, plans: ['basic', 'pro', 'enterprise'] },
  { key: 'admin', name: 'Admin', price: 39, plans: ['pro', 'enterprise'] },
  { key: 'ai-decision', name: 'AI Decision', price: 149, plans: ['enterprise'] },
  { key: 'digital-twin', name: 'Digital Twin', price: 199, plans: ['enterprise'] },
]

function tenantKey(context = {}) {
  return context.tenantId || context.runtimeState?.tenant?.id || context.tenant?.id || 'demo_company'
}

function planKey(context = {}) {
  return context.plan || context.runtimeState?.plan || context.tenant?.plan || 'free'
}

function defaultModulesForPlan(plan) {
  return marketplaceModules
    .filter((module) => module.plans.includes(plan) && module.price === 0)
    .map((module) => module.key)
}

export function listAvailableModules(context = {}) {
  const plan = planKey(context)
  return marketplaceModules.map((module) => ({
    ...module,
    available: module.plans.includes(plan),
    enabled: isModuleEnabled(context, module.key),
  }))
}

export function enableModule(context = {}, moduleKey) {
  const tenantId = tenantKey(context)
  const plan = planKey(context)
  const module = marketplaceModules.find((item) => item.key === moduleKey)

  if (!module || !module.plans.includes(plan)) {
    return {
      success: false,
      module: moduleKey,
      error: 'MODULE_NOT_AVAILABLE_FOR_PLAN',
    }
  }

  if (!tenantModules[tenantId]) {
    tenantModules[tenantId] = new Set(defaultModulesForPlan(plan))
  }

  tenantModules[tenantId].add(moduleKey)

  return {
    success: true,
    module: moduleKey,
    enabled: true,
  }
}

export function disableModule(context = {}, moduleKey) {
  const tenantId = tenantKey(context)
  if (!tenantModules[tenantId]) tenantModules[tenantId] = new Set(defaultModulesForPlan(planKey(context)))
  tenantModules[tenantId].delete(moduleKey)

  return {
    success: true,
    module: moduleKey,
    enabled: false,
  }
}

export function getEnabledModules(context = {}) {
  const tenantId = tenantKey(context)
  const plan = planKey(context)

  if (!tenantModules[tenantId]) {
    tenantModules[tenantId] = new Set(defaultModulesForPlan(plan))
  }

  return Array.from(tenantModules[tenantId])
}

export function isModuleEnabled(context = {}, moduleKey) {
  return getEnabledModules(context).includes(moduleKey)
}

export function getModulePricing(moduleKey) {
  return marketplaceModules.find((module) => module.key === moduleKey)?.price || 0
}

export function calculateModuleAdoption(context = {}) {
  const available = listAvailableModules(context).filter((module) => module.available)
  const enabled = available.filter((module) => module.enabled)

  return {
    available: available.length,
    enabled: enabled.length,
    rate: available.length === 0 ? 1 : enabled.length / available.length,
  }
}
