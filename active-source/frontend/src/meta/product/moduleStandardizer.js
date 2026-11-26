import { ApiContract } from '../core/apiContract.js'
import { getPermissionSnapshot, canPerformAction } from '../runtime/permissionEngine.js'
import { runReviewControlLoop } from '../review/reviewControlEngine.js'
import { getExecutionStatus } from '../ai/executionEngine.js'
import { stateManager } from '../runtime/stateManager.js'
import { lockSystem } from '../freeze/systemLockManager.js'
import { createDeliveryMeta, getDeploymentEnvironment } from './productDelivery.js'

const deploymentProfiles = {
  dev: {
    debugHooks: true,
    frozenRuntimeOnly: false,
    apiStrictMode: true,
  },
  staging: {
    debugHooks: true,
    frozenRuntimeOnly: true,
    apiStrictMode: true,
  },
  production: {
    debugHooks: false,
    frozenRuntimeOnly: true,
    apiStrictMode: true,
  },
}

function resolveModuleName(schema = {}) {
  return schema.name || schema.meta?.module || schema.api?.module || 'unknownModule'
}

export function formatApiResponse(data, meta = {}) {
  return {
    success: true,
    data,
    error: null,
    meta: createDeliveryMeta(meta.module || 'system'),
  }
}

export function formatApiError(error, meta = {}) {
  return {
    success: false,
    data: null,
    error: error?.message || String(error || 'UNKNOWN_ERROR'),
    meta: createDeliveryMeta(meta.module || 'system'),
  }
}

export function buildApiContract(schema = {}) {
  const module = schema.api?.module || resolveModuleName(schema)
  const contract = ApiContract[module] || {}

  return {
    module,
    requestFormat: {
      tenantId: 'string',
      role: 'string',
      plan: 'string',
      params: 'object',
      payload: 'object',
    },
    responseFormat: {
      success: 'boolean',
      data: 'any',
      error: 'string|null',
      meta: 'object',
    },
    errorFormat: {
      success: false,
      data: null,
      error: 'string',
      meta: {},
    },
    endpoints: {
      list: contract.list || null,
      detail: contract.detail || null,
      create: contract.create || null,
      update: contract.update || null,
      delete: contract.delete || null,
    },
    stable: Boolean(contract.list && contract.detail),
  }
}

export function buildUIContract(schema = {}) {
  const columns = schema.ui?.list?.columns || []
  const actions = schema.ui?.list?.actions || []

  return {
    pageType: schema.pageType || 'list',
    columns: columns.map((column) => ({
      key: column.key || column.prop || column.field,
      label: column.label || column.key,
      sortable: column.sortable === true,
      filter: column.filter || false,
      filterType: column.filterType || (typeof column.filter === 'string' ? column.filter : null),
    })),
    actions: actions.map((action) => ({
      key: action.key || action.action || action.event,
      type: action.type || 'event',
      workflowAction: action.workflowAction || null,
    })),
    generatedBySchema: true,
  }
}

export function buildWorkflowContract(schema = {}) {
  const workflow = schema.workflow || {}
  const states = workflow.states || []
  const transitions = workflow.transitions || []
  const actions = workflow.actions || {}

  return {
    stateField: workflow.stateField || 'workflow_state',
    states,
    transitions,
    actions,
    standalone: states.length > 0 && transitions.length > 0,
    maxDepth: Math.max(1, transitions.length),
  }
}

export function buildPermissionContract(schema = {}, runtimeState = stateManager.snapshot()) {
  const moduleName = resolveModuleName(schema)
  const review = runReviewControlLoop(schema)
  const permission = getPermissionSnapshot(runtimeState)
  const execution = getExecutionStatus()

  return {
    module: moduleName,
    unifiedPermissionModel: {
      reviewControlMode: review.controlMode,
      role: runtimeState.role,
      plan: runtimeState.plan,
      tenant: runtimeState.tenant?.id,
      dataScope: permission.dataScope,
      allowedActions: permission.actions,
      canExecute: canPerformAction(runtimeState.role, 'EXECUTE') && review.controlMode !== 'BLOCKED',
      executionStatus: execution.status || 'IDLE',
      blockedRule: 'HARD_STOP',
      restrictedRule: 'HUMAN_GATE_ONLY',
      autoRule: 'POLICY_CONTROLLED',
    },
  }
}

export function buildDeploymentContract(environment = 'production') {
  const profile = deploymentProfiles[environment] || deploymentProfiles.production
  const deliveryEnvironment = getDeploymentEnvironment(environment)

  return {
    environment,
    deliveryEnvironment,
    profiles: deploymentProfiles,
    activeProfile: profile,
    productionReady: environment === 'production' ? profile.frozenRuntimeOnly && !profile.debugHooks : true,
    rule: environment === 'production'
      ? 'production = frozen runtime only; no AI debug hooks'
      : 'non-production may expose debug hooks',
  }
}

export function bundleModule(standardizedModule = {}) {
  return {
    moduleName: standardizedModule.moduleName,
    schemaPack: standardizedModule.schema,
    apiPack: standardizedModule.api,
    workflowPack: standardizedModule.workflow,
    uiPack: standardizedModule.ui,
    permissionPack: standardizedModule.permission,
    deploymentPack: standardizedModule.deployment,
    bundleFormat: 'PROFITOS_SAAS_MODULE_PACK',
  }
}

export function standardizeModule(schema = {}, options = {}) {
  const moduleName = resolveModuleName(schema)
  const deployment = buildDeploymentContract(options.environment || 'production')
  const freeze = lockSystem(options.convergence || {})
  const permissions = buildPermissionContract(schema, options.runtimeState || stateManager.snapshot())
  const standardized = {
    mode: 'V14_MODULE_STANDARDIZATION',
    moduleName,
    schema,
    api: buildApiContract(schema),
    ui: buildUIContract(schema),
    workflow: buildWorkflowContract(schema),
    permissions,
    permission: permissions,
    dataModel: schema.dataModel || schema.model || schema.fields || {},
    deployment,
    freeze,
  }

  return {
    ...standardized,
    package: bundleModule(standardized),
    compliance: {
      apiStable: standardized.api.stable,
      workflowStandalone: standardized.workflow.standalone,
      permissionUnified: true,
      productionFrozen: deployment.activeProfile.frozenRuntimeOnly && freeze.status === 'FROZEN',
      debugHooksDisabledInProduction: deployment.environment !== 'production' || deployment.activeProfile.debugHooks === false,
    },
  }
}

export function standardizeModules(schemas = [], options = {}) {
  const modules = schemas.map((schema) => standardizeModule(schema, options))
  const compliant = modules.filter((module) =>
    module.compliance.apiStable
    && module.compliance.permissionUnified
    && module.compliance.productionFrozen
    && module.compliance.debugHooksDisabledInProduction
  )

  return {
    mode: 'V14_PRODUCT_MODULE_PACK',
    modules,
    readinessScore: modules.length === 0 ? 100 : Math.round((compliant.length / modules.length) * 100),
    moduleComplianceIndex: modules.length === 0 ? 1 : compliant.length / modules.length,
    apiStabilityMeter: modules.length === 0 ? 1 : modules.filter((module) => module.api.stable).length / modules.length,
  }
}
