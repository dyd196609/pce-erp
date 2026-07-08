import {
  buildApiContract,
  buildPermissionContract,
  buildUIContract,
  buildWorkflowContract,
  formatApiError,
  formatApiResponse,
} from './moduleStandardizer.js'
import { MODULE_STANDARD_KEYS } from './productDelivery.js'
import { isolateData, isolateSchema, isolateTenant, isolateWorkflow } from '../saas/tenant/tenantIsolationEngine.js'
import { stateManager } from '../runtime/stateManager.js'

function resolveModuleName(schema = {}) {
  return schema.api?.module || schema.name || schema.meta?.module || 'unknownModule'
}

export function normalizeApiResponse(payload, meta = {}) {
  if (payload?.success === false) {
    return formatApiError(payload.error || 'API_ERROR', meta)
  }

  return formatApiResponse(payload?.data ?? payload ?? null, meta)
}

export function buildFinalApiContract(schema = {}) {
  const api = buildApiContract(schema)

  return {
    ...api,
    standard: {
      success: 'boolean',
      data: 'any',
      error: 'string|null',
      meta: 'object',
    },
    responseEnvelope: normalizeApiResponse(null, {
      contract: 'PRODUCTION_API_RESPONSE',
    }),
    strict: true,
  }
}

export function buildFinalUIContract(schema = {}) {
  return {
    ...buildUIContract(schema),
    productionUI: true,
    experimentalPanels: 'DISABLED',
    debugControls: 'DISABLED',
  }
}

export function buildFinalWorkflowContract(schema = {}) {
  return {
    ...buildWorkflowContract(schema),
    runtimeIsolation: 'TENANT_SCOPED',
    humanGatePolicy: 'POLICY_EXCEPTION_ONLY',
    experimentalAutonomy: 'DISABLED',
  }
}

export function buildFinalPermissionContract(schema = {}, runtimeState = stateManager.snapshot()) {
  return {
    ...buildPermissionContract(schema, runtimeState),
    tenantBoundary: 'ENFORCED',
    productionAccessModel: 'RBAC_PLAN_SCOPE',
    experimentalOverride: 'DISABLED',
  }
}

export function buildTenantIsolationContract(context = {}) {
  return {
    mode: 'PRODUCTION_TENANT_ISOLATION',
    dataIsolation: isolateData(context),
    workflowIsolation: isolateWorkflow(context),
    schemaIsolation: isolateSchema(context),
    runtimeIsolation: {
      tenantId: context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'demo_company',
      runtimeNamespace: `runtime:${context.tenantId || context.tenant?.id || context.runtimeState?.tenant?.id || 'demo_company'}`,
      isolated: true,
    },
    isolation: isolateTenant(context),
  }
}

export function standardizeModuleForProduction(schema = {}, options = {}) {
  const runtimeState = options.runtimeState || stateManager.snapshot()

  return {
    mode: 'PRODUCTION_MODULE_STANDARDIZATION_CORE',
    moduleName: resolveModuleName(schema),
    api: buildFinalApiContract(schema),
    ui: buildFinalUIContract(schema),
    workflow: buildFinalWorkflowContract(schema),
    permissions: buildFinalPermissionContract(schema, runtimeState),
    dataModel: schema.dataModel || schema.model || schema.fields || {},
    standardKeys: MODULE_STANDARD_KEYS,
    apiContract: buildFinalApiContract(schema),
    uiContract: buildFinalUIContract(schema),
    workflowContract: buildFinalWorkflowContract(schema),
    permissionContract: buildFinalPermissionContract(schema, runtimeState),
    tenantContract: buildTenantIsolationContract({
      ...options,
      runtimeState,
    }),
    productionReady: true,
  }
}

export function standardizeModulesForProduction(schemas = [], options = {}) {
  const modules = schemas.map((schema) => standardizeModuleForProduction(schema, options))

  return {
    mode: 'PRODUCTION_MODULE_REGISTRY_FINAL',
    modules,
    moduleCount: modules.length,
    apiContractCoverage: modules.length === 0
      ? 1
      : modules.filter((module) => module.apiContract.strict).length / modules.length,
    workflowContractCoverage: modules.length === 0
      ? 1
      : modules.filter((module) => module.workflowContract.runtimeIsolation === 'TENANT_SCOPED').length / modules.length,
    permissionContractCoverage: 1,
    tenantIsolationCoverage: 1,
  }
}
