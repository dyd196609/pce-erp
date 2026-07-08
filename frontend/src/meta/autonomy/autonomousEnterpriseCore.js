import {
  autoDecide as decideWithAutopilot,
  autoExecute as executeWithAutopilot,
  continuousOptimize as optimizeWithAutopilot,
} from './businessOrchestrator.js'
import { runContinuousRuntime } from './continuousRuntimeEngine.js'
import { selfHeal } from './selfHealingEngine.js'
import { runFinancialAutopilot } from './financialAutopilotEngine.js'
import { activateZeroHumanControl } from './zeroHumanControlLayer.js'

const enterpriseCoreHistory = []

export function autoDecide(context = {}) {
  return decideWithAutopilot(context)
}

export function autoExecute(context = {}) {
  const zeroHuman = activateZeroHumanControl(context)
  const continuousRuntime = runContinuousRuntime(context)
  const execution = executeWithAutopilot(context)
  const financialAutopilot = runFinancialAutopilot(context)

  return {
    mode: 'V30_AUTONOMOUS_EXECUTION',
    zeroHuman,
    continuousRuntime,
    workflowExecution: continuousRuntime.workflow,
    execution,
    financialAutopilot,
    noManualApprovalRequired: true,
    timestamp: Date.now(),
  }
}

export function continuousOptimize(context = {}) {
  return {
    mode: 'V30_CONTINUOUS_ENTERPRISE_OPTIMIZATION',
    ...optimizeWithAutopilot(context),
  }
}

export function runAutonomousEnterprise(context = {}) {
  const decisions = autoDecide(context)
  const execution = autoExecute({
    ...context,
    decision: decisions,
  })
  const healing = selfHeal({
    ...context,
    executionSnapshot: context.executionSnapshot,
  })
  const optimization = continuousOptimize({
    ...context,
    decisions,
    execution,
    healing,
  })

  const result = {
    mode: 'V30_AUTONOMOUS_ENTERPRISE_OS',
    fullAutonomyMode: 'ON',
    zeroHumanLayer: 'ACTIVE',
    continuousRuntime: 'ENABLED',
    selfHealing: 'ACTIVE',
    decisions,
    execution,
    healing,
    optimization,
    metrics: {
      enterpriseAutonomyIndex: 100,
      manualApprovalRequired: 0,
      workflowAutopilot: execution.workflowExecution?.selfRunningWorkflow || 'ACTIVE',
      financialAutopilot: execution.financialAutopilot?.financialAutopilot || 'ACTIVE',
      selfHealingRate: healing.consistency?.consistent ? 100 : 0,
    },
    timestamp: Date.now(),
  }

  enterpriseCoreHistory.unshift(result)
  if (enterpriseCoreHistory.length > 100) enterpriseCoreHistory.length = 100

  return result
}

export function getAutonomousEnterpriseSnapshot() {
  return {
    fullAutonomyMode: 'ON',
    zeroHumanLayer: 'ACTIVE',
    continuousRuntime: 'ENABLED',
    selfHealing: 'ACTIVE',
    latest: enterpriseCoreHistory[0] || null,
    history: [...enterpriseCoreHistory],
    metrics: {
      enterpriseAutonomyIndex: enterpriseCoreHistory[0]?.metrics?.enterpriseAutonomyIndex ?? 100,
      manualApprovalRequired: 0,
      autonomousRuns: enterpriseCoreHistory.length,
    },
  }
}

