import { recordEvent } from '../core/monitoringLayer.js'

function getOptimizationTarget(module) {
  const targetMap = {
    ERP: 'master-data-validation',
    MES: 'execution-trace-path',
    SCM: 'purchase-supply-path',
    WMS: 'inventory-sync-path',
    CRM: 'customer-profit-path',
    BI: 'analytics-refresh-path',
    ProfitOS: 'decision-feedback-path',
  }

  return targetMap[module] || 'general-runtime-path'
}

export function adjustWorkflowAutomatically(moduleCompliance = []) {
  const workflowAdjustments = moduleCompliance
    .filter((module) => module.complianceRate < 0.6)
    .map((module) => ({
      module: module.module,
      action: 'WORKFLOW_REVIEW_MODE',
      target: getOptimizationTarget(module.module),
      reason: 'module compliance below optimization threshold',
    }))

  return {
    mode: 'AUTO_WORKFLOW_OPTIMIZATION',
    workflowAdjustments,
  }
}

export function optimizeModuleExecutionPath(moduleCompliance = []) {
  const executionPaths = moduleCompliance.map((module) => ({
    module: module.module,
    path: module.complianceRate < 0.5 ? 'SAFE_EXECUTION_PATH' : 'STANDARD_EXECUTION_PATH',
    restricted: module.complianceRate < 0.5,
  }))

  return {
    mode: 'MODULE_EXECUTION_PATH_OPTIMIZATION',
    executionPaths,
  }
}

export function rebalanceSystemLoad(systemScores = {}) {
  const loadMode = systemScores.executionIntegrityScore < 60
    ? 'PROTECTED_LOAD'
    : 'NORMAL_LOAD'

  return {
    mode: 'SYSTEM_LOAD_REBALANCE',
    loadMode,
    resourcePolicy: loadMode === 'PROTECTED_LOAD'
      ? 'prioritize decision and review workloads'
      : 'standard resource allocation',
  }
}

export function runAutoOptimization(reviewStatus) {
  const workflow = adjustWorkflowAutomatically(reviewStatus.moduleCompliance)
  const execution = optimizeModuleExecutionPath(reviewStatus.moduleCompliance)
  const load = rebalanceSystemLoad(reviewStatus.systemScores)

  recordEvent({
    type: 'REVIEW_AUTO_OPTIMIZATION',
    module: 'review',
    status: load.loadMode,
    adjustments: workflow.workflowAdjustments.length,
  })

  return {
    mode: 'V12.5_AUTO_OPTIMIZATION',
    workflow,
    execution,
    load,
  }
}

export function optimizePage(schema = {}) {
  const columns = schema?.ui?.list?.columns || []
  const actions = schema?.ui?.list?.actions || []
  const hasWideTable = columns.length > 8

  return {
    mode: 'V12.5_PAGE_AUTO_OPTIMIZATION',
    schemaName: schema?.name || schema?.meta?.module || 'unknown',
    optimization: {
      autoReorderColumns: hasWideTable,
      autoReduceLoad: hasWideTable,
      autoRouteOptimization: actions.some((action) => action?.type === 'route'),
    },
    columns: hasWideTable
      ? [
          ...columns.filter((column) => column.type === 'index'),
          ...columns.filter((column) => column.type !== 'index'),
        ]
      : columns,
    actions,
  }
}
