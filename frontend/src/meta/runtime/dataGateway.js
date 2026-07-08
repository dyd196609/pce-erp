import request from '../../api/request.js'
import { adaptResponse } from '../core/apiAdapter.js'
import { resolveAPI, resolveApi } from '../core/apiResolver.js'
import { recordEvent } from '../core/monitoringLayer.js'
import { canPerformAction, getDataScope } from './permissionEngine.js'
import { stateManager } from './stateManager.js'
import { recordUsage } from '../saas/billing/billingEngine.js'
import { recordQuotaUsage } from '../saas/quota/quotaManager.js'
import {
  recordFailure,
  recordLatency,
  recordModuleHealth,
  recordTenantLoad,
} from '../saas/monitoring/productionMonitor.js'
import { canRunModule } from '../saas/ops/opsControlCenter.js'
import { recordActivation, activationSteps } from '../growth/activationEngine.js'
import { recordRetentionActivity } from '../growth/retentionEngine.js'
import { createUIState } from '../ui/uiStateManager.js'
import { financeModel } from '../data/models/financeModel.js'
import { crmModel } from '../data/models/crmModel.js'
import { scmModel } from '../data/models/scmModel.js'
import { inventoryModel } from '../data/models/inventoryModel.js'
import { purchaseModel } from '../data/models/purchaseModel.js'
import { executeWorkflow } from '../workflow/businessWorkflowEngine.js'
import { propagateStateTransition } from '../orchestration/autoWorkflowConnector.js'
import { readDatabase, seedDatabase } from '../data/databaseLayer.js'
import { bindExecutionData } from '../data/executionDataBinder.js'
import { syncWorkflowWithDB } from '../data/syncEngine.js'
import { runBusinessTransaction } from './businessRuntimeEngine.js'

const enterpriseModels = {
  finance: financeModel,
  crm: crmModel,
  scm: scmModel,
  inventory: inventoryModel,
  purchaseOrder: purchaseModel,
  purchase: purchaseModel,
  purchaseOrderDetail: purchaseModel,
}

function getContext() {
  const state = stateManager.snapshot()

  return {
    tenantId: state.tenant.id,
    role: state.role,
    plan: state.plan,
    dataScope: getDataScope(state.tenant),
    demoMode: state.session.demoMode,
  }
}

function withContext(payload = {}) {
  return {
    ...payload,
    ...getContext(),
  }
}

function normalizeList(res) {
  const data = res?.data ?? res

  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  if (Array.isArray(data?.list)) return data.list
  if (Array.isArray(data?.data)) return data.data

  return []
}

function responseEnvelope(module, data, success = true, error = null) {
  return {
    success,
    data,
    error,
    meta: {
      module,
      timestamp: Date.now(),
    },
  }
}

function normalizeEnvelope(module, response, fallbackData) {
  if (response?.success !== undefined && response?.meta?.module && response?.meta?.timestamp) {
    return response
  }

  return responseEnvelope(module, response?.data ?? response ?? fallbackData)
}

function getEnterpriseModel(module) {
  return enterpriseModels[module] || null
}

function resolveGateway(path, params = {}) {
  return resolveAPI(path, withContext(params))
}

function shouldUseGateway(res) {
  return res?.success === true && ['execution-gateway'].includes(res?.meta?.source)
}

function fallbackList(module, error) {
  const context = getContext()

  recordFailure({
    tenantId: context.tenantId,
    module,
    action: 'list',
    message: error?.message || String(error),
  })

  recordEvent({
    type: 'DATA_GATEWAY_FALLBACK',
    module,
    action: 'list',
    tenantId: context.tenantId,
    message: error?.message || String(error),
  })

  const enterpriseModel = getEnterpriseModel(module)
  if (enterpriseModel) {
    return enterpriseModel.list().data
  }

  return []
}

function fallbackDetail(module, id, error) {
  const context = getContext()

  recordFailure({
    tenantId: context.tenantId,
    module,
    action: 'detail',
    message: error?.message || String(error),
  })

  recordEvent({
    type: 'DATA_GATEWAY_FALLBACK',
    module,
    action: 'detail',
    tenantId: context.tenantId,
    message: error?.message || String(error),
  })

  const enterpriseModel = getEnterpriseModel(module)
  if (enterpriseModel) {
    return enterpriseModel.detail(id).data
  }

  return null
}

async function send(config) {
  const raw = await request(config)
  return adaptResponse(raw)
}

function isFallbackNotFound(response) {
  return response?.success === false && response?.error === 'API_NOT_FOUND'
}

function apiFallbackEnvelope(module, response) {
  return {
    success: false,
    data: Array.isArray(response?.data) ? response.data : [],
    error: 'API_NOT_FOUND',
    meta: {
      module,
      timestamp: Date.now(),
      source: response?.meta?.source || 'real-api',
      fallback: true,
    },
  }
}

