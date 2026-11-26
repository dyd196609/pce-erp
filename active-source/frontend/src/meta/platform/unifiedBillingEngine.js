import { calculateSaasBill } from '../saas/billing/billingEngine.js'

const platformBillingHistory = []

export function aggregateProductUsage(products = []) {
  return products.map((product) => {
    const tenantId = product.tenantId || product.tenant?.id || `${product.id || product.key || product.name}_tenant`
    const plan = product.plan || product.tenant?.plan || 'enterprise'
    const enabledModules = product.enabledModules || product.modules?.map((module) => module.key || module.name) || []
    return calculateSaasBill({
      tenantId,
      plan,
      enabledModules,
    })
  })
}

export function unifyBilling(products = []) {
  const productBills = aggregateProductUsage(products)
  const total = Number(productBills.reduce((sum, bill) => sum + Number(bill.total || 0), 0).toFixed(2))
  const result = {
    platformBilling: 'ENABLED',
    crossProductSubscription: 'ACTIVE',
    usageAggregation: 'ACTIVE',
    productBills,
    total,
    timestamp: Date.now(),
  }

  platformBillingHistory.unshift(result)
  if (platformBillingHistory.length > 80) platformBillingHistory.length = 80

  return result
}

export function getUnifiedBillingSnapshot() {
  return platformBillingHistory[0] || unifyBilling([])
}
