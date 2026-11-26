import { optimizeRevenue } from '../business/autonomousRevenueEngine.js'

export function guideWorkflow(context = {}) {
  const revenue = optimizeRevenue(context)

  return {
    target: revenue.usage.intensity === 'LOW' ? 'FIRST_WORKFLOW_EXECUTION' : 'ADVANCED_WORKFLOW_AUTOMATION',
    message: revenue.usage.intensity === 'LOW'
      ? 'Guide user to execute first workflow'
      : 'Guide user to automate repeated workflows',
  }
}

export function nudgeFeatures(context = {}) {
  const revenue = optimizeRevenue(context)

  return revenue.upgradePaths.map((path) => ({
    feature: path.to === 'enterprise' ? 'AI_DECISION' : 'SIMULATION',
    nudge: `Promote ${path.to} plan because ${path.reason}`,
  }))
}

export function influenceUsageOptimization(context = {}) {
  const revenue = optimizeRevenue(context)

  return {
    action: revenue.usage.intensity === 'HIGH' ? 'PROMOTE_BATCH_WORKFLOW' : 'PROMOTE_MODULE_DISCOVERY',
    expectedImpact: revenue.usage.intensity === 'HIGH' ? 'REDUCE_FRICTION' : 'INCREASE_USAGE',
  }
}

export function influenceBehavior(context = {}) {
  return {
    mode: 'V24_BEHAVIOR_INFLUENCE',
    workflowGuidance: guideWorkflow(context),
    featureNudges: nudgeFeatures(context),
    usageOptimization: influenceUsageOptimization(context),
  }
}
