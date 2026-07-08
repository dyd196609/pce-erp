import { runContractGovernance } from './contractGovernanceEngine.js'
import { recordDecision } from './decisionMemoryEngine.js'
import { optimizeDecisionWeights } from './decisionWeightOptimizer.js'
import { runExecutionIntelligence } from './executionIntelligenceEngine.js'
import { recordEvent, triggerAutoHealingIfMonitor } from './monitoringLayer.js'
import { evaluateSystemState } from './systemStateManager.js'
import { applyReviewDecisionToSystem } from '../review/reviewControlEngine.js'

function resolveFinalDecision(execution, governance, state) {
  if (state.authority === 'SELF_HEALING') {
    return {
      decision: 'RESTRICT',
      source: 'SELF_HEALING_CONTROL',
      reason: 'System recovery mode active',
      weights: optimizeDecisionWeights(),
      state,
    }
  }

  if (state.authority === 'GOVERNANCE') {
    return {
      decision: governance.decision === 'BLOCK_SYSTEM' ? 'BLOCK' : 'RESTRICT',
      source: 'GOVERNANCE_CONTROL',
      reason: 'Governance has control authority',
      weights: optimizeDecisionWeights(),
      state,
    }
  }

  const weights = optimizeDecisionWeights()

  if (state.authority === 'EXECUTION') {
    return {
      decision: execution.decision === 'BLOCK_OR_REVIEW' ? 'MONITOR' : 'ALLOW',
      source: 'EXECUTION_CONTROL',
      reason: 'Execution is in control mode',
      weights,
      state,
    }
  }

  if (governance.decision === 'BLOCK_SYSTEM') {
    return {
      decision: 'BLOCK',
      source: 'GOVERNANCE',
      reason: 'System blocked by governance due to high contract drift',
      weights,
      state,
    }
  }

  const execScore = execution.anomaly?.risky ? 1 * weights.executionWeight : 0
  const govScore = governance.decision === 'RESTRICT' ? 1 * weights.governanceWeight : 0

  if (execution.anomaly?.risky && execScore >= govScore) {
    return {
      decision: 'RESTRICT',
      source: 'EXECUTION_WEIGHTED',
      reason: 'Execution anomaly detected',
      weights,
      state,
    }
  }

  if (governance.decision === 'RESTRICT' && govScore > execScore) {
    return {
      decision: 'RESTRICT',
      source: 'GOVERNANCE_WEIGHTED',
      reason: 'Governance risk threshold exceeded',
      weights,
      state,
    }
  }

  if (governance.decision === 'MONITOR' || execution.decision === 'BLOCK_OR_REVIEW') {
    return {
      decision: 'MONITOR',
      source: 'BOTH',
      reason: 'Partial risk detected in execution or governance',
      weights,
      state,
    }
  }

  return {
    decision: 'ALLOW',
    source: weights.executionWeight >= weights.governanceWeight ? 'EXECUTION_WEIGHTED' : 'GOVERNANCE_WEIGHTED',
    reason: 'No risk detected across execution and governance layers',
    weights,
    state,
  }
}

export function runUnifiedDecisionKernel(patchSet) {
  const execution = runExecutionIntelligence(patchSet)
  const governance = runContractGovernance()
  const reviewControl = applyReviewDecisionToSystem()
  const systemState = evaluateSystemState({
    systemError: execution.anomaly?.risky || reviewControl.decision === 'RESTRICT',
  })
  let finalDecision = resolveFinalDecision(execution, governance, systemState)

  if (reviewControl.decision === 'RESTRICT') {
    finalDecision = {
      decision: 'RESTRICT',
      source: 'REVIEW_CONTROL',
      reason: reviewControl.reason,
      weights: finalDecision.weights,
      state: systemState,
    }
  } else if (reviewControl.decision === 'MONITOR' && finalDecision.decision === 'ALLOW') {
    finalDecision = {
      decision: 'MONITOR',
      source: 'REVIEW_CONTROL',
      reason: reviewControl.reason,
      weights: finalDecision.weights,
      state: systemState,
    }
  }

  const result = {
    mode: 'V6.9_UNIFIED_DECISION_KERNEL',
    execution,
    governance,
    reviewControl,
    systemState,
    finalDecision,
    auditTrail: {
      executionMode: execution.mode,
      governanceMode: governance.decision,
      reviewMode: reviewControl.decision,
      systemMode: systemState.mode,
      controlAuthority: systemState.authority,
      timestamp: Date.now(),
    },
  }

  recordEvent({
    type: finalDecision.decision === 'ALLOW' ? 'DECISION' : 'ERROR',
    module: 'unifiedDecisionKernel',
    status: finalDecision.decision,
    source: finalDecision.source,
    message: finalDecision.reason,
  })

  recordDecision({
    executionDecision: execution.decision,
    governanceDecision: governance.decision,
    reviewDecision: reviewControl.decision,
    finalDecision: finalDecision.decision,
    source: finalDecision.source,
    weights: finalDecision.weights,
  })

  triggerAutoHealingIfMonitor(governance, patchSet)

  return result
}
