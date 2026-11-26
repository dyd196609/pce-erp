export function applyBusinessPolicy(context = {}) {
  const prediction = context.predictionRuntime || context.predictiveDecision || context.prediction || {}
  const approval = prediction.approvalProbability || {}
  const risk = prediction.riskLevel || {}
  const cost = prediction.costImpact || {}
  const approvalScore = Number(approval.probabilityScore || 0)
  const totalImpact = Number(cost.totalImpact || 0)

  return {
    policyDecision: 'ENABLED',
    policy: 'ENTERPRISE_DECISION_GUARDRAIL',
    canAutoExecute: risk.level === 'LOW' && approvalScore >= 75 && totalImpact <= 0,
    enforcedRules: [
      'LOW_RISK_REQUIRED_FOR_AUTO_EXECUTION',
      'APPROVAL_SCORE_MIN_75',
      'COST_IMPACT_MUST_NOT_INCREASE',
    ],
  }
}

export function enforceEnterpriseRules(context = {}) {
  const policy = applyBusinessPolicy(context)

  return {
    ...policy,
    enforcement: policy.canAutoExecute ? 'ALLOW_AUTO_EXECUTION' : 'REQUIRE_CONTROLLED_REVIEW',
  }
}

export function overrideRiskyOperations(context = {}) {
  const policy = enforceEnterpriseRules(context)

  return {
    override: policy.canAutoExecute ? 'NO_OVERRIDE_REQUIRED' : 'AUTO_OVERRIDE_TO_REVIEW',
    policy,
  }
}
