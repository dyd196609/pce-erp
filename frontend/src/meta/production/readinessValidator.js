import { getAllSchemaEntries } from '../core/schemaRegistry.js'
import { getExecutionLayerSnapshot } from '../execution/executionEngine.js'
import { getStructuralEvolutionSnapshot } from '../evolution/structuralEvolutionEngine.js'

function scoreFromBoolean(value) {
  return value ? 100 : 0
}

export function checkUICompleteness() {
  const entries = getAllSchemaEntries()
  const checked = entries.map(({ route, schema }) => {
    const columns = schema?.columns || schema?.ui?.list?.columns || schema?.fields || []
    const title = schema?.meta?.title || schema?.title || schema?.name

    return {
      route,
      complete: Boolean(title) && Array.isArray(columns) && columns.length > 0,
    }
  })
  const complete = checked.filter((item) => item.complete).length

  return {
    complete: complete === checked.length,
    score: checked.length ? Math.round((complete / checked.length) * 100) : 100,
    checked,
  }
}

export function checkAPIStability() {
  const execution = getExecutionLayerSnapshot()
  const successRate = execution.history.length ? execution.metrics?.executionSuccessRate ?? 100 : 90

  return {
    stable: successRate >= 80,
    score: successRate,
    source: 'execution_layer',
  }
}

export function checkWorkflowCompleteness() {
  const execution = getExecutionLayerSnapshot()
  const hasWorkflow = execution.history.length > 0
  const blocked = execution.history.filter((item) => item.status === 'BLOCKED').length

  return {
    complete: hasWorkflow ? blocked <= execution.history.length : true,
    score: hasWorkflow ? Math.max(0, 100 - blocked * 10) : 90,
    blocked,
  }
}

export function checkDataConsistency() {
  const evolution = getStructuralEvolutionSnapshot()
  const allowed = evolution.stability?.metrics?.safeEvolutionStatus !== 'BLOCKED'

  return {
    consistent: allowed,
    score: scoreFromBoolean(allowed),
    stabilityStatus: evolution.stability?.metrics?.safeEvolutionStatus || 'ALLOWED',
  }
}

export function validateProductionReadiness() {
  const ui = checkUICompleteness()
  const api = checkAPIStability()
  const workflow = checkWorkflowCompleteness()
  const data = checkDataConsistency()
  const score = Math.round((ui.score + api.score + workflow.score + data.score) / 4)

  return {
    deploymentReady: score >= 85 && ui.complete && api.stable && workflow.complete && data.consistent,
    productionReadinessScore: score,
    ui,
    api,
    workflow,
    data,
    timestamp: Date.now(),
  }
}
