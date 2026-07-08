export function optimizeControl(feedback = {}) {
  const riskIncreased = feedback.errorRate > 0.1 || feedback.blockingRate > 0.2
  const safeRuntime = feedback.errorRate < 0.03 && feedback.blockingRate < 0.05

  return {
    policy: safeRuntime ? 'RELAX_WHEN_SAFE' : riskIncreased ? 'TIGHTEN_RISK_RULES' : 'MONITOR',
    thresholds: {
      restrict: riskIncreased ? 0.2 : safeRuntime ? 0.5 : 0.3,
      block: riskIncreased ? 0.45 : safeRuntime ? 0.8 : 0.6,
    },
    control: {
      relaxRules: safeRuntime,
      tightenRules: riskIncreased,
      autoAdjustRestrictBlockThresholds: true,
    },
  }
}
