import { executeFinancialOps } from './autonomousFinanceEngine.js'
import { runFullWorkflow } from './selfRunningWorkflowEngine.js'
import { autoDecisionExecution } from './zeroHumanDecisionLayer.js'
import { continuousOptimization } from './continuousOptimizationEngine.js'

export function runAutonomousEnterprise(context = {}) {
  const execution = runFullWorkflow(context)
  const finance = executeFinancialOps(context)
  const decisions = autoDecisionExecution({
    ...context,
    workflowExecution: execution,
  })
  const optimization = continuousOptimization({
    ...context,
    workflowExecution: execution,
    finance,
    decisions,
  })
  const enterpriseAutonomyIndex = Math.round((
    execution.metrics.workflowAutopilotRate * 30
    + finance.metrics.invoiceAutomationRate * 25
    + decisions.metrics.zeroHumanExecutionRate * 25
    + optimization.metrics.systemSelfOptimizationRate * 20
  ))

  return {
    mode: 'V30_FULL_BUSINESS_AUTOPILOT',
    fullAutonomyMode: 'ON',
    execution,
    finance,
    decisions,
    optimization,
    metrics: {
      enterpriseAutonomyIndex,
      workflowAutopilotStatus: execution.selfRunningWorkflow,
      financialExecutionValue: finance.metrics.paymentExecutionValue,
      zeroHumanDecisionRate: decisions.metrics.zeroHumanExecutionRate,
      systemSelfOptimizationRate: optimization.metrics.systemSelfOptimizationRate,
    },
    operatingPrinciple: 'HUMAN_SETS_GOAL_SYSTEM_EXECUTES',
  }
}
