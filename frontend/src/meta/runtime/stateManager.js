const storageKey = 'profitos_runtime_state'
const listeners = new Set()

const defaultState = {
  tenant: {
    id: 'demo_company',
    name: 'Demo Company',
    dataScope: 'demo',
  },
  role: 'manager',
  plan: 'pro',
  session: {
    demoMode: true,
    authenticated: false,
    onboardingStep: 0,
    onboardingCompleted: false,
    updatedAt: Date.now(),
  },
}

let state = clone(defaultState)

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function canUseStorage() {
  return typeof localStorage !== 'undefined'
}

function persist() {
  state.session.updatedAt = Date.now()

  if (canUseStorage()) {
    localStorage.setItem(storageKey, JSON.stringify(state))
  }

  listeners.forEach((listener) => listener(getState()))
}

export function getState() {
  return clone(state)
}

export const stateManager = {
  setTenant(tenant) {
    state.tenant = {
      ...state.tenant,
      ...(typeof tenant === 'string' ? { id: tenant, name: tenant } : tenant),
    }
    persist()
  },

  getTenant() {
    return clone(state.tenant)
  },

  setRole(role) {
    state.role = role || defaultState.role
    persist()
  },

  getRole() {
    return state.role
  },

  setPlan(plan) {
    state.plan = plan || defaultState.plan
    persist()
  },

  getPlan() {
    return state.plan
  },

  setSession(sessionPatch = {}) {
    state.session = {
      ...state.session,
      ...sessionPatch,
    }
    persist()
  },

  getSession() {
    return clone(state.session)
  },

  setOnboardingStep(step) {
    state.session.onboardingStep = step
    persist()
  },

  completeOnboarding() {
    state.session.onboardingCompleted = true
    state.session.onboardingStep = 3
    persist()
  },

  initFromStorage() {
    if (!canUseStorage()) return getState()

    try {
      const saved = localStorage.getItem(storageKey)
      state = saved
        ? {
            ...clone(defaultState),
            ...JSON.parse(saved),
          }
        : clone(defaultState)
    } catch {
      state = clone(defaultState)
    }

    return getState()
  },

  clear() {
    state = clone(defaultState)

    if (canUseStorage()) {
      localStorage.removeItem(storageKey)
    }

    listeners.forEach((listener) => listener(getState()))
  },

  subscribe(listener) {
    listeners.add(listener)
    listener(getState())

    return () => listeners.delete(listener)
  },

  snapshot: getState,
}

stateManager.initFromStorage()
