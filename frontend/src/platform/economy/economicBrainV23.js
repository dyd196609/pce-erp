// ======================================
// AI Economic System V23
// 经济体大脑
// ======================================

const economy = {
  totalProfit: 0,
  demand: {},
  supply: {},
}

/**
 * 更新市场需求
 */
export const updateDemand = (type, value) => {
  economy.demand[type] = value
}

/**
 * 更新供应
 */
export const updateSupply = (type, value) => {
  economy.supply[type] = value
}

/**
 * 计算经济平衡
 */
export const balanceEconomy = () => {
  const result = {}

  Object.keys(economy.demand).forEach((key) => {
    const demand = economy.demand[key] || 0
    const supply = economy.supply[key] || 0

    result[key] = demand - supply
  })

  return result
}
