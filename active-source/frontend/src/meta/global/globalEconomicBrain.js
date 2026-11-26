import { createDefaultEnterpriseNetwork } from '../network/enterpriseGraphEngine.js'
import { optimizeEnterpriseNetwork } from '../network/globalOptimizationEngine.js'

const defaultRegions = [
  { country: 'CN', currency: 'CNY', baseRate: 7.2, demandIndex: 1.12, productionCost: 0.92, logisticsCost: 0.08 },
  { country: 'US', currency: 'USD', baseRate: 1, demandIndex: 1.05, productionCost: 1.18, logisticsCost: 0.12 },
  { country: 'DE', currency: 'EUR', baseRate: 0.92, demandIndex: 0.98, productionCost: 1.14, logisticsCost: 0.1 },
  { country: 'VN', currency: 'VND', baseRate: 25400, demandIndex: 0.88, productionCost: 0.74, logisticsCost: 0.09 },
]

function normalizeRegion(region, index) {
  const fallback = defaultRegions[index % defaultRegions.length]

  return {
    ...fallback,
    ...(region || {}),
    demandIndex: Number(region?.demandIndex ?? fallback.demandIndex),
    productionCost: Number(region?.productionCost ?? fallback.productionCost),
    logisticsCost: Number(region?.logisticsCost ?? fallback.logisticsCost),
    baseRate: Number(region?.baseRate ?? fallback.baseRate),
  }
}

function attachGlobalContext(enterprises, regions) {
  return enterprises.map((enterprise, index) => {
    const region = normalizeRegion(enterprise.region || regions[index % regions.length], index)

    return {
      ...enterprise,
      country: enterprise.country || region.country,
      currency: enterprise.currency || region.currency,
      exchangeRate: Number(enterprise.exchangeRate || region.baseRate),
      regionalDemand: Math.round(Number(enterprise.demand || 0) * region.demandIndex),
      landedCost: Math.round(Number(enterprise.price || 0) * (region.productionCost + region.logisticsCost)),
      region,
    }
  })
}

export function simulateGlobalMarket(context = {}) {
  const regions = (context.regions?.length ? context.regions : defaultRegions).map(normalizeRegion)
  const enterprises = attachGlobalContext(
    context.enterprises || createDefaultEnterpriseNetwork(),
    regions
  )
  const network = context.network || optimizeEnterpriseNetwork(enterprises, context)
  const totalDemand = enterprises.reduce((sum, item) => sum + item.regionalDemand, 0)
  const totalSupply = enterprises.reduce((sum, item) => sum + Number(item.inventory || 0), 0)
  const demandSupplyBalance = totalDemand === 0 ? 1 : Math.min(1, totalSupply / totalDemand)
  const priceFluctuation = enterprises.map((enterprise) => {
    const shortagePressure = enterprise.regionalDemand > enterprise.inventory ? 0.08 : -0.03
    const currencyPressure = enterprise.exchangeRate > 1 ? 0.04 : 0

    return {
      enterprise: enterprise.id,
      country: enterprise.country,
      currency: enterprise.currency,
      basePrice: Number(enterprise.price || 0),
      projectedPrice: Math.round(Number(enterprise.price || 0) * (1 + shortagePressure + currencyPressure)),
      currencyImpact: Number((enterprise.exchangeRate / (enterprise.region?.baseRate || enterprise.exchangeRate || 1)).toFixed(4)),
    }
  })
  const currencyFlows = network.resourceExchange.transfers.map((transfer, index) => {
    const from = enterprises.find((item) => item.id === transfer.from) || enterprises[index] || enterprises[0]
    const to = enterprises.find((item) => item.id === transfer.to) || enterprises[index + 1] || enterprises[0]
    const fxImpact = Number(((to?.exchangeRate || 1) / (from?.exchangeRate || 1)).toFixed(4))

    return {
      from: transfer.from,
      to: transfer.to,
      fromCurrency: from?.currency,
      toCurrency: to?.currency,
      cashFlow: transfer.cashFlow,
      fxImpact,
      adjustedCost: Math.round(transfer.cashFlow * fxImpact),
    }
  })

  return {
    mode: 'GLOBAL_MARKET_SIMULATION',
    regions,
    enterprises,
    network,
    priceFluctuation,
    currencyFlows,
    demandSupplyBalance,
  }
}

