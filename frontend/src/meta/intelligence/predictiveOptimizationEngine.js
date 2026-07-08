export function predictBottlenecks(context = {}) {
  const bottlenecks = context.optimizationRuntime?.process?.bottlenecks
    || context.processOptimization?.bottlenecks
    || []

  return bottlenecks.map((item, index) => ({
    id: `predicted:${index + 1}`,
    step: item.step,
    role: item.role,
    probability: item.severity === 'HIGH' ? 0.86 : item.severity === 'MEDIUM' ? 0.64 : 0.38,
    predictedImpact: item.severity === 'HIGH' ? 'execution_delay' : 'handoff_slowdown',
    proactiveAction: item.recommendation,
  }))
}

export function simulateFuturePerformance(context = {}) {
  const performance = context.optimizationRuntime?.performance?.processEfficiency
    || context.performance?.processEfficiency
    || { score: 80 }
  const gain = context.optimizationRuntime?.process?.efficiencyGain?.gain || 0

  return {
    currentScore: performance.score,
    forecastScore: Math.min(100, performance.score + gain + 5),
    horizon: 'next_process_cycle',
  }
}

export function recommendProactiveImprovements(context = {}) {
  const predictions = predictBottlenecks(context)

  return predictions.length
    ? predictions.map((prediction) => ({
        target: prediction.step,
        owner: prediction.role,
        action: prediction.proactiveAction,
        priority: prediction.probability >= 0.7 ? 'HIGH' : 'MEDIUM',
      }))
    : [{
        target: 'purchase',
        owner: 'Process Owner',
        action: 'Keep monitoring optimized workflow path',
        priority: 'LOW',
      }]
}

export function forecastImprovements(context = {}) {
  return {
    predictiveOptimization: 'ACTIVE',
    predictedBottlenecks: predictBottlenecks(context),
    futurePerformance: simulateFuturePerformance(context),
    proactiveImprovements: recommendProactiveImprovements(context),
  }
}
