import { evaluateDecision } from '../ai/decisionEngine.js'
import { executeDecision } from '../ai/executionEngine.js'
import { enforcePolicies } from './policyEnforcementEngine.js'
import { optimizeWorkflow } from './workflowOptimizationAI.js'
import { detectAndIntervene } from './riskInterventionEngine.js'

export function runAutonomousDecisionCycle(context = {}) {
  const decision = context.decision || evaluateDecision(context)
  const policies = enforcePolicies({
    ...context,
    decision,
  })
  const intervention = detectAndIntervene({
    ...context,
    decision,
  })
  const canAutoRun = policies.businessRules.level === 'AUTO'
    && intervention.prevention.blocked === false
    && ['AUTO_APPROVE', 'APPROVE'].includes(decision.recommendation)

  const execution = canAutoRun
    ? executeDecision({
        ...context,
        decision,
        action: decision.recommendation === 'AUTO_APPROVE' ? 'APPROVE' : context.action || 'SUBMIT',
        manualConfirm: decision.risk?.level !== 'LOW',
      })
    : {
        status: policies.businessRules.level === 'BLOCKED' ? 'BLOCKED' : 'GOVERNANCE_MONITORING',
        executed: false,
        reason: intervention.prevention.reason || policies.businessRules.reason,
      }

  return {
    decision,
    policies,
    intervention,
    execution,
    autopilot: canAutoRun ? 'RUNNING' : 'GATED',
  }
}

export function runSelfRunningWorkflows(context = {}) {
  const optimization = optimizeWorkflow(context)

  return {
    mode: 'SELF_RUNNING_WORKFLOW',
    enabled: optimization.path.priority === 'HIGH' || optimization.score >= 75,
    optimization,
  }
}

export function runBusinessAutopilot(context = {}) {
  const cycle = runAutonomousDecisionCycle(context)
  const workflow = runSelfRunningWorkflows(context)

  return {
    mode: 'V29_BUSINESS_AUTOPILOT',
    autopilotStatus: cycle.autopilot,
    cycle,
    workflow,
    stability: cycle.autopilot === 'RUNNING' && !cycle.intervention.rollback.rollbackRequired ? 88 : 64,
  }
}
