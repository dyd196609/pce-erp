import { executeFinancialOps } from './autonomousFinanceEngine.js'
import { runFinancialAutonomy } from './financialAutonomyEngine.js'

const autopilotHistory = []

export function autoSettlement(context = {}) {
  const finance = runFinancialAutonomy(context)
  return finance.settlement
}

export function autoAccounting(context = {}) {
  const operations = executeFinancialOps(context)
  return {
    status: 'POSTED',
    accrualStatus: 'AUTO_POSTED',
    invoiceCount: operations.invoiceProcessing.processed.length,
    paymentValue: operations.metrics.paymentExecutionValue,
    timestamp: Date.now(),
  }
}

export function optimizeProfit(context = {}) {
  const operations = executeFinancialOps(context)
  return {
    status: 'OPTIMIZED',
    strategy: operations.optimization.strategy,
    optimizedCash: operations.optimization.optimizedCash,
    optimizationGain: operations.metrics.financialOptimizationGain,
    timestamp: Date.now(),
  }
}

export function runFinancialAutopilot(context = {}) {
  const operations = executeFinancialOps(context)
  const result = {
    mode: 'V30_FINANCIAL_AUTOPILOT_ENGINE',
    financialAutopilot: 'ACTIVE',
    settlement: autoSettlement(context),
    accounting: autoAccounting(context),
    profitOptimization: optimizeProfit(context),
    operations,
    metrics: {
      settlementAutomation: 100,
      accountingAutomation: 100,
      profitOptimizationGain: operations.metrics.financialOptimizationGain,
      paymentExecutionValue: operations.metrics.paymentExecutionValue,
    },
    timestamp: Date.now(),
  }

  autopilotHistory.unshift(result)
  if (autopilotHistory.length > 100) autopilotHistory.length = 100

  return result
}

export function getFinancialAutopilotSnapshot() {
  return {
    financialAutopilot: 'ACTIVE',
    latest: autopilotHistory[0] || null,
    history: [...autopilotHistory],
    metrics: {
      autopilotRuns: autopilotHistory.length,
      settlementAutomation: autopilotHistory[0]?.metrics?.settlementAutomation ?? 100,
      accountingAutomation: autopilotHistory[0]?.metrics?.accountingAutomation ?? 100,
    },
  }
}

