import { buildEconomicGraph } from './economicGraphEngine.js'

export function calculatePriceRippleEffects(context = {}) {
  const graph = buildEconomicGraph(context.tenants)

  return graph.interactions.map((interaction) => ({
    ...interaction,
    rippleAction: interaction.impactLevel === 'HIGH' ? 'HEDGE_PRICE_CHANGE' : 'MONITOR',
  }))
}

export function simulateCompetitorPricing(context = {}) {
  const graph = buildEconomicGraph(context.tenants)
  const averagePriceIndex = graph.nodes.length
    ? graph.nodes.reduce((sum, node) => sum + node.priceIndex, 0) / graph.nodes.length
    : 1

  return graph.nodes.map((node) => ({
    tenantId: node.id,
    priceIndex: node.priceIndex,
    competitorGap: Number((node.priceIndex - averagePriceIndex).toFixed(3)),
    action: node.priceIndex > averagePriceIndex ? 'PROTECT_MARGIN' : 'GAIN_SHARE',
  }))
}

export function propagateSupplyChainCost(context = {}) {
  const graph = buildEconomicGraph(context.tenants)

  return graph.edges.map((edge) => ({
    from: edge.from,
    to: edge.to,
    costImpact: edge.pressure === 'SHORTAGE' ? 0.08 : 0.02,
    propagation: edge.pressure === 'SHORTAGE' ? 'UPSTREAM_COST_PRESSURE' : 'NORMAL_PASS_THROUGH',
  }))
}

export function simulateCrossEnterprisePricing(context = {}) {
  return {
    mode: 'V25_CROSS_ENTERPRISE_PRICING',
    rippleEffects: calculatePriceRippleEffects(context),
    competitorPricing: simulateCompetitorPricing(context),
    costPropagation: propagateSupplyChainCost(context),
  }
}
