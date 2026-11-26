import { getAllGlobalModules } from '../registry/globalModuleRegistry.js'

const sharedRegistry = new Map()

function moduleKey(module = {}) {
  return module.key || module.schema?.api?.module || module.name || 'module'
}

export function registerSharedModule(module = {}, productId = 'platform') {
  const key = moduleKey(module)
  const existing = sharedRegistry.get(key) || {
    key,
    name: module.name || module.label || key,
    version: module.version || '1.0.0',
    products: new Set(),
    module,
    registeredAt: Date.now(),
  }

  existing.products.add(productId)
  existing.version = module.version || existing.version
  existing.module = {
    ...existing.module,
    ...module,
  }
  sharedRegistry.set(key, existing)

  return {
    ...existing,
    products: [...existing.products],
  }
}

export function buildSharedRegistry(products = []) {
  const baseModules = getAllGlobalModules()

  products.forEach((product) => {
    const productModules = product.modules || baseModules
    productModules.forEach((module) => registerSharedModule(module, product.id || product.key || product.name))
  })

  return {
    sharedModuleRegistry: 'ACTIVE',
    modules: [...sharedRegistry.values()].map((entry) => ({
      ...entry,
      products: [...entry.products],
      reuseCount: entry.products.size,
    })),
    versionControl: 'ENABLED',
  }
}

export function getSharedModuleRegistrySnapshot() {
  return buildSharedRegistry([])
}
