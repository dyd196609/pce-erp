import { stateManager } from '../runtime/stateManager.js'

const sessionKey = 'profitos_session'
const onboardingKey = 'profitos_onboarded'

const defaultSession = {
  tenantId: 'demo_company',
  tenantName: 'Demo Company',
  role: 'manager',
  plan: 'pro',
  demoMode: true,
}

export function getDemoOrder() {
  return {
    id: 'A001',
    revenue: 1000,
    materialCost: 400,
    laborCost: 200,
    overhead: 100,
  }
}

export function getDemoCustomers() {
  return [
    { name: 'Company A', profit: 300, width: '100%' },
    { name: 'Company B', profit: 220, width: '73%' },
    { name: 'Company C', profit: 160, width: '53%' },
    { name: 'Company D', profit: 90, width: '30%' },
  ]
}

export function getCommercialPlans() {
  return [
    {
      key: 'basic',
      name: 'Basic',
      price: 99,
      description: 'For teams validating ProfitOS with one tenant.',
      features: ['Profit cockpit', 'Demo data', 'Basic billing'],
    },
    {
      key: 'pro',
      name: 'Pro',
      price: 299,
      description: 'For operating teams running multi-module profit analysis.',
      features: ['Multi-tenant cockpit', 'Agent status', 'Trace panel'],
    },
    {
      key: 'enterprise',
      name: 'Enterprise',
      price: 999,
      description: 'For production rollout with governance and deployment controls.',
      features: ['RBAC', 'Observability', 'Deployment architecture'],
    },
  ]
}

export function createProfitSession(input = {}) {
  const session = {
    ...defaultSession,
    ...input,
  }

  stateManager.setTenant({
    id: session.tenantId,
    name: session.tenantName,
    dataScope: session.demoMode ? 'demo' : session.tenantId,
  })
  stateManager.setRole(session.role)
  stateManager.setPlan(session.plan)
  stateManager.setSession({
    demoMode: session.demoMode,
    authenticated: true,
  })

  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(sessionKey, JSON.stringify(session))
  }

  return session
}

export function getProfitSession() {
  const state = stateManager.snapshot()

  if (typeof localStorage === 'undefined') {
    return {
      ...defaultSession,
      tenantId: state.tenant.id,
      tenantName: state.tenant.name,
      role: state.role,
      plan: state.plan,
      demoMode: state.session.demoMode,
    }
  }

  try {
    const saved = localStorage.getItem(sessionKey)
    return saved
      ? { ...defaultSession, ...JSON.parse(saved) }
      : {
          ...defaultSession,
          tenantId: state.tenant.id,
          tenantName: state.tenant.name,
          role: state.role,
          plan: state.plan,
          demoMode: state.session.demoMode,
        }
  } catch {
    return {
      ...defaultSession,
      tenantId: state.tenant.id,
      tenantName: state.tenant.name,
      role: state.role,
      plan: state.plan,
      demoMode: state.session.demoMode,
    }
  }
}

export function enableDemoMode(role = 'manager') {
  return createProfitSession({
    ...defaultSession,
    role,
    demoMode: true,
  })
}

export function hasCompletedOnboarding() {
  if (stateManager.getSession().onboardingCompleted) return true
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(onboardingKey) === 'true'
}

export function completeOnboarding() {
  stateManager.completeOnboarding()

  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(onboardingKey, 'true')
  }
}
