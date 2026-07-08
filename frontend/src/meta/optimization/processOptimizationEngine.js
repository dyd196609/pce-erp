import { detectBottlenecks } from './bottleneckDetectionEngine.js'
import { analyzePerformance } from './performanceAnalysisEngine.js'

export function reduceSteps(executionData = {}) {
  const timeline = executionData.timeline?.timeline || []
  const removable = timeline.filter((item) => item.durationMs <= 1000)
  const originalStepCount = timeline.length + 1
  const optimizedStepCount = Math.max(1, originalStepCount - Math.min(1, removable.length))

  return {
    originalStepCount,
    optimizedStepCount,
    reducedSteps: originalStepCount - optimizedStepCount,
    recommendation: removable.length
      ? 'Merge low-cost handoff into adjacent workflow step'
      : 'Keep current step structure and optimize handoff timing',
  }
}

export function calculateEfficiency(executionData = {}) {
  const performance = analyzePerformance(executionData)
  const baseScore = performance.processEfficiency.score
  const optimizedScore = Math.min(100, baseScore + 8)

  return {
    before: baseScore,
    after: optimizedScore,
    gain: optimizedScore - baseScore,
    gainRate: baseScore ? (optimizedScore - baseScore) / baseScore : 0,
  }
}

export function optimizeProcess(executionData = {}) {
  return {
    optimizationMode: 'ON',
    processOptimization: 'ACTIVE',
    optimizedFlow: reduceSteps(executionData),
    efficiencyGain: calculateEfficiency(executionData),
    bottlenecks: detectBottlenecks(executionData),
  }
}
