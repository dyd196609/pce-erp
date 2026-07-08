import axios from 'axios'
import { createStandardApiError, createStandardApiResponse } from '@/meta/product/productDelivery'

// =====================
// V3.8 unified API exit
// =====================

const instance = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 15000,
  validateStatus: () => true,
})

function resolveModule(config = {}) {
  return config.meta?.module
    || String(config.url || '')
      .split('/')
      .filter(Boolean)[1]
    || 'system'
}

function isStandardEnvelope(payload) {
  return payload
    && typeof payload === 'object'
    && typeof payload.success === 'boolean'
    && Object.prototype.hasOwnProperty.call(payload, 'data')
    && Object.prototype.hasOwnProperty.call(payload, 'error')
    && payload.meta
}

function createApiNotFoundFallback(config = {}) {
  return {
    success: false,
    data: [],
    error: 'API_NOT_FOUND',
    meta: {
      module: resolveModule(config),
      timestamp: new Date().toISOString(),
      source: 'real-api',
      fallback: true,
    },
  }
}

function createHttpFallback(res) {
  return {
    success: false,
    data: [],
    error: res.status === 404 ? 'API_NOT_FOUND' : `HTTP_${res.status}`,
    meta: {
      module: resolveModule(res.config),
      timestamp: new Date().toISOString(),
      source: 'real-api',
      fallback: true,
      status: res.status,
    },
  }
}

// Request interceptor
instance.interceptors.request.use((config) => {
  return config
})

// Response interceptor
instance.interceptors.response.use(
  (res) => {
    if (res.status === 404) {
      return createApiNotFoundFallback(res.config)
    }

    if (res.status >= 400) {
      return createHttpFallback(res)
    }

    if (isStandardEnvelope(res.data)) {
      return {
        ...res.data,
        meta: {
          module: res.data.meta.module || resolveModule(res.config),
          timestamp: res.data.meta.timestamp || new Date().toISOString(),
        },
      }
    }

    return createStandardApiResponse(res.data, {
      module: resolveModule(res.config),
    })
  },
  (err) => {
    return Promise.resolve(createStandardApiError(err, {
      module: resolveModule(err.config),
      source: 'real-api',
      fallback: true,
    }))
  }
)

export default function request(config) {
  return instance({
    method: config.method || 'GET',
    url: config.url,
    data: config.data,
    params: config.params,
    meta: config.meta,
  })
}
