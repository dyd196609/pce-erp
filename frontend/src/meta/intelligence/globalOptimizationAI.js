import { optimizeProcess } from '../optimization/processOptimizationEngine.js'
import { optimizeCost } from '../optimization/costOptimizationEngine.js'
import { allocateResources } from '../optimization/resourceAllocationAI.js'
import { optimizeProcessPathDynamically } from './adaptiveProcessEngine.js'
import { optimizeCosts as runCostIntelligence } from './costIntelligenceEngine.js'
import { optimizeResources as runResourceIntelligence } from './resourceIntelligenceAI.js'
import { forecastImprovements } from './predictiveOptimizationEngine.js'

function normalizeContext(context = {}) {
  const executionData = context.executionClosedLoop || context.executionData || context
  const optimizationRuntime = context.optimizationRuntime || {
    process: optimizeProcess(executionData),
    cost: optimizeCost(executionData),
    resources: allocateResources(executionData),
  }

  return {
    ...context,
    executionData,
    optimizationRuntime,
    processOptimization: optimizationRuntime.process,
    costOptimization: optimizationRuntime.cost,
    resourceAllocation: optimizationRuntime.resources,
  }
}

export function optimizeProcesses(context = {}) {
  const normalized = normalizeContext(context)

  return {
    ...normalized.processOptimization,
    adaptiveFlow: optimizeProcessPathDynamically(normalized),
  }
}

export function optimizeCosts(context = {}) {
  const normalized = normalizeContext(context)

  return {
    ...normalized.costOptimization,
    intelligence: optimizeCostsIntelligently(normalized),
  }
}

export function optimizeCostsIntelligently(context = {}) {
  return runCostIntelligence(context)
}

export function optimizeResources(context = {}) {
  const normalized = normalizeContext(context)

  return {
    ...normalized.resourceAllocation,
    intelligence: optimizeResourcesIntelligently(normalized),
  }
}

export function optimizeResourcesIntelligently(context = {}) {
  return runResourceIntelligence(context)
}

export function optimizeEnterprise(context = {}) {
  const normalized = normalizeContext(context)
  const processOptimization = optimizeProcesses(normalized)
  const costOptimization = optimizeCosts(normalized)
  const resourceOptimization = optimizeResources(normalized)
  const predictedImprovements = forecastImprovements(normalized)

  return {
    intelligenceOptimizationMode: 'ON',
    globalOptimizationAI: 'ACTIVE',
    adaptiveProcess: 'ENABLED',
    predictiveOptimization: 'ACTIVE',
    processOptimization,
    costOptimization,
    resourceOptimization,
    predictedImprovements,
    globalPlan: {
      target: 'enterprise_efficiency',
      actions: [
        processOptimization.adaptiveFlow.pathPolicy,
        costOptimization.intelligence.procurementStrategy.strategy,
        resourceOptimization.intelligence.workloadBalancing.policy,
      ],
      expectedEfficiencyScore: predictedImprovements.futurePerformance.forecastScore,
      expectedCostSaving: costOptimization.intelligence.operationalCost.dynamicSaving,
    },
  }
}
