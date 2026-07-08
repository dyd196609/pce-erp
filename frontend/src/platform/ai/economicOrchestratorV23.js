import { balanceEconomy } from '../economy/economicBrainV23'
import { getAllEnterprises } from '../economy/enterpriseNetworkV23'

/**
 * ============================
 * AI Economic Orchestrator
 * 经济调度器
 * ============================
 */

export const runEconomicCycle = () => {
  const balance = balanceEconomy()
  const enterprises = getAllEnterprises()

  enterprises.forEach((ent) => {
    Object.keys(balance).forEach((key) => {
      if (balance[key] > 0) {
        ent.strategy = 'EXPAND'
      } else {
        ent.strategy = 'REDUCE_COST'
      }
    })
  })

  return {
    balance,
    enterprises,
  }
}
