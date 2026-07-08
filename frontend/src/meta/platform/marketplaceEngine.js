const productCatalog = new Map()
const installedProducts = new Map()

export function publishSaasApp(product = {}) {
  const id = product.id || product.key || product.name || `product_${Date.now()}`
  const entry = {
    id,
    name: product.name || id,
    version: product.version || '1.0.0',
    modules: product.modules || [],
    status: 'PUBLISHED',
    publishedAt: Date.now(),
  }

  productCatalog.set(id, entry)
  return entry
}

export function installProduct(productId, tenantId = 'platform_tenant') {
  const product = productCatalog.get(productId) || publishSaasApp({ id: productId })
  const key = `${tenantId}:${productId}`
  const install = {
    tenantId,
    productId,
    version: product.version,
    status: 'INSTALLED',
    installedAt: Date.now(),
  }

  installedProducts.set(key, install)
  return install
}

export function removeProduct(productId, tenantId = 'platform_tenant') {
  const key = `${tenantId}:${productId}`
  installedProducts.delete(key)
  return {
    tenantId,
    productId,
    status: 'REMOVED',
    removedAt: Date.now(),
  }
}

export function getMarketplaceSnapshot() {
  const catalog = [...productCatalog.values()]
  const installed = [...installedProducts.values()]

  return {
    marketplace: 'ACTIVE',
    catalog,
    installed,
    adoptionIndex: catalog.length ? Math.round((installed.length / catalog.length) * 100) : 0,
  }
}
