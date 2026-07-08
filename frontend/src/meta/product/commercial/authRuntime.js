import { listRoles } from '../../auth/rbacEngine.js'
import { stateManager } from '../../runtime/stateManager.js'

const storageKey = 'profitos_commercial_auth'
const memoryAuth = {
  users: [],
  session: null,
}

function canUseStorage() {
  return typeof localStorage !== 'undefined'
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function loadAuthState() {
  if (!canUseStorage()) return memoryAuth

  try {
    const saved = localStorage.getItem(storageKey)
    if (!saved) return memoryAuth

    const parsed = JSON.parse(saved)
    memoryAuth.users = Array.isArray(parsed.users) ? parsed.users : []
    memoryAuth.session = parsed.session || null
  } catch {
    memoryAuth.users = []
    memoryAuth.session = null
  }

  return memoryAuth
}

function persistAuthState() {
  if (canUseStorage()) {
    localStorage.setItem(storageKey, JSON.stringify(memoryAuth))
  }
}

function normalizeUser(input = {}) {
  const email = String(input.email || 'owner@profitos.local').trim().toLowerCase()
  const tenantId = input.tenantId || input.tenant?.id || 'commercial_demo'
  const role = listRoles().includes(input.role) ? input.role : 'admin'
  const plan = input.plan || 'enterprise'

  return {
    id: input.id || `user_${email.replace(/[^a-z0-9]+/g, '_')}`,
    email,
    name: input.name || input.companyName || 'Commercial Owner',
    tenantId,
    role,
    plan,
    password: input.password || 'profitos-demo',
    createdAt: input.createdAt || Date.now(),
  }
}

function syncRuntimeSession(user, session) {
  stateManager.setTenant({
    id: user.tenantId,
    name: session.tenantName || user.tenantId,
    dataScope: user.tenantId,
  })
  stateManager.setRole(user.role)
  stateManager.setPlan(user.plan)
  stateManager.setSession({
    authenticated: true,
    demoMode: false,
    commercialMode: true,
    userId: user.id,
    email: user.email,
    sessionId: session.sessionId,
  })
}

export function registerUser(input = {}) {
  loadAuthState()
  const user = normalizeUser(input)
  const existingIndex = memoryAuth.users.findIndex((item) => item.email === user.email)

  if (existingIndex >= 0) {
    memoryAuth.users.splice(existingIndex, 1, {
      ...memoryAuth.users[existingIndex],
      ...user,
      createdAt: memoryAuth.users[existingIndex].createdAt,
    })
  } else {
    memoryAuth.users.push(user)
  }

  persistAuthState()

  return {
    success: true,
    user: {
      id: user.id,
      email: user.email,
      name: user.name,
      tenantId: user.tenantId,
      role: user.role,
      plan: user.plan,
    },
  }
}

export function loginUser(credentials = {}) {
  loadAuthState()
  const email = String(credentials.email || 'owner@profitos.local').trim().toLowerCase()
  let user = memoryAuth.users.find((item) => item.email === email)

  if (!user) {
    user = registerUser({
      ...credentials,
      email,
    }).user
    user = memoryAuth.users.find((item) => item.email === email)
  }

  if (credentials.password && user.password && credentials.password !== user.password) {
    return {
      success: false,
      session: null,
      error: 'INVALID_CREDENTIALS',
    }
  }

  const session = {
    sessionId: `session_${user.id}_${Date.now()}`,
    userId: user.id,
    email: user.email,
    tenantId: user.tenantId,
    tenantName: credentials.tenantName || credentials.companyName || user.tenantId,
    role: user.role,
    plan: user.plan,
    authenticated: true,
    commercialMode: true,
    createdAt: Date.now(),
  }

  memoryAuth.session = session
  persistAuthState()
  syncRuntimeSession(user, session)

  return {
    success: true,
    session: clone(session),
    user: {
      id: user.id,
      email: user.email,
      name: user.name,
      tenantId: user.tenantId,
      role: user.role,
      plan: user.plan,
    },
  }
}

export function getSession() {
  loadAuthState()
  return memoryAuth.session ? clone(memoryAuth.session) : null
}

export function logout() {
  loadAuthState()
  memoryAuth.session = null
  persistAuthState()
  stateManager.setSession({
    authenticated: false,
    commercialMode: false,
    sessionId: null,
  })

  return {
    success: true,
    session: null,
  }
}

export function assignRole(userId, role = 'viewer') {
  loadAuthState()
  const nextRole = listRoles().includes(role) ? role : 'viewer'
  const user = memoryAuth.users.find((item) => item.id === userId || item.email === userId)

  if (!user) {
    return {
      success: false,
      error: 'USER_NOT_FOUND',
    }
  }

  user.role = nextRole
  if (memoryAuth.session?.userId === user.id) {
    memoryAuth.session.role = nextRole
    stateManager.setRole(nextRole)
  }
  persistAuthState()

  return {
    success: true,
    user: {
      id: user.id,
      email: user.email,
      role: user.role,
    },
  }
}

export function listCommercialUsers() {
  loadAuthState()
  return memoryAuth.users.map((user) => ({
    id: user.id,
    email: user.email,
    name: user.name,
    tenantId: user.tenantId,
    role: user.role,
    plan: user.plan,
  }))
}

export function initAuthSystem(context = {}) {
  const registered = registerUser({
    email: context.email || 'owner@profitos.local',
    name: context.name || 'Commercial Owner',
    tenantId: context.tenantId || 'commercial_demo',
    tenantName: context.companyName || 'Commercial Demo',
    role: context.role || 'admin',
    plan: context.plan || 'enterprise',
    password: context.password || 'profitos-demo',
  })
  const login = loginUser({
    email: registered.user.email,
    password: context.password || 'profitos-demo',
    tenantName: context.companyName || 'Commercial Demo',
  })

  return {
    mode: 'COMMERCIAL_AUTH_RUNTIME',
    status: login.success ? 'ACTIVE' : 'AUTH_ERROR',
    roles: listRoles(),
    registeredUsers: listCommercialUsers(),
    session: login.session,
    register: registered,
    login,
  }
}
