import { isModuleRestrictedByReview } from '../review/reviewControlEngine.js'
import { getModule, listModules } from '../registry/moduleRegistry.js'

const planModuleAccess = {
  basic: ['dashboard', 'work-center', 'analytics'],
  pro: ['dashboard', 'organization', 'process-center', 'work-center', 'analytics', 'admin'],
  enterprise: ['dashboard', 'organization', 'process-center', 'work-center', 'analytics', 'admin'],
}

const roleActionAccess = {
  admin: ['READ', 'ANALYZE', 'EXECUTE', 'MANAGE', 'BILLING'],
  manager: ['READ', 'ANALYZE', 'EXECUTE'],
  viewer: ['READ', 'ANALYZE'],
}

function normalizePlan(plan) {
  const value = String(plan || 'basic').toLowerCase()
  if (value.includes('enterprise')) return 'enterprise'
  if (value.includes('pro')) return 'pro'
  return planModuleAccess[value] ? value : 'basic'
}

export function canAccessModule(plan, moduleKey) {
  const normalizedPlan = normalizePlan(plan)
  return hasPlanAccess(normalizedPlan, moduleKey) && !isModuleRestrictedByReview(moduleKey)
}

export function hasPlanAccess(plan, moduleKey) {
  const normalizedPlan = normalizePlan(plan)
  const module = getModule(moduleKey)
  const planAllowsGenerated = module?.generated && (normalizedPlan === 'pro' || normalizedPlan === 'enterprise')
  const planAllowedByBinding = module?.permission?.plans?.includes(normalizedPlan)
  const registeredPlatformModule = module && ['pro', 'enterprise'].includes(normalizedPlan)
  return (planModuleAccess[normalizedPlan] || planModuleAccess.basic).includes(moduleKey) || planAllowsGenerated || planAllowedByBinding || registeredPlatformModule
}

export function canPerformAction(role, action) {
  return (roleActionAccess[role] || roleActionAccess.viewer).includes(action)
}

export function canFetchData() {
  return true
}

export function getDataScope(tenant = {}) {
  return tenant.dataScope || tenant.id || 'demo'
}

export function getAccessibleNavigation(navigation, state) {
  return navigation.filter((item) => canAccessModule(state.plan, item.key))
}

export function getPermissionSnapshot(state) {
  const normalizedPlan = normalizePlan(state.plan)
  const planModules = [
    ...(planModuleAccess[normalizedPlan] || planModuleAccess.basic),
    ...(normalizedPlan === 'pro' || normalizedPlan === 'enterprise'
      ? listModules().filter((module) => module.generated).map((module) => module.key)
      : []),
  ]

  return {
    plan: state.plan,
    role: state.role,
    dataScope: getDataScope(state.tenant),
    modules: planModules.filter((moduleKey) => !isModuleRestrictedByReview(moduleKey)),
    reviewRestrictedModules: planModules.filter((moduleKey) => isModuleRestrictedByReview(moduleKey)),
    actions: roleActionAccess[state.role] || roleActionAccess.viewer,
  }
}
