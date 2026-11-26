import { enforceZeroHumanOperation, runGoalBasedExecution } from './zeroHumanLayer.js'

const controlHistory = []

export function enforceGoalBasedExecution(context = {}) {
  const result = runGoalBasedExecution(context)
  const zeroHuman = {
    mode: 'V30_ZERO_HUMAN_CONTROL_LAYER',
    zeroHumanLayer: 'ACTIVE',
    fullAutonomyMode: 'ON',
    manualApprovalRequired: false,
    approvalPolicy: 'NO_MANUAL_APPROVAL_REQUIRED',
    controlPrinciple: 'GOAL_BASED_EXECUTION_ONLY',
    ...result,
    timestamp: Date.now(),
  }

  controlHistory.unshift(zeroHuman)
  if (controlHistory.length > 100) controlHistory.length = 100

  return zeroHuman
}

export function requireNoManualApproval(context = {}) {
  return {
    ...enforceZeroHumanOperation(context),
    manualApprovalRequired: false,
    noManualApprovalRequired: true,
  }
}

export function activateZeroHumanControl(context = {}) {
  return enforceGoalBasedExecution(context)
}

export function getZeroHumanControlSnapshot() {
  return {
    zeroHumanLayer: 'ACTIVE',
    latest: controlHistory[0] || null,
    history: [...controlHistory],
    metrics: {
      goalBasedRuns: controlHistory.length,
      manualApprovalRate: 0,
      autonomyMode: 100,
    },
  }
}

