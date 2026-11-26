import { registerPlatformModule } from '../platform/moduleHub.js'
import { bindModule } from '../platform/selfBindingEngine.js'
import { distributeRevenue } from './revenueSharingEngine.js'

const marketplaceModules = new Map()
const tenantInstalls = new Map()

function normalizeModule(module = {}, meta = {}) {
  const key = module.key || module.schema?.api?.module || module.schema?.name || meta.key

  return bindModule({
    layer: 'executionLayer',
    generated: true,
    ...module,
    key,
    name: module.name || module.schema?.meta?.title || key,
    route: module.route || `/${key}`,
    developerId: meta.developerId || module.developerId || 'platform',
    marketplace: {
      status: 'PUBLISHED',
      version: meta.version || module.version || '1.0.0',
      price: Number(meta.price || module.price || 0),
      publishedAt: Date.now(),
    },
  })
}

function getTenantSet(tenantId) {
  if (!tenantInstalls.has(tenantId)) {
    tenantInstalls.set(tenantId, new Set())
  }

  return tenantInstalls.get(tenantId)
}

export function publishModule(module = {}, meta = {}) {
  const normalized = normalizeModule(module, meta)
  marketplaceModules.set(normalized.key, normalized)

  return {
    status: 'PUBLISHED',
    module: normalized,
    version: normalized.marketplace.version,
  }
}

export function installModule(moduleKey, tenantId = 'demo_company') {
  const module = marketplaceModules.get(moduleKey)

  if (!module) {
    return {
      status: 'NOT_FOUND',
      moduleKey,
      tenantId,
    }
  }

  const registered = registerPlatformModule(module)
  getTenantSet(tenantId).add(moduleKey)

  const revenue = module.marketplace.price > 0
    ? distributeRevenue({
        pluginId: module.pluginId || module.key,
        moduleKey: module.key,
        developerId: module.developerId,
        tenantId,
        amount: module.marketplace.price,
      })
    : null

  return {
    status: 'INSTALLED',
    tenantId,
    module: registered,
    revenue,
  }
}

export function uninstallModule(moduleKey, tenantId = 'demo_company') {
  getTenantSet(tenantId).delete(moduleKey)

  return {
    status: 'UNINSTALLED',
    tenantId,
    moduleKey,
  }
}

export function listMarketplaceModules() {
  return Array.from(marketplaceModules.values())
}

export function getInstalledModules(tenantId = 'demo_company') {
  const keys = Array.from(getTenantSet(tenantId).values())
  return keys.map((key) => marketplaceModules.get(key)).filter(Boolean)
}

export function getModuleVersions(moduleKey) {
  const module = marketplaceModules.get(moduleKey)

  return {
    moduleKey,
    current: module?.marketplace?.version || null,
    versions: module ? [module.marketplace.version] : [],
  }
}

export function clearMarketplace() {
  marketplaceModules.clear()
  tenantInstalls.clear()
}