async function list(module, params = {}) {
  const context = getContext()
  const start = Date.now()

  recordUsage({ tenantId: context.tenantId, module, type: 'api', units: 1 })
  recordQuotaUsage(context, 'apiCalls', 1)
  recordTenantLoad({ tenantId: context.tenantId, module, action: 'list' })
  recordActivation({ tenantId: context.tenantId, module, step: activationSteps.FIRST_MODULE_USAGE })
  recordRetentionActivity({ tenantId: context.tenantId, module, workflow: 'list' })

  const ops = canRunModule(context.tenantId, module)
  if (!ops.allowed) {
    recordFailure({
      tenantId: context.tenantId,
      module,
      action: 'list',
      message: 'OPS_MODULE_BLOCKED',
    })
    return responseEnvelope(module, [], false, 'OPS_MODULE_BLOCKED')
  }

  const enterpriseModel = getEnterpriseModel(module)
  if (enterpriseModel) {
    seedDatabase(module, enterpriseModel.list(params).data || [], context)
    const rows = await readDatabase(module, 'list', {
      ...params,
      tenantId: context.tenantId,
    })
    recordLatency({ tenantId: context.tenantId, module, action: 'list', latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })
    return responseEnvelope(module, rows)
  }

  const gatewayRes = resolveGateway(resolveApi(module, 'list'), params)
  if (shouldUseGateway(gatewayRes)) {
    const rows = normalizeList(gatewayRes)
    recordEvent({
      type: 'DATA_GATEWAY_EXECUTION_GATEWAY',
      module,
      tenantId: context.tenantId,
      rows: rows.length,
      source: gatewayRes.meta.source,
    })
    recordLatency({ tenantId: context.tenantId, module, action: 'list', latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })
    return responseEnvelope(module, rows)
  }

  try {
    const res = await send({
      url: resolveApi(module, 'list'),
      method: 'GET',
      params: withContext(params),
    })

    if (isFallbackNotFound(res)) {
      return apiFallbackEnvelope(module, res)
    }

    const rows = normalizeList(res)

    recordEvent({
      type: 'DATA_GATEWAY_LIST',
      module,
      tenantId: getContext().tenantId,
      rows: rows.length,
    })
    recordLatency({ tenantId: context.tenantId, module, action: 'list', latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })

    return responseEnvelope(module, rows)
  } catch (error) {
    return responseEnvelope(module, fallbackList(module, error))
  }
}

async function detail(module, id) {
  const context = getContext()
  const start = Date.now()

  recordUsage({ tenantId: context.tenantId, module, type: 'api', units: 1 })
  recordQuotaUsage(context, 'apiCalls', 1)
  recordTenantLoad({ tenantId: context.tenantId, module, action: 'detail' })
  recordActivation({ tenantId: context.tenantId, module, step: activationSteps.FIRST_MODULE_USAGE })
  recordRetentionActivity({ tenantId: context.tenantId, module, workflow: 'detail' })

  const ops = canRunModule(context.tenantId, module)
  if (!ops.allowed) {
    recordFailure({
      tenantId: context.tenantId,
      module,
      action: 'detail',
      message: 'OPS_MODULE_BLOCKED',
    })
    return responseEnvelope(module, null, false, 'OPS_MODULE_BLOCKED')
  }

  const enterpriseModel = getEnterpriseModel(module)
  if (enterpriseModel) {
    seedDatabase(module, enterpriseModel.list().data || [], context)
    const row = await readDatabase(module, 'detail', {
      id,
      tenantId: context.tenantId,
    })
    recordLatency({ tenantId: context.tenantId, module, action: 'detail', latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })
    return responseEnvelope(module, row)
  }

  const gatewayRes = resolveGateway(resolveApi(module, 'detail', { id }), { id })
  if (shouldUseGateway(gatewayRes)) {
    recordEvent({
      type: 'DATA_GATEWAY_EXECUTION_GATEWAY',
      module,
      action: 'detail',
      tenantId: context.tenantId,
      source: gatewayRes.meta.source,
    })
    recordLatency({ tenantId: context.tenantId, module, action: 'detail', latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })
    return responseEnvelope(module, gatewayRes.data ?? null)
  }

  try {
    const res = await send({
      url: resolveApi(module, 'detail', { id }),
      method: 'GET',
      params: withContext(),
    })

    if (isFallbackNotFound(res)) {
      return {
        ...apiFallbackEnvelope(module, res),
        data: null,
      }
    }

    recordLatency({ tenantId: context.tenantId, module, action: 'detail', latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })

    return responseEnvelope(module, res.data ?? res)
  } catch (error) {
    return responseEnvelope(module, fallbackDetail(module, id, error))
  }
}

