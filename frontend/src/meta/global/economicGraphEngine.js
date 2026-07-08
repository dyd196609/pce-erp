import { computeEconomicState } from '../economy/economicDynamicsEngine.js'

const defaultTenants = [
  { id: 'supplier_a', industry: 'manufacturing', plan: 'pro', role: 'supplier', demand: 72, supply: 120 },
  { id: 'manufacturer_b', industry: 'manufacturing', plan: 'enterprise', role: 'manufacturer', demand: 110, supply: 95 },
  { id: 'distributor_c', industry: 'logistics', plan: 'pro', role: 'distributor', demand: 88, supply: 76 },
  { id: 'retailer_d', industry: 'retail', plan: 'basic', role: 'retailer', demand: 130, supply: 62 },
]

function normalizeTenants(tenants = []) {
  return (tenants.length ? tenants : defaultTenants).map((tenant, index) => ({
    id: tenant.id || `tenant_${index + 1}`,
    industry: tenant.industry || 'general',
    plan: tenant.plan || 'basic',
    role: tenant.role || 'enterprise',
    demand: Number(tenant.demand ?? 80 + index * 12),
    supply: Number(tenant.supply ?? 90 - index * 8),
    priceIndex: Number(tenant.priceIndex ?? 1 + index * 0.04),
  }))
}

export function mapEnterprises(tenants = []) {
  return normalizeTenants(tenants).map((tenant) => {
    const economy = computeEconomicState({
      tenantId: tenant.id,
      plan: tenant.plan,
    })

    return {
      ...tenant,
      economy,
      economicScore: economy.metrics.profitMaximizationScore,
      pricingVolatility: economy.metrics.pricingVolatility,
    }
  })
}

export function mapSupplyChainRelations(tenants = []) {
  const nodes = normalizeTenants(tenants)

  return nodes.slice(0, -1).map((tenant, index) => ({
    from: tenant.id,
    to: nodes[index + 1].id,
    relation: `${tenant.role}_to_${nodes[index + 1].role}`,
    flow: Math.min(tenant.supply, nodes[index + 1].demand),
    pressure: nodes[index + 1].demand > tenant.supply ? 'SHORTAGE' : 'BALANCED',
  }))
}

export function calculateCrossTenantImpact(tenants = []) {
  const nodes = normalizeTenants(tenants)

  return nodes.map((tenant, index) => {
    const neighbor = nodes[index + 1] || nodes[0]
    const priceRipple = Number(((neighbor.priceIndex - tenant.priceIndex) * 100).toFixed(2))

    return {
      source: tenant.id,
      target: neighbor.id,
      priceRipple,
      demandImpact: neighbor.demand - tenant.supply,
      impactLevel: Math.abs(priceRipple) > 8 || neighbor.demand > tenant.supply ? 'HIGH' : 'NORMAL',
    }
  })
}

export function buildEconomicGraph(tenants = []) {
  const nodes = mapEnterprises(tenants)
  const edges = mapSupplyChainRelations(tenants)
  const interactions = calculateCrossTenantImpact(tenants)

  return {
    mode: 'V25_MULTI_ENTERPRISE_ECONOMIC_GRAPH',
    nodes,
    edges,
    interactions,
  }
}
