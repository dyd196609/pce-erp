import { runAutonomousBusiness } from '../business/businessAutonomyRuntime.js'
import { runGlobalEconomicSystem } from '../global/globalEconomicRuntime.js'
import { runWorldEconomicSystem } from '../world/worldEconomicRuntime.js'

const defaultIndustries = ['manufacturing', 'logistics', 'retail', 'finance']

export function mapEnterprises(context = {}) {
  const tenants = context.tenants?.length
    ? context.tenants
    : [
        { id: 'supplier_a', plan: 'pro', industry: 'manufacturing' },
        { id: 'manufacturer_b', plan: 'enterprise', industry: 'manufacturing' },
        { id: 'retailer_c', plan: 'basic', industry: 'retail' },
      ]

  return tenants.map((tenant) => ({
    tenantId: tenant.id,
    industry: tenant.industry || 'general',
    plan: tenant.plan || 'basic',
    business: runAutonomousBusiness({
      tenantId: tenant.id,
      plan: tenant.plan || 'basic',
    }),
  }))
}

export function mapIndustries(context = {}) {
  const globalEconomic = runGlobalEconomicSystem(context)
  const sectors = globalEconomic.industrySupply.sectorBalance
  const fallback = defaultIndustries.map((industry) => ({
    industry,
    demand: 80,
    supply: 82,
    balance: 'SURPLUS',
    gap: 2,
  }))

  return (sectors.length ? sectors : fallback).map((sector) => ({
    ...sector,
    stability: sector.balance === 'SURPLUS' ? 88 : 64,
  }))
}

export function mapCountries(context = {}) {
  const world = runWorldEconomicSystem(context)

  return world.countryEconomies.map((country) => ({
    ...country,
    stability: Math.max(0, Math.round(100 - country.inflation * 100 + country.employment * 10)),
  }))
}

export function mapGlobalEconomy(context = {}) {
  const globalEconomic = runGlobalEconomicSystem(context)
  const world = runWorldEconomicSystem(context)

  return {
    globalEconomic,
    world,
    health: Math.round((globalEconomic.metrics.macroProfitEfficiency + world.metrics.macroStability) / 2),
  }
}

export function buildCivilizationState(context = {}) {
  const enterpriseLayer = mapEnterprises(context)
  const industryLayer = mapIndustries(context)
  const countryLayer = mapCountries(context)
  const globalLayer = mapGlobalEconomy(context)

  return {
    mode: 'V27_UNIFIED_CIVILIZATION_MODEL',
    enterpriseLayer,
    industryLayer,
    countryLayer,
    globalLayer,
  }
}
