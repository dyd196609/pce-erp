import { runBusinessCore } from '../business-core/index.js'
import { optimizeRevenue } from '../business/autonomousRevenueEngine.js'
import { runMarketControl } from '../business/marketControlEngine.js'

export function maximizeEnterpriseRevenue(context = {}) {
  const revenue = optimizeRevenue(context)
  const projectedPrice = revenue.revenueModel.prices[revenue.usage.plan] || 0
  const upgradeLift = revenue.upgradePaths.length * 120

  return {
    projectedRevenue: projectedPrice + upgradeLift,
    upgradeLift,
    strategy: upgradeLift > 0 ? 'UPGRADE_CAPTURE' : 'USAGE_EXPANSION',
  }
}

export function optimizeSubscriptionMix(context = {}) {
  const revenue = optimizeRevenue(context)

  return {
    currentPlan: revenue.usage.plan,
    recommendedPlan: revenue.upgradePaths[0]?.to || revenue.usage.plan,
    mixAction: revenue.upgradePaths.length ? 'SHIFT_UPMARKET' : 'KEEP_MIX',
  }
}

export function optimizeModuleAdoption(context = {}) {
  const market = runMarketControl(context)

  return {
    hotModules: market.popularity.filter((item) => item.heat === 'HOT').map((item) => item.moduleKey),
    coldModules: market.popularity.filter((item) => item.heat === 'COLD').map((item) => item.moduleKey),
    action: market.popularity.some((item) => item.heat === 'COLD') ? 'RUN_DISCOVERY_CAMPAIGN' : 'EXPAND_HOT_MODULES',
  }
}

export function optimizeProfit(context = {}) {
  const business = runBusinessCore(context.data || {})
  const enterpriseRevenue = maximizeEnterpriseRevenue(context)
  const subscriptionMix = optimizeSubscriptionMix(context)
  const moduleAdoption = optimizeModuleAdoption(context)
  const profitBase = business?.decision?.profit?.profit || 0

  return {
    mode: 'V24_PROFIT_OPTIMIZATION',
    enterpriseRevenue,
    subscriptionMix,
    moduleAdoption,
    profitBase,
    score: Math.min(100, Math.max(0, Math.round(60 + enterpriseRevenue.upgradeLift / 10 + moduleAdoption.hotModules.length * 5))),
  }
}
