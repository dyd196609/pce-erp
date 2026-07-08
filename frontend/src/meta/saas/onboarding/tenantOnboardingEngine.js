import { onboardTenant as onboardUserTenant, initWorkspace as initUserWorkspace, provisionDefaultModules } from './userOnboardingEngine.js'

const onboardingHistory = []

export function createTenant(user = {}) {
  const result = onboardUserTenant({
    ...user,
    plan: user.plan || 'enterprise',
    source: user.source || 'commercial_launch',
  })

  return result.tenant
}

export function initWorkspace(tenant = {}) {
  return initUserWorkspace(tenant)
}

export function provisionModules(tenant = {}) {
  return provisionDefaultModules(tenant)
}

export function onboardTenant(user = {}) {
  const tenant = createTenant(user)
  const workspace = initWorkspace(tenant)
  const modules = provisionModules(tenant)
  const result = {
    tenantId: tenant.id,
    tenant,
    workspace,
    modules,
    status: 'ACTIVE',
    onboardedAt: Date.now(),
  }

  onboardingHistory.unshift(result)
  if (onboardingHistory.length > 100) onboardingHistory.length = 100

  return result
}

export function getTenantOnboardingSnapshot() {
  return {
    onboarding: 'ACTIVE',
    latest: onboardingHistory[0] || null,
    tenants: [...onboardingHistory],
    metrics: {
      activeTenants: onboardingHistory.length,
      tenantGrowth: onboardingHistory.length ? 100 : 0,
    },
  }
}
