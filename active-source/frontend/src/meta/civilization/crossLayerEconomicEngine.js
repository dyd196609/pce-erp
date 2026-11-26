import { buildCivilizationState } from './unifiedCivilizationEngine.js'

function resolveState(context = {}) {
  return context.civilizationState || buildCivilizationState(context)
}

export function mapCrossLayerInteractions(context = {}) {
  const state = resolveState(context)

  return {
    enterpriseToIndustry: state.enterpriseLayer.map((enterprise) => ({
      from: enterprise.tenantId,
      to: enterprise.industry,
      impact: enterprise.business.metrics.marketHeat > 0 ? 'DEMAND_SIGNAL' : 'LOW_ACTIVITY',
    })),
    industryToCountry: state.industryLayer.map((industry, index) => ({
      from: industry.industry,
      to: state.countryLayer[index % state.countryLayer.length]?.country || 'GLOBAL',
      impact: industry.balance === 'DEFICIT' ? 'SUPPLY_PRESSURE' : 'STABLE_FLOW',
    })),
    countryToGlobal: state.countryLayer.map((country) => ({
      from: country.country,
      to: 'GLOBAL_ECONOMY',
      impact: country.inflation > 0.05 ? 'INFLATION_PRESSURE' : 'NORMAL_MACRO_FLOW',
    })),
  }
}

export function simulateCascadingEconomicEffects(context = {}) {
  const interactions = context.crossLayerInteractions || mapCrossLayerInteractions(context)
  const risks = [
    ...interactions.industryToCountry.filter((item) => item.impact === 'SUPPLY_PRESSURE'),
    ...interactions.countryToGlobal.filter((item) => item.impact === 'INFLATION_PRESSURE'),
  ]

  return risks.map((risk) => ({
    source: risk.from,
    target: risk.to,
    effect: risk.impact,
    severity: risk.impact === 'INFLATION_PRESSURE' ? 'HIGH' : 'MEDIUM',
  }))
}

export function buildMultiLayerDependencyGraph(context = {}) {
  const interactions = context.crossLayerInteractions || mapCrossLayerInteractions(context)

  return {
    nodes: [
      ...interactions.enterpriseToIndustry.map((item) => item.from),
      ...interactions.industryToCountry.map((item) => item.from),
      ...interactions.countryToGlobal.map((item) => item.from),
      'GLOBAL_ECONOMY',
    ],
    edges: [
      ...interactions.enterpriseToIndustry,
      ...interactions.industryToCountry,
      ...interactions.countryToGlobal,
    ],
  }
}

export function runCrossLayerEconomy(context = {}) {
  const interactions = mapCrossLayerInteractions(context)

  return {
    mode: 'V27_CROSS_LAYER_ECONOMY',
    interactions,
    cascadingEffects: simulateCascadingEconomicEffects({
      ...context,
      crossLayerInteractions: interactions,
    }),
    dependencyGraph: buildMultiLayerDependencyGraph({
      ...context,
      crossLayerInteractions: interactions,
    }),
  }
}
