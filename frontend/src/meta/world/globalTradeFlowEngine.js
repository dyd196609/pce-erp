export function simulateGlobalCapitalFlow(context = {}) {
  const flows = context.capitalFlows?.length
    ? context.capitalFlows
    : [
        { from: 'US', to: 'CN', amount: 180 },
        { from: 'EU', to: 'VN', amount: 96 },
      ]

  return flows.map((flow) => ({
    ...flow,
    riskAdjustedAmount: Math.round(flow.amount * 0.94),
  }))
}

export function simulateGoodsMovement(context = {}) {
  const goods = context.goodsFlows?.length
    ? context.goodsFlows
    : [
        { from: 'CN', to: 'US', units: 1200 },
        { from: 'DE', to: 'CN', units: 560 },
      ]

  return goods.map((flow) => ({
    ...flow,
    status: flow.units > 1000 ? 'HIGH_VOLUME' : 'NORMAL',
  }))
}

export function modelServiceFlow(context = {}) {
  const services = context.serviceFlows?.length
    ? context.serviceFlows
    : [
        { from: 'US', to: 'DE', value: 72 },
        { from: 'CN', to: 'VN', value: 44 },
      ]

  return services.map((flow) => ({
    ...flow,
    growth: flow.value > 60 ? 'EXPANDING' : 'STABLE',
  }))
}

export function simulateGlobalTradeFlow(context = {}) {
  return {
    mode: 'V26_GLOBAL_TRADE_FLOW',
    capitalFlow: simulateGlobalCapitalFlow(context),
    goodsMovement: simulateGoodsMovement(context),
    serviceFlow: modelServiceFlow(context),
  }
}