export function simulateMacroEconomy(market = {}) {
  const averageDemand = market.enterprises?.length
    ? market.enterprises.reduce((sum, item) => sum + item.region.demandIndex, 0) / market.enterprises.length
    : 1
  const averageCost = market.enterprises?.length
    ? market.enterprises.reduce((sum, item) => sum + item.region.productionCost + item.region.logisticsCost, 0) / market.enterprises.length
    : 1
  const inflationPressure = Number(Math.max(0, averageCost - 0.9).toFixed(2))
  const gdpTrend = Number((2.4 + averageDemand * 1.8 - inflationPressure).toFixed(2))
  const interestRateImpact = inflationPressure > 0.25 ? 'TIGHTENING' : 'STABLE'

  return {
    mode: 'MACRO_ECONOMY_SIMULATION',
    gdpTrend,
    inflationPressure,
    interestRateImpact,
    industryCycles: (market.regions || []).map((region) => ({
      country: region.country,
      cycle: region.demandIndex > 1 ? 'EXPANSION' : 'NORMALIZATION',
    })),
  }
}

export function buildGlobalSupplyChain(market = {}) {
  const enterprises = market.enterprises || []
  const lowestCostRegion = [...enterprises].sort((a, b) => a.landedCost - b.landedCost)[0]
  const highestDemandRegion = [...enterprises].sort((a, b) => b.regionalDemand - a.regionalDemand)[0]

  return {
    mode: 'GLOBAL_SUPPLY_CHAIN',
    productionShifting: lowestCostRegion
      ? {
          targetCountry: lowestCostRegion.country,
          targetEnterprise: lowestCostRegion.id,
          reason: 'lowest landed cost',
        }
      : null,
    logisticsRerouting: (market.network?.graph?.edges || []).map((edge) => ({
      from: edge.from,
      to: edge.to,
      route: 'optimized cross-country lane',
      priority: highestDemandRegion?.id === edge.to ? 'HIGH' : 'NORMAL',
    })),
    costOptimization: {
      estimatedSavings: Math.round((market.network?.resourceExchange?.cashFlow || 0) * 0.06),
      currencyAware: true,
      demandBalanced: market.demandSupplyBalance > 0.8,
    },
  }
}

export function generateEconomicPolicies(macro = {}) {
  const highInflation = macro.inflationPressure > 0.25
  const tightening = macro.interestRateImpact === 'TIGHTENING'

  return {
    mode: 'AI_ECONOMIC_POLICY',
    pricingPolicies: [
      highInflation ? 'apply currency-indexed pricing' : 'maintain competitive pricing',
      macro.gdpTrend < 3 ? 'protect margin on low-demand regions' : 'expand strategic market share',
    ],
    supplyConstraints: [
      tightening ? 'reduce high-interest inventory exposure' : 'keep normal replenishment rhythm',
    ],
    riskControls: [
      highInflation ? 'tighten FX exposure controls' : 'monitor FX variance',
      'route critical supply through lowest-risk lanes',
    ],
    optimizationRules: [
      'rebalance production toward lowest landed cost',
      'prioritize high-demand regions with healthy currency flow',
    ],
  }
}

export function simulateGlobalEconomy(context = {}) {
  const market = simulateGlobalMarket(context)
  const macro = simulateMacroEconomy(market)
  const supplyChain = buildGlobalSupplyChain(market)
  const policy = generateEconomicPolicies(macro)

  return {
    mode: 'V13.6_GLOBAL_ECONOMIC_OS',
    market,
    macro,
    supplyChain,
    policy,
  }
}
