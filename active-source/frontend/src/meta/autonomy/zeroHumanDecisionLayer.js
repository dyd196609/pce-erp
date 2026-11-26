import { evaluateDecision } from '../ai/decisionEngine.js'
import { executeDecision } from '../ai/executionEngine.js'
import { enforcePolicies } from '../governance/policyEnforcementEngine.js'

export function makePolicyBasedDecision(context = {}) {
  const decision = context.decision || evaluateDecision(context)
  const policies = enforcePolicies({
    ...context,
    decision,
  })
  const riskLevel = decision.risk?.level || 'LOW'
  const authority = policies.businessRules.level === 'AUTO' && riskLevel !== 'HIGH'
    ? 'AI_EXECUTION_AUTHORITY'
    : 'POLICY_EXCEPTION'

  return {
    mode: 'V30_POLICY_BASED_AUTOMATIC_DECISION',
    recommendation: authority === 'AI_EXECUTION_AUTHORITY'
      ? decision.recommendation === 'REJECT' ? 'DEFER' : decision.recommendation
      : 'POLICY_EXCEPTION',
    score: decision.score,
    risk: decision.risk,
    policies,
    authority,
  }
}

export function executeWithoutHumanInput(context = {}) {
  const automaticDecision = context.automaticDecision || makePolicyBasedDecision(context)
  const allowed = automaticDecision.authority === 'AI_EXECUTION_AUTHORITY'

  if (!allowed) {
    return {
      mode: 'V30_ZERO_HUMAN_EXECUTION',
      status: 'POLICY_EXCEPTION',
      executed: false,
      humanInputRequired: false,
      reason: automaticDecision.policies.businessRules.reason,
      automaticDecision,
    }
  }

  const execution = executeDecision({
    ...context,
    decision: {
      ...(context.decision || {}),
      recommendation: automaticDecision.recommendation,
      risk: automaticDecision.risk,
      score: automaticDecision.score,
    },
    action: context.action || 'APPROVE',
    manualConfirm: true,
  })

  return {
    mode: 'V30_ZERO_HUMAN_EXECUTION',
    status: execution.executed ? 'EXECUTED_WITHOUT_HUMAN' : execution.status,
    executed: execution.executed,
    humanInputRequired: false,
    automaticDecision,
    execution,
  }
}

export function autoDecisionExecution(context = {}) {
  const automaticDecision = makePolicyBasedDecision(context)
  const execution = executeWithoutHumanInput({
    ...context,
    automaticDecision,
  })

  return {
    mode: 'V30_ZERO_HUMAN_DECISION_LAYER',
    zeroHumanDecision: automaticDecision.authority === 'AI_EXECUTION_AUTHORITY' ? 'ENABLED' : 'POLICY_EXCEPTION',
    executionAuthority: automaticDecision.authority,
    automaticDecision,
    execution,
    metrics: {
      decisionScore: automaticDecision.score,
      zeroHumanExecutionRate: execution.executed ? 1 : 0,
      policyExceptionCount: automaticDecision.authority === 'POLICY_EXCEPTION' ? 1 : 0,
    },
  }
}
