import { simulateCountryEconomy } from './countryEconomicModel.js'
import { simulateGlobalSupplyChain } from './globalSupplyChainEngine.js'
import { simulateFXTrade } from './fxTradeEngine.js'
import { simulateMacroShock } from './macroShockEngine.js'
import { simulateGlobalTradeFlow } from './globalTradeFlowEngine.js'

export function runWorldEconomicSystem(context = {}) {
  const countries = context.countries?.length
    ? context.countries
    : [{ code: 'CN' }, { code: 'US' }, { code: 'DE' }, { code: 'VN' }]
  const countryEconomies = countries.map(simulateCountryEconomy)
  const supplyChain = simulateGlobalSupplyChain(context)
  const fxTrade = simulateFXTrade(context)
  const macroShock = simulateMacroShock({
    ...context,
    countries,
  })
  const tradeFlow = simulateGlobalTradeFlow(context)
  const averageGDP = countryEconomies.length
    ? countryEconomies.reduce((sum, country) => sum + country.gdp, 0) / countryEconomies.length
    : 0
  const macroStability = Math.max(0, Math.round(100 - macroShock.crisis.severity * 100 - supplyChain.disruptionPropagation.length * 5))

  return {
    mode: 'V26_GLOBAL_ECONOMY_SIMULATION_OS',
    worldEconomicMode: 'ON',
    countrySimulation: 'ACTIVE',
    fxTradeSimulation: 'ENABLED',
    macroShockEngine: 'ACTIVE',
    countryEconomies,
    supplyChain,
    fxTrade,
    macroShock,
    tradeFlow,
    metrics: {
      globalGDP: Math.round(averageGDP),
      currencyFlowCount: fxTrade.currencyFluctuation.length,
      supplyChainNodes: supplyChain.logisticsNetwork.length,
      macroStability,
    },
  }
}
