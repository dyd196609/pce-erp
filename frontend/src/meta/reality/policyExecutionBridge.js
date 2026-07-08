import { runDigitalCivilization } from '../civilization/civilizationRuntime.js'

export function convertPolicyToExecution(context = {}) {
  const civilization = context.civilization || runDigitalCivilization(context)
  const policy = context.policy || civilization.policy

  return {
    recommendedPolicy: policy?.macro?.recommendedPolicy || 'BALANCED_POLICY',
    executionPlan: [
      'notify_responsible_roles',
      'adjust_workflow_priority',
      'monitor_feedback_metrics',
    ],
  }
}

export function enforceBehavioralRules(context = {}) {
  const feedback = context.feedback || {}
  const critical = feedback.complianceRisk === 'CRITICAL' || feedback.blocked === true

  return {
    allowed: !critical,
    rule: critical ? 'HARD_STOP_REALITY_EXECUTION' : 'ALLOW_CONTROLLED_EXECUTION',
    reason: critical ? 'COMPLIANCE_OR_BLOCKED_FEEDBACK' : 'RULES_PASSED',
  }
}

export function injectRealtimeConstraints(context = {}) {
  const feedback = context.feedback || {}

  return {
    maxApprovalDelayDays: feedback.urgent ? 1 : 3,
    maxExecutionRisk: feedback.urgent ? 0.4 : 0.6,
    manualGateRequired: feedback.complianceRisk === 'HIGH' || feedback.complianceRisk === 'CRITICAL',
  }
}

export function bridgePolicyExecution(context = {}) {
  return {
    mode: 'V28_POLICY_EXECUTION_BRIDGE',
    policyExecution: convertPolicyToExecution(context),
    behavioralRules: enforceBehavioralRules(context),
    realtimeConstraints: injectRealtimeConstraints(context),
  }
}
