import { autoDecide } from '../decision/decisionAutomationEngine.js'
import { autoRepair } from './selfHealingEngine.js'
import { continuousRun } from './continuousLoopEngine.js'
import { eliminateManualApproval } from './zeroApprovalLayer.js'

export function autoExecute(context = {}) {
  const decision = context.decisionAutomationRuntime || autoDecide(context)
  const zeroApproval = eliminateManualApproval({
    ...context,
    decisionAutomationRuntime: decision,
  })
  const executionAllowed = decision.autoExecution === 'READY'
    && zeroApproval.lowRisk.autoApproveLowRisk
    && decision.riskDecision?.action === 'ALLOW_LOW_RISK_EXECUTION'

  return {
    autoExecution: 'ACTIVE',
    executed: executionAllowed,
    executionMode: executionAllowed ? 'ZERO_TOUCH_EXECUTION' : 'CONTROLLED_AUTONOMY',
    zeroApproval,
    executionTrace: [
      decision.approvalDecision?.action,
      decision.riskDecision?.action,
      zeroApproval.finalApprovalPath,
      executionAllowed ? 'EXECUTED' : 'SUPERVISED',
    ],
  }
}

export function runAutonomousERP(context = {}) {
  const decision = context.decisionAutomationRuntime || autoDecide(context)
  const execution = autoExecute({
    ...context,
    decisionAutomationRuntime: decision,
  })
  const healing = autoRepair({
    ...context,
    decisionAutomationRuntime: decision,
    autonomousExecution: execution,
  })
  const loop = continuousRun({
    ...context,
    decisionAutomationRuntime: decision,
    autonomousExecution: execution,
    healing,
  })

  return {
    fullAutonomyMode: 'ON',
    autoExecution: 'ACTIVE',
    zeroApproval: 'ENABLED',
    continuousLoop: 'ON',
    decision,
    execution,
    healing,
    loop,
    unattendedMode: execution.executed && healing.consistency?.consistent !== false ? 'ACTIVE' : 'CONTROLLED',
  }
}
