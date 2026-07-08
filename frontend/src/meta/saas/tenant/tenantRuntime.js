import { createTenant, ensureTenant, getTenant, listTenants } from '../../tenant/tenantManager.js'
import { enableModule, getEnabledModules } from '../market/moduleMarketplace.js'
import { isolateTenant } from './tenantIsolationEngine.js'

function normalizeTenantInput(input = {}) {
  const tenantId = input.tenantId || input.id || 'commercial_demo'
  const plan = input.plan || input.tenant?.plan || 'enterprise'

  return {
    tenantId,
    plan,
    companyName: input.companyName || input.name || input.tenant?.name || tenantId,
    modules: input.modules || ['dashboard', 'orders', 'profit-analysis', 'inventory', 'customers', 'system-health'],
  }
}

export function createCommercialTenant(input = {}) {
  const normalized = normalizeTenantInput(input)
  const tenant = createTenant(normalized.tenantId, {
    plan: normalized.plan,
    companyName: normalized.companyName,
    commercialMode: true,
  })

  return {
    success: true,
    tenant,
  }
}

export function assignPlan(tenantId = 'commercial_demo', plan = 'enterprise') {
  const existing = ensureTenant(tenantId, {
    plan,
  })
  existing.plan = plan
  existing.config = {
    ...(existing.config || {}),
    plan,
  }

  return {
    success: true,
    tenant: existing,
    plan,
  }
}

export function enableTenantModules(context = {}) {
  const normalized = normalizeTenantInput(context)
  const enabled = normalized.modules.map((moduleKey) => enableModule({
    tenantId: normalized.tenantId,
    plan: normalized.plan,
  }, moduleKey))

  return {
    success: true,
    tenantId: normalized.tenantId,
    requestedModules: normalized.modules,
    enabled,
    activeModules: getEnabledModules({
      tenantId: normalized.tenantId,
      plan: normalized.plan,
    }),
  }
}

export function getTenantIsolation(context = {}) {
  const normalized = normalizeTenantInput(context)

  return isolateTenant({
    tenantId: normalized.tenantId,
    tenant: getTenant(normalized.tenantId),
    plan: normalized.plan,
  })
}

export function initTenantSystem(context = {}) {
  const normalized = normalizeTenantInput(context)
  const tenant = getTenant(normalized.tenantId)
    ? {
        success: true,
        tenant: getTenant(normalized.tenantId),
      }
    : createCommercialTenant(normalized)
  const plan = assignPlan(normalized.tenantId, normalized.plan)
  const modules = enableTenantModules(normalized)
  const isolation = getTenantIsolation(normalized)

  return {
    mode: 'COMMERCIAL_TENANT_RUNTIME',
    status: 'ACTIVE',
    tenant: tenant.tenant,
    plan,
    modules,
    isolation,
    tenants: listTenants(),
  }
}
