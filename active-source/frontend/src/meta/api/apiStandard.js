import {
  API_RESPONSE_STANDARD,
  createStandardApiError,
  createStandardApiResponse,
} from '../product/productDelivery.js'

export const ApiStandard = {
  responseFormat: API_RESPONSE_STANDARD,
  core: {
    namespace: '/api/core',
    routes: {
      run: '/api/core/run',
      health: '/api/core/health',
      modules: '/api/core/modules',
    },
  },
  profit: {
    namespace: '/api/profit',
    routes: {
      run: '/api/profit/run',
      decision: '/api/profit/decision',
      matrix: '/api/profit/matrix',
    },
  },
  execution: {
    namespace: '/api/execution',
    routes: {
      run: '/api/execution/run',
      erp: '/api/execution/erp',
      mes: '/api/execution/mes',
      scm: '/api/execution/scm',
      wms: '/api/execution/wms',
    },
  },
}

export function createApiResponse(data = null, meta = {}) {
  return createStandardApiResponse(data, meta)
}

export function createApiError(error, meta = {}) {
  return createStandardApiError(error, meta)
}

export function resolveApiStandard(layer, action) {
  const route = ApiStandard[layer]?.routes?.[action]

  if (!route) {
    throw new Error(`[API STANDARD] Missing route: ${layer}.${action}`)
  }

  return route
}

export function listApiStandards() {
  return ApiStandard
}
