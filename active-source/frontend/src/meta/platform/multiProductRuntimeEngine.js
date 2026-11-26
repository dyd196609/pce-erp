import { getAllGlobalModules } from '../registry/globalModuleRegistry.js'
import { buildSharedRegistry } from './sharedModuleRegistry.js'
import { createCrossProductBridge } from './crossProductDataBridge.js'
import { unifyBilling } from './unifiedBillingEngine.js'
import { getMarketplaceSnapshot, installProduct, publishSaasApp } from './marketplaceEngine.js'

const defaultProducts = [
  { id: 'enterprise-os', name: 'Enterprise OS', plan: 'enterprise', modules: ['process-center', 'organization', 'work-center'] },
  { id: 'process-cloud', name: 'Process Cloud', plan: 'enterprise', modules: ['purchase', 'warehouse', 'finance'] },
  { id: 'analytics-cloud', name: 'Analytics Cloud', plan: 'pro', modules: ['analytics'] },
]

function normalizeProduct(product = {}) {
  const globalModules = getAllGlobalModules()
  const moduleKeys = product.modules || []
  const matchesModule = (module, requestedKey) => {
    const normalized = String(requestedKey || '').toLowerCase()
    const candidates = [
      module.key,
      module.name,
      module.schema?.api?.module,
      module.schema?.meta?.title,
    ].map((item) => String(item || '').toLowerCase())

    if (normalized === 'purchase') {
      candidates.push('purchase')
      return candidates.some((item) => item.includes('purchase') || item.includes('order') || item.includes('采购'))
    }

    return candidates.some((item) => item === normalized || item.includes(normalized))
  }
  const modules = moduleKeys.length && typeof moduleKeys[0] === 'string'
    ? globalModules.filter((module) => moduleKeys.some((key) => matchesModule(module, key)))
    : moduleKeys.length
      ? moduleKeys
      : globalModules

  return {
    id: product.id || product.key || product.name,
    name: product.name || product.id || 'SaaS Product',
    plan: product.plan || 'enterprise',
    tenantId: product.tenantId || `${product.id || product.key || product.name}_tenant`,
    modules,
    enabledModules: modules.map((module) => module.key || module.schema?.api?.module || module.name),
  }
}

export function runPlatform(products = defaultProducts) {
  const activeProducts = products.map(normalizeProduct)
  activeProducts.forEach((product) => {
    publishSaasApp(product)
    installProduct(product.id, product.tenantId)
  })

  const sharedModules = buildSharedRegistry(activeProducts)
  const dataBridge = createCrossProductBridge(activeProducts)
  const billing = unifyBilling(activeProducts)
  const marketplace = getMarketplaceSnapshot()

  return {
    platformMode: 'ACTIVE',
    multiProductRuntime: 'ON',
    crossProductDataFlow: 'ENABLED',
    marketplace: 'ACTIVE',
    activeProducts,
    sharedModules,
    dataBridge,
    billing,
    marketplaceSnapshot: marketplace,
    metrics: {
      platformRevenue: billing.total,
      productDistribution: activeProducts.length,
      crossProductUsage: dataBridge.flows.length,
      marketplaceAdoptionIndex: marketplace.adoptionIndex,
    },
  }
}

export function getPlatformRuntimeSnapshot() {
  return runPlatform(defaultProducts)
}
