export function testBomFailure(value, fallback = '测试BOM操作未完成，请重试。') {
  const raw = value?.error || value
  const code = String(raw?.code || value?.errorCode || '')
  const status = Number(value?.httpStatus || value?.meta?.status || value?.response?.status || 0)
  const authMessage = typeof raw?.message === 'string' ? raw.message : typeof raw === 'string' ? raw : ''
  const authenticationRequired = /Token已过期|无效的Token|请重新登录|未登录|会话.*失效|credentials.*not provided|token.*expired/i.test(authMessage) || status === 401 || /^(HTTP_401|AUTHENTICATION_CONTEXT_CHANGED|NOT_AUTHENTICATED|TOKEN_NOT_VALID|TOKEN_EXPIRED|INVALID_TOKEN|AUTHENTICATION_FAILED)$/i.test(code)
  if (authenticationRequired) return {message:'尚未登录或会话已失效，请通过正常登录入口重新登录后刷新测试BOM。', authenticationRequired:true}
  if (status === 403) return {message:'当前账号无权执行此操作，请使用已有相应权限的账号。', authenticationRequired:false}
  const message = typeof raw === 'string' ? raw : typeof raw?.message === 'string' ? raw.message : typeof value?.errorMessage === 'string' ? value.errorMessage : fallback
  return {message:message && message !== '[object Object]' ? message : fallback, authenticationRequired:false}
}
