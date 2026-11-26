export const ACCESS_CONTROL_LOAD_STATE = Object.freeze({
  LOADING: 'loading',
  LOADED: 'loaded',
  EMPTY_VALID: 'empty_valid',
  PERMISSION_DENIED: 'permission_denied',
  AUTH_EXPIRED: 'auth_expired',
  READ_FAILED: 'read_failed',
})

const authenticationCodes = new Set([
  'authentication_failed',
  'not_authenticated',
  'token_not_valid',
  'AUTHENTICATION_REQUIRED',
])

export function classifyAccessControlFailure(response = {}) {
  const facts = response.factLoadFacts || {}
  const httpStatus = Number(facts.httpStatus || response.meta?.status || 0)
  const errorCode = String(facts.errorCode || response.error?.code || 'FACT_READ_FAILED')
  const apiUrl = String(facts.apiUrl || '')
  let state = ACCESS_CONTROL_LOAD_STATE.READ_FAILED
  let message = '服务器读取组织与权限正式数据失败，请核对目标服务与数据库后重试。'

  if (httpStatus === 401 || authenticationCodes.has(errorCode)) {
    state = ACCESS_CONTROL_LOAD_STATE.AUTH_EXPIRED
    message = '登录状态已失效，请从正常登录入口重新登录后再读取。'
  } else if (httpStatus === 403) {
    state = ACCESS_CONTROL_LOAD_STATE.PERMISSION_DENIED
    message = '当前账号没有访问组织与权限管理数据的正式授权。'
  }

  return { state, message, httpStatus, errorCode, apiUrl }
}

export function loadStateMessage(state) {
  return {
    [ACCESS_CONTROL_LOAD_STATE.LOADING]: '统计和列表会在服务端正式事实读取完成后显示。',
    [ACCESS_CONTROL_LOAD_STATE.LOADED]: '已读取服务端正式数据。',
    [ACCESS_CONTROL_LOAD_STATE.EMPTY_VALID]: '服务端读取成功，并确认当前范围内没有记录。',
    [ACCESS_CONTROL_LOAD_STATE.PERMISSION_DENIED]: '未取得管理读取授权，统计和列表未加载。',
    [ACCESS_CONTROL_LOAD_STATE.AUTH_EXPIRED]: '未取得有效登录身份，统计和列表未加载。',
    [ACCESS_CONTROL_LOAD_STATE.READ_FAILED]: '本次读取失败，统计显示为未知值，列表不会显示“暂无数据”。',
  }[state] || '尚未取得可信的服务端事实。'
}
