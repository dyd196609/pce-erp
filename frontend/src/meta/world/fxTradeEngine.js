const defaultCurrencies = [
  { code: 'USD', rate: 1, volatility: 0.02 },
  { code: 'CNY', rate: 7.2, volatility: 0.035 },
  { code: 'EUR', rate: 0.92, volatility: 0.018 },
  { code: 'VND', rate: 25400, volatility: 0.045 },
]

function currencies(context = {}) {
  return context.currencies?.length ? context.currencies : defaultCurrencies
}

export function simulateCurrencyFluctuation(context = {}) {
  return currencies(context).map((currency) => ({
    code: currency.code,
    rate: currency.rate,
    projectedRate: Number((currency.rate * (1 + currency.volatility)).toFixed(4)),
    volatility: currency.volatility,
  }))
}

export function simulateTradeImbalance(context = {}) {
  const flows = context.tradeFlows?.length
    ? context.tradeFlows
    : [
        { from: 'CN', to: 'US', exports: 130, imports: 90 },
        { from: 'DE', to: 'CN', exports: 80, imports: 72 },
      ]

  return flows.map((flow) => ({
    ...flow,
    imbalance: flow.exports - flow.imports,
    status: Math.abs(flow.exports - flow.imports) > 30 ? 'IMBALANCED' : 'STABLE',
  }))
}

export function calculateCrossBorderPricingImpact(context = {}) {
  return simulateCurrencyFluctuation(context).map((currency) => ({
    currency: currency.code,
    costImpact: Number(((currency.projectedRate - currency.rate) / currency.rate).toFixed(4)),
    action: currency.volatility > 0.03 ? 'APPLY_FX_BUFFER' : 'MONITOR',
  }))
}

export function simulateFXTrade(context = {}) {
  return {
    mode: 'V26_FX_TRADE',
    currencyFluctuation: simulateCurrencyFluctuation(context),
    tradeImbalance: simulateTradeImbalance(context),
    crossBorderPricingImpact: calculateCrossBorderPricingImpact(context),
  }
}
