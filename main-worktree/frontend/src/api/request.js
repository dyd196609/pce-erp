import axios from 'axios'
import { createStandardApiError, createStandardApiResponse } from '@/meta/product/productDelivery'
import {
  assertPceFactLoadFacts,
  createReadFailedFactLoad,
  currentPceServerFactContext,
  rememberPceServerFactContext,
} from '@/meta/runtime/pceFactLoadContract'
import { isUsableServerJwt } from '@/meta/runtime/latestBaseDataProviderState.js'
import {
  authenticationContextChanged,
  getTabAuthEpoch,
  getTabAuthToken,
} from '@/meta/runtime/tabAuthenticationContext.js'

// =====================
// V3.8 unified API exit
// =====================

const instance = axios.create({
  // Keep browser requests same-origin by default so HttpOnly workflow
  // authority cookies survive localhost/127.0.0.1 development routing.
  // Deployments with a dedicated API origin must opt in explicitly.
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 15000,
  withCredentials: true,
  withXSRFToken: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  validateStatus: () => true,
})

export function getAuthenticationHeaders() {
  const token = getTabAuthToken()
  return isUsableServerJwt(token) ? { Authorization: `Bearer ${token}` } : {}
}

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

function serverFactLoadFacts(payload) {
  return payload?.factLoadFacts
    || payload?.data?.factLoadFacts
    || null
}

function validatedServerFailureFacts(payload, config, status) {
  const serverFacts = serverFactLoadFacts(payload)
  if (!serverFacts) return null
  try {
    const facts = assertPceFactLoadFacts(
      serverFacts,
      'api-error-response',
      config?.url || '',
    )
    return facts.factLoadStatus === 'read_failed' ? facts : null
  } catch {
    return createReadFailedFactLoad({
      apiUrl: serverFacts.apiUrl || config?.url,
      httpStatus: serverFacts.httpStatus || status,
      errorCode: 'FACT_LOAD_CONTRACT_INCOMPLETE',
      errorMessage: 'Server error response violated PCE-FACT-LOAD-CONTRACT-V1.0',
      loadedAt: serverFacts.loadedAt,
      tenantId: serverFacts.tenantId,
      batchId: serverFacts.batchId,
    })
  }
}

function createHttpFailure(res) {
  const factLoadFacts = validatedServerFailureFacts(
    res.data,
    res.config,
    res.status,
  ) || createReadFailedFactLoad({
    apiUrl: res.config?.url,
    httpStatus: res.status,
    errorCode:
      res.data?.error?.code
      || res.data?.code
      || res.data?.errorCode
      || (res.status === 404 ? 'API_NOT_FOUND' : `HTTP_${res.status}`),
    errorMessage:
      res.data?.error?.message
      || res.data?.errorMessage
      || res.data?.message
      || `HTTP ${res.status} while reading ${res.config?.url || ''}`,
    ...currentPceServerFactContext(),
  })
  return {
    success: false,
    data: null,
    error: {
      code: factLoadFacts.errorCode,
      message: factLoadFacts.errorMessage,
      details:
        res.data?.error?.details
        || res.data?.details
        || {},
    },
    ...factLoadFacts,
    factLoadFacts,
    meta: {
      module: resolveModule(res.config),
      timestamp: new Date().toISOString(),
      source: 'real-api',
      status: res.status,
    },
  }
}

function rememberResponseContext(payload) {
  const facts = serverFactLoadFacts(payload)
  if (!facts) return
  try {
    rememberPceServerFactContext(
      assertPceFactLoadFacts(facts, 'api-success-response'),
    )
  } catch {
    // Contract consumers will surface the incomplete server payload.
  }
}

// Request interceptor
instance.interceptors.request.use((config) => {
  const authenticationHeaders = getAuthenticationHeaders()
  config.headers = config.headers || {}
  config.meta = { ...(config.meta || {}), tabAuthEpoch: getTabAuthEpoch() }
  Object.entries(authenticationHeaders).forEach(([name, value]) => {
    if (!config.headers[name]) config.headers[name] = value
  })
  const method = String(config.method || 'get').toLowerCase()
  if (!['get', 'head', 'options', 'trace'].includes(method)
    && !config.headers['X-CSRFToken'] && typeof document !== 'undefined') {
    const token = document.cookie.split(';').map(value => value.trim())
      .find(value => value.startsWith('csrftoken='))?.slice('csrftoken='.length)
    if (token) config.headers['X-CSRFToken'] = decodeURIComponent(token)
  }
  return config
})

// Response interceptor
instance.interceptors.response.use(
  (res) => {
    if (authenticationContextChanged(res.config?.meta?.tabAuthEpoch)) {
      return {
        success: false,
        data: null,
        error: {
          code: 'AUTHENTICATION_CONTEXT_CHANGED',
          message: '标签页登录身份已变化，已丢弃旧身份响应。',
        },
        meta: {
          module: resolveModule(res.config),
          source: 'tab-auth-context',
          timestamp: new Date().toISOString(),
          status: res.status,
        },
      }
    }
    if (res.status >= 400) {
      return createHttpFailure(res)
    }

    rememberResponseContext(res.data)
    if (isStandardEnvelope(res.data)) {
      return {
        ...res.data,
        meta: {
          module: res.data.meta.module || resolveModule(res.config),
          timestamp: res.data.meta.timestamp || new Date().toISOString(),
          status: res.status,
        },
      }
    }

    const response = createStandardApiResponse(res.data, {
      module: resolveModule(res.config),
    })
    return {
      ...response,
      meta: {
        ...response.meta,
        status: res.status,
      },
    }
  },
  (err) => {
    const standardError = createStandardApiError(err, {
      module: resolveModule(err.config),
      source: 'real-api',
      fallback: true,
    })
    const factLoadFacts = createReadFailedFactLoad({
      apiUrl: err.config?.url,
      httpStatus: err.response?.status || 0,
      errorCode: err.code || 'NETWORK_READ_FAILED',
      errorMessage: err.message || 'Network fact read failed',
      ...currentPceServerFactContext(),
    })
    return Promise.resolve({
      ...standardError,
      success: false,
      data: null,
      error: {
        code: factLoadFacts.errorCode,
        message: factLoadFacts.errorMessage,
      },
      ...factLoadFacts,
      factLoadFacts,
    })
  }
)

export default function request(config) {
  return instance({
    method: config.method || 'GET',
    url: config.url,
    data: config.data,
    params: config.params,
    headers: config.headers,
    ...(config.timeout !== undefined ? { timeout: config.timeout } : {}),
    withCredentials: config.withCredentials ?? true,
    responseType: config.responseType,
    meta: config.meta,
  })
}
