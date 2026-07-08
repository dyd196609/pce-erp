import { buildEconomicGraph } from './economicGraphEngine.js'

export function forecastIndustryDemand(context = {}) {
  const graph = buildEconomicGraph(context.tenants)
  const totalDemand = graph.nodes.reduce((sum, node) => sum + node.demand, 0)
  const averageDemand = graph.nodes.length ? totalDemand / graph.nodes.length : 0

  return {
    totalDemand,
    averageDemand,
    trend: averageDemand > 100 ? 'EXPANSION' : averageDemand > 70 ? 'STABLE' : 'SOFTENING',
  }
}

export function simulateSupplyChainPressure(context = {}) {
  const graph = buildEconomicGraph(context.tenants)
  const shortageEdges = graph.edges.filter((edge) => edge.pressure === 'SHORTAGE')

  return {
    pressureScore: graph.edges.length === 0 ? 0 : shortageEdges.length / graph.edges.length,
    shortageEdges,
    status: shortageEdges.length ? 'PRESSURE' : 'BALANCED',
  }
}

export function balanceSectorSupply(context = {}) {
  const graph = buildEconomicGraph(context.tenants)
  const sectorMap = {}

  graph.nodes.forEach((node) => {
    if (!sectorMap[node.industry]) {
      sectorMap[node.industry] = {
        industry: node.industry,
        demand: 0,
        supply: 0,
      }
    }

    sectorMap[node.industry].demand += node.demand
    sectorMap[node.industry].supply += node.supply
  })

  return Object.values(sectorMap).map((sector) => ({
    ...sector,
    balance: sector.supply >= sector.demand ? 'SURPLUS' : 'DEFICIT',
    gap: sector.supply - sector.demand,
  }))
}

export function simulateIndustrySupply(context = {}) {
  return {
    mode: 'V25_INDUSTRY_SUPPLY_SIMULATION',
    demandForecast: forecastIndustryDemand(context),
    supplyPressure: simulateSupplyChainPressure(context),
    sectorBalance: balanceSectorSupply(context),
  }
}