async function execute(action, payload = {}) {
  const context = getContext()
  const permission = payload.permission || 'EXECUTE'
  const module = payload.module || 'runtime'
  const start = Date.now()

  recordUsage({ tenantId: context.tenantId, module, type: 'execution', units: 1 })
  recordQuotaUsage(context, 'workflowExecutions', 1)
  recordTenantLoad({ tenantId: context.tenantId, module, action })
  recordActivation({ tenantId: context.tenantId, module, step: activationSteps.FIRST_WORKFLOW_EXECUTION })
  recordRetentionActivity({ tenantId: context.tenantId, module, workflow: action })

  const ops = canRunModule(context.tenantId, module)
  if (!ops.allowed) {
    recordFailure({
      tenantId: context.tenantId,
      module,
      action,
      message: 'OPS_MODULE_BLOCKED',
    })
    return responseEnvelope(module, { action, module, ops }, false, 'OPS_MODULE_BLOCKED')
  }

  if (!canPerformAction(context.role, permission)) {
    return responseEnvelope(module, { action, role: context.role }, false, 'ROLE_ACTION_DENIED')
  }

  const enterpriseModel = getEnterpriseModel(module)
  if (enterpriseModel) {
    const currentRecord = payload.id || payload.data?.id
      ? enterpriseModel.detail(payload.id || payload.data?.id).data
      : payload.data || payload
    const workflow = executeWorkflow(module, action, {
      record: currentRecord || {},
      payload: payload.data || payload,
      role: context.role,
      user: {
        role: context.role,
        tenantId: context.tenantId,
      },
    })

    if (workflow.result?.executed === false) {
      return responseEnvelope(module, workflow, false, workflow.result.message || 'WORKFLOW_BLOCKED')
    }

    const workflowPayload = {
      ...payload,
      data: {
        ...(payload.data || {}),
        ...(workflow.result?.record || {}),
      },
    }

    recordLatency({ tenantId: context.tenantId, module, action, latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })
    const result = normalizeEnvelope(module, enterpriseModel.execute(action, workflowPayload), null)
    const dataBinding = bindExecutionData(module, result.data, {
      tenantId: context.tenantId,
      action,
      record: result.data,
    })
    const workflowSync = syncWorkflowWithDB(module, workflow, {
      tenantId: context.tenantId,
      record: result.data,
    })
    const orchestration = propagateStateTransition(module, action, result.data, workflow)
    const businessRuntime = runBusinessTransaction({
      type: module === 'purchase' || module === 'purchaseOrder' ? 'purchase.approved' : `${module}.${action}`,
      module,
      action,
      payload: {
        module,
        action,
        record: result.data,
      },
    }, {
      tenantId: context.tenantId,
      role: context.role,
      module,
      action,
    })
    return responseEnvelope(module, {
      record: result.data,
      workflow,
      dataBinding,
      workflowSync,
      orchestration,
      businessRuntime,
    }, result.success !== false, result.error)
  }

  if (!payload.module || !payload.apiAction) {
    recordLatency({ tenantId: context.tenantId, module, action, latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })
    return responseEnvelope(module, {
      mode: 'ENTERPRISE_EXECUTION_ACK',
      action,
      context,
      payload,
    })
  }

  const gatewayRes = resolveGateway(resolveApi(payload.module, payload.apiAction, payload.params || {}), {
    ...(payload.params || {}),
    payload: payload.data || payload,
  })
  if (shouldUseGateway(gatewayRes)) {
    recordLatency({ tenantId: context.tenantId, module, action, latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })
    return gatewayRes
  }

  try {
    const res = await send({
      url: resolveApi(payload.module, payload.apiAction, payload.params || {}),
      method: payload.method || 'POST',
      data: withContext(payload.data || {}),
    })

    if (isFallbackNotFound(res)) {
      return apiFallbackEnvelope(module, res)
    }

    recordLatency({ tenantId: context.tenantId, module, action, latency: Date.now() - start })
    recordModuleHealth({ tenantId: context.tenantId, module, status: 'HEALTHY' })

    return responseEnvelope(module, res.data ?? res)
  } catch (error) {
    recordFailure({
      tenantId: context.tenantId,
      module,
      action,
      message: error?.message || String(error),
    })
    return responseEnvelope(module, null, false, error?.message || String(error))
  }
}

export const dataGateway = {
  list,
  detail,
  execute,
  async listState(module, params = {}) {
    try {
      const result = await list(module, params)
      return createUIState({
        loading: false,
        error: result?.success === false ? result.error || 'LIST_FAILED' : null,
        data: Array.isArray(result?.data) ? result.data : [],
      })
    } catch (error) {
      return createUIState({
        loading: false,
        error: error?.message || String(error),
        data: [],
      })
    }
  },
  async detailState(module, id) {
    try {
      const result = await detail(module, id)
      return createUIState({
        loading: false,
        error: result?.success === false ? result.error || 'DETAIL_FAILED' : null,
        data: result?.data ?? null,
      })
    } catch (error) {
      return createUIState({
        loading: false,
        error: error?.message || String(error),
        data: null,
      })
    }
  },
  async executeState(action, payload = {}) {
    try {
      const data = await execute(action, payload)
      return createUIState({
        loading: false,
        error: data?.success === false ? data.error || 'EXECUTION_FAILED' : null,
        data,
      })
    } catch (error) {
      return createUIState({
        loading: false,
        error: error?.message || String(error),
        data: null,
      })
    }
  },
}
