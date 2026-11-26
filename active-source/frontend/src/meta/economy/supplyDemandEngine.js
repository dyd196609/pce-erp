import { runMarketControl } from '../business/marketControlEngine.js'

export function controlModulePopularity(context = {}) {
  const market = runMarketControl(context)

  return market.popularity.map((item) => ({
    ...item,
    control: item.heat === 'HOT' ? 'MAINTAIN' : 'NUDGE_OR_RETIRE',
  }))
}

export function throttleFeatures(context = {}) {
  const market = runMarketControl(context)
  const supplyHeavy = market.supplyDemand.balance === 'SUPPLY_HEAVY'

  return {
    enabled: supplyHeavy,
    target: supplyHeavy ? 'LOW_USAGE_FEATURES' : 'NONE',
    action: supplyHeavy ? 'THROTTLE_VISIBILITY' : 'NO_THROTTLE',
  }
}

export function shapeDemand(context = {}) {
  const market = runMarketControl(context)

  return market.popularity.map((item) => ({
    moduleKey: item.moduleKey,
    heat: item.heat,
    action: item.heat === 'HOT' ? 'EXPAND_CAPACITY' : 'CREATE_DISCOVERY_PROMPT',
  }))
}

export function analyzeDemand(context = {}) {
  const controls = controlModulePopularity(context)
  const hot = controls.filter((item) => item.heat === 'HOT').length

  return {
    pressure: controls.length === 0 ? 0 : hot / controls.length,
    controls,
    shaping: shapeDemand(context),
  }
}

export function analyzeSupply(context = {}) {
  const market = runMarketControl(context)

  return {
    supply: market.supplyDemand.supply,
    demand: market.supplyDemand.demand,
    balance: market.supplyDemand.balance,
    throttling: throttleFeatures(context),
  }
}
