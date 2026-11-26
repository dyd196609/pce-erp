const tenants = {}

export function createTenant(id, config = {}) {
  tenants[id] = {
    id,
    config,
    plan: config.plan || 'basic',
    createdAt: Date.now(),
  }

  return tenants[id]
}

export function getTenant(id) {
  return tenants[id]
}

export function ensureTenant(id, config = {}) {
  return getTenant(id) || createTenant(id, config)
}

export function listTenants() {
  return Object.keys(tenants)
}
