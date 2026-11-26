import { runAutonomousEcosystem } from '../ecosystem/autonomous/autonomousRuntime.js'
import { listMarketplaceModules } from '../ecosystem/marketplaceEngine.js'

export function balanceSupplyDemand(context = {}) {
  const ecosystem = runAutonomousEcosystem(context)
  const supply = listMarketplaceModules().length
  const demand = ecosystem.lifecycle.lifecycle.reduce((sum, module) => sum + module.usage, 0)

  return {
    supply,
    demand,
    balance: supply === 0 ? 'EMPTY_MARKET' : demand >= supply * 0.5 ? 'BALANCED' : 'SUPPLY_HEAVY',
  }
}

export function controlModulePopularity(context = {}) {
  const ecosystem = runAutonomousEcosystem(context)

  return ecosystem.lifecycle.lifecycle.map((module) => ({
    moduleKey: module.moduleKey,
    heat: module.usage > 0 ? 'HOT' : 'COLD',
    action: module.usage > 0 ? 'MAINTAIN_VISIBILITY' : 'BOOST_OR_RETIRE',
  }))
}

export function reshapeEcosystem(context = {}) {
  const ecosystem = runAutonomousEcosystem(context)

  return ecosystem.evolution.mutations.map((mutation) => ({
    target: mutation.target || mutation.type,
    action: mutation.action,
    status: 'MARKET_CONTROL_SUGGESTED',
  }))
}

export function runMarketControl(context = {}) {
  return {
    mode: 'V23_MARKET_CONTROL',
    supplyDemand: balanceSupplyDemand(context),
    popularity: controlModulePopularity(context),
    reshaping: reshapeEcosystem(context),
  }
}
