import { buildEnterpriseGraph } from './enterpriseGraphEngine.js'

export function simulateCompetition(enterprises = [], context = {}) {
  const graph = buildEnterpriseGraph(enterprises)
  const totalCapacity = graph.nodes.reduce((sum, node) => sum + node.capacity, 0) || 1
  const averagePrice = graph.nodes.reduce((sum, node) => sum + node.price, 0) / (graph.nodes.length || 1)
  const disruption = context.supplyDisruption === true

  const market = graph.nodes.map((node) => {
    const priceImpact = node.price <= averagePrice ? 1.08 : 0.94
    const disruptionImpact = disruption && ['supplier', 'manufacturer'].includes(node.role) ? 0.85 : 1
    const marketShare = (node.capacity / totalCapacity) * priceImpact * disruptionImpact

    return {
      enterprise: node.id,
      role: node.role,
      marketShare,
      pricingImpact: priceImpact,
      disruptionRisk: disruptionImpact < 1 ? 'HIGH' : 'LOW',
    }
  })

  return {
    mode: 'COMPETITION_SIMULATION',
    market,
    supplyChainDisruption: disruption,
  }
}
