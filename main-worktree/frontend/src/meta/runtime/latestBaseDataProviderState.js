export const LATEST_BASE_DATA_PROVIDER_STATES = Object.freeze({
  LOADING: 'LOADING',
  LOADED_EMPTY: 'LOADED_EMPTY',
  LOADED_WITH_DATA: 'LOADED_WITH_DATA',
  AUTH_FAILED: 'AUTH_FAILED',
  SERVER_CONTEXT_UNAVAILABLE: 'SERVER_CONTEXT_UNAVAILABLE',
  API_FAILED: 'API_FAILED',
  SCHEMA_FAILED: 'SCHEMA_FAILED',
})

const AUTH_ERROR_CODES = new Set([
  'not_authenticated',
  'authentication_failed',
  'token_not_valid',
  'AUTH_REQUIRED',
])

export function isUsableServerJwt(token) {
  try {
    const [, encodedPayload] = String(token || '').split('.')
    if (!encodedPayload) return false
    const normalized = encodedPayload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const payload = JSON.parse(atob(padded))
    return !payload.exp || Number(payload.exp) * 1000 > Date.now() + 5000
  } catch {
    return false
  }
}

export function hasUsableServerAuthentication() {
  return isUsableServerJwt(getTabAuthToken())
}

export function resolveLatestBaseDataProviderState({
  loading = false,
  succeeded = false,
  factLoadFacts = null,
  count = null,
} = {}) {
  if (loading) return LATEST_BASE_DATA_PROVIDER_STATES.LOADING

  const status = String(factLoadFacts?.factLoadStatus || '')
  const errorCode = String(factLoadFacts?.errorCode || '')
  const httpStatus = Number(factLoadFacts?.httpStatus || 0)
  if (status === 'read_failed') {
    if (httpStatus === 401 || httpStatus === 403 || AUTH_ERROR_CODES.has(errorCode)) {
      return LATEST_BASE_DATA_PROVIDER_STATES.AUTH_FAILED
    }
    if (errorCode === 'FACT_LOAD_CONTRACT_INCOMPLETE' || errorCode === 'FACT_API_URL_MISMATCH') {
      return LATEST_BASE_DATA_PROVIDER_STATES.SCHEMA_FAILED
    }
    if (errorCode === 'SERVER_CONTEXT_UNAVAILABLE') {
      return LATEST_BASE_DATA_PROVIDER_STATES.SERVER_CONTEXT_UNAVAILABLE
    }
    return LATEST_BASE_DATA_PROVIDER_STATES.API_FAILED
  }

  const successfulStatus = ['success', 'loaded', 'empty_valid'].includes(status)
  if (succeeded || successfulStatus) {
    return Number(count) > 0
      ? LATEST_BASE_DATA_PROVIDER_STATES.LOADED_WITH_DATA
      : LATEST_BASE_DATA_PROVIDER_STATES.LOADED_EMPTY
  }

  return LATEST_BASE_DATA_PROVIDER_STATES.SERVER_CONTEXT_UNAVAILABLE
}

export function latestBaseDataProviderStateLabel(state) {
  return Object.freeze({
    LOADING: '正在连接正式服务端',
    LOADED_EMPTY: '正式服务端已连接：当前业务范围为 0 条',
    LOADED_WITH_DATA: '正式服务端已连接：数据加载成功',
    AUTH_FAILED: '身份认证失败：请重新登录后读取正式数据',
    SERVER_CONTEXT_UNAVAILABLE: '服务端上下文尚未建立',
    API_FAILED: '正式 API 读取失败',
    SCHEMA_FAILED: '服务端事实契约不完整',
  })[state] || state
}
import { getTabAuthToken } from './tabAuthenticationContext.js'
