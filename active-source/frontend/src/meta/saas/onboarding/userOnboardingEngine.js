import { createTenant } from '../../tenant/tenantManager.js'
import { enableModule, getEnabledModules } from '../market/moduleMarketplace.js'
import { recordProductionEvent } from '../monitoring/productionMonitor.js'
import { trackAcquisition } from '../../growth/acquisitionEngine.js'
import { recordActivation, activationSteps } from '../../growth/activationEngine.js'

function slugify(value = '') {
  return String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function resolveTenantId(user = {}) {
  return user.tenantId || slugify(user.companyName || user.company || user.email || 'new_tenant') || 'new_tenant'
}

function createTenantFromUser(user = {}) {
  const tenantId = resolveTenantId(user)
  const plan = user.plan || 'basic'

  return createTenant(tenantId, {
    plan,
    companyName: user.companyName || user.company || tenantId,
    ownerEmail: user.email || '',
    source: 'USER_ONBOARDING',
  })
}

export function initWorkspace(tenant) {
  return {
    tenantId: tenant.id,
    workspaceId: `${tenant.id}_workspace`,
    schemaNamespace: `schema_${tenant.id}`,
    workflowNamespace: `workflow_${tenant.id}`,
    dashboard: {
      route: '/dashboard',
      initialized: true,
      defaultView: 'ProfitOS Cockpit',
    },
    initializedAt: Date.now(),
  }
}

export function provisionDefaultModules(tenant) {
  const context = {
    tenantId: tenant.id,
    tenant,
    plan: tenant.plan,
  }
  const defaultModules = ['dashboard', 'orders', 'profit-analysis']

  defaultModules.forEach((moduleKey) => {
    enableModule(context, moduleKey)
  })

  return {
    tenantId: tenant.id,
    enabledModules: getEnabledModules(context),
    schemaInitialized: true,
    workflowInitialized: true,
    dashboardInitialized: true,
  }
}

export function onboardTenant(user = {}) {
  const tenant = createTenantFromUser(user)
  const workspace = initWorkspace(tenant)
  const modules = provisionDefaultModules(tenant)

  const result = {
    mode: 'V16_USER_ONBOARDING',
    tenant,
    workspace,
    modules,
    status: 'TENANT_READY',
  }

  recordProductionEvent({
    type: 'TENANT_ONBOARDED',
    tenantId: tenant.id,
    plan: tenant.plan,
    modules: modules.enabledModules,
    status: 'SUCCESS',
  })
  trackAcquisition({
    source: user.source || 'direct',
    campaign: user.campaign || 'signup',
    tenantId: tenant.id,
    converted: true,
  })
  recordActivation({
    tenantId: tenant.id,
    step: activationSteps.FIRST_LOGIN,
    module: 'dashboard',
  })

  return result
}
