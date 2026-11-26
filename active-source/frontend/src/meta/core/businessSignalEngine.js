export function detectBusinessSignals(context = {}) {
  const signals = []

  if (context.stockLow) {
    signals.push({
      type: 'LOW_STOCK',
      severity: 'HIGH',
    })
  }

  if (context.purchaseDelay) {
    signals.push({
      type: 'PURCHASE_DELAY',
      severity: 'MEDIUM',
    })
  }

  if (context.financeAnomaly) {
    signals.push({
      type: 'FINANCE_ANOMALY',
      severity: 'HIGH',
    })
  }

  return signals
}
