import { runEcosystemGovernance } from '../governance/governanceRuntime.js'

export function generateGovernanceRules(context = {}) {
  const governance = runEcosystemGovernance(context)

  return [
    {
      key: 'PLUGIN_MIN_SCORE',
      value: governance.quality.averageScore < 70 ? 70 : 60,
      action: 'REVIEW_BELOW_THRESHOLD',
    },
    {
      key: 'SANDBOX_REQUIRED',
      value: true,
      action: 'BLOCK_NON_SANDBOX_PLUGIN',
    },
    {
      key: 'SECURITY_THREAT_ISOLATION',
      value: governance.security.threatCount > 0 ? 'STRICT' : 'STANDARD',
      action: 'ISOLATE_UNSAFE_WORKFLOW',
    },
  ]
}

export function adjustEcosystemPolicies(context = {}) {
  const governance = runEcosystemGovernance(context)

  return {
    commissionPolicy: governance.revenueFairness.fairnessIndex < 70
      ? 'LOWER_PLATFORM_COMMISSION'
      : 'KEEP_STANDARD_COMMISSION',
    promotionPolicy: governance.quality.averageScore >= 80
      ? 'PROMOTE_HIGH_SCORE_PLUGINS'
      : 'QUALITY_REVIEW_FIRST',
  }
}

export function evolveSecurityConstraints(context = {}) {
  const governance = runEcosystemGovernance(context)

  return {
    sandboxLimits: governance.security.threatCount > 0
      ? { maxActions: 10, maxPayloadSize: 5000 }
      : { maxActions: 20, maxPayloadSize: 10000 },
    apiScope: '/api/execution/*',
    mutationAllowed: false,
  }
}

export function generateAutonomousPolicy(context = {}) {
  return {
    mode: 'V22_AUTONOMOUS_POLICY',
    rules: generateGovernanceRules(context),
    policies: adjustEcosystemPolicies(context),
    securityConstraints: evolveSecurityConstraints(context),
  }
}
