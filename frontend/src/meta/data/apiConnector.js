import axios from 'axios'
import { adaptResponse } from '../core/apiAdapter.js'
import { recordLatency, recordModuleHealth, recordFailure } from '../saas/monitoring/productionMonitor.js'
import { enforceTenantFilter } from './tenantIsolationLayer.js'

const apiEvents = []
const httpClient = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 15000,
  validateStatus: () => true,
})

function normalizeAction(action = 'list') {
  if (action === 'detail') return 'detail'
  if (action === 'execute') return 'execute'
  return action || 'list'
}

function createApiFallback(module, action, status = 404) {
  return {
    success: false,
    data: [],
    error: status === 404 ? 'API_NOT_FOUND' : `HTTP_${status}`,
    meta: {
      module,
      action,
      timestamp: Date.now(),
      source: 'real-api',
      fallback: true,
      status,
    },
  }
}

export async function fetchRealData(module, action, params = {}) {
  const start = Date.now()
  const safeAction = normalizeAction(action)
  const tenantParams = enforceTenantFilter(params)

  try {
    const response = await httpClient.request({
      url: `/api/execution/${module}/${safeAction}`,
      method: 'GET',
      params: tenantParams,
    })
    const adapted = response.status >= 400
      ? createApiFallback(module, safeAction, response.status)
      : adaptResponse(response.data)
    const latency = Date.now() - start

    apiEvents.unshift({
      module,
      action: safeAction,
      tenantId: tenantParams.tenantId,
      status: adapted?.success === false ? 'ERROR' : 'SUCCESS',
      latency,
      timestamp: Date.now(),
    })
    if (apiEvents.length > 100) apiEvents.length = 100
    recordLatency({ tenantId: tenantParams.tenantId, module, action: safeAction, latency })
    recordModuleHealth({
      tenantId: tenantParams.tenantId,
      module,
      status: adapted?.success === false ? 'UNHEALTHY' : 'HEALTHY',
    })

    return adapted
  } catch (error) {
    const latency = Date.now() - start
    apiEvents.unshift({
      module,
      action: safeAction,
      tenantId: tenantParams.tenantId,
      status: 'ERROR',
      latency,
      message: error?.message || String(error),
      timestamp: Date.now(),
    })
    if (apiEvents.length > 100) apiEvents.length = 100
    recordFailure({
      tenantId: tenantParams.tenantId,
      module,
      action: safeAction,
      message: error?.message || String(error),
    })
    return {
      success: false,
      data: [],
      error: error?.response?.status === 404 ? 'API_NOT_FOUND' : error?.message || String(error),
      meta: {
        module,
        action: safeAction,
        timestamp: Date.now(),
        source: 'real-api',
        fallback: true,
      },
    }
  }
}

export function getApiConnectorSnapshot() {
  const latencySamples = apiEvents.filter((event) => Number.isFinite(event.latency))
  const averageLatency = latencySamples.length
    ? latencySamples.reduce((sum, event) => sum + event.latency, 0) / latencySamples.length
    : 0

  return {
    apiConnector: 'ACTIVE',
    realApiMode: 'ON',
    events: [...apiEvents],
    metrics: {
      apiLatency: Number(averageLatency.toFixed(2)),
      successCount: apiEvents.filter((event) => event.status === 'SUCCESS').length,
      errorCount: apiEvents.filter((event) => event.status === 'ERROR').length,
    },
  }
}
