export const REVIEW_LOAD_STATES = Object.freeze({
  IDLE: 'idle',
  LOADING: 'loading',
  SUCCESS: 'success',
  OBJECT_REQUIRED: 'object_required',
  ASSIGNMENT_REQUIRED: 'assignment_required',
  SCOPE_DENIED: 'scope_denied',
  UNAUTHENTICATED: 'unauthenticated',
  FORBIDDEN: 'forbidden',
  TIMEOUT: 'timeout',
  TEMPLATE_ERROR: 'template_error',
  RESPONSE_ERROR: 'response_error',
  SERVICE_ERROR: 'service_error',
})

export function validateOrderReviewFacts(facts) {
  if (!facts || typeof facts !== 'object') return '服务端未返回评审事实。'
  if (!facts.source || !facts.orderContext) return '服务端响应缺少来源或订单上下文。'
  if (!facts.review?.template || !Array.isArray(facts.review?.templateItems)) {
    return '服务端响应缺少正式评审模板结构。'
  }
  if (!facts.review.templateItems.length) return '正式评审模板没有可用项目，请联系管理员核对模板配置。'
  return ''
}

export function classifyOrderReviewFailure(response) {
  const code = String(response?.error?.code || response?.errorCode || '').trim()
  const message = String(response?.error?.message || response?.errorMessage || '评审资料读取失败。').trim()
  const status = Number(response?.meta?.status || response?.httpStatus || response?.factLoadFacts?.httpStatus || 0)
  const lowered = `${code} ${message}`.toLowerCase()

  if (status === 401 || /重新登录|未登录|token.*(过期|无效)|authentication/.test(lowered)) {
    return { state: REVIEW_LOAD_STATES.UNAUTHENTICATED, code: code || 'NOT_AUTHENTICATED', message }
  }
  if (code === 'REVIEW_OBJECT_ACCESS_REQUIRED') {
    return { state: REVIEW_LOAD_STATES.ASSIGNMENT_REQUIRED, code, message }
  }
  if (code === 'REVIEW_SCOPE_DENIED') {
    return { state: REVIEW_LOAD_STATES.SCOPE_DENIED, code, message }
  }
  if (status === 403 || code === 'VIEW_PERMISSION_DENIED') {
    return { state: REVIEW_LOAD_STATES.FORBIDDEN, code: code || 'VIEW_PERMISSION_DENIED', message }
  }
  if (code === 'REVIEW_OBJECT_REQUIRED' || code === 'ORDER_SOURCE_NOT_FOUND') {
    return { state: REVIEW_LOAD_STATES.OBJECT_REQUIRED, code, message }
  }
  if (code === 'REVIEW_TEMPLATE_MISSING') {
    return { state: REVIEW_LOAD_STATES.TEMPLATE_ERROR, code, message }
  }
  if (code === 'ECONNABORTED' || /timeout|超时/.test(lowered)) {
    return { state: REVIEW_LOAD_STATES.TIMEOUT, code: code || 'READ_TIMEOUT', message: '评审资料读取超时，请重新读取。' }
  }
  return { state: REVIEW_LOAD_STATES.SERVICE_ERROR, code: code || 'REVIEW_READ_FAILED', message }
}

export function reviewLoadPresentation(state, message = '') {
  const presentations = {
    [REVIEW_LOAD_STATES.IDLE]: ['尚未读取评审资料', '点击“重新读取”取得当前服务端事实。'],
    [REVIEW_LOAD_STATES.LOADING]: ['正在读取评审资料', '正在核对评审对象、来源版本、正式模板、历史和当前权限。项目数量在读取完成前显示为“—”。'],
    [REVIEW_LOAD_STATES.OBJECT_REQUIRED]: ['尚未确定评审对象', message || '请从正常流程选择可辨认的订单、客户和项目后再进入。'],
    [REVIEW_LOAD_STATES.ASSIGNMENT_REQUIRED]: ['尚未分配当前评审', message || '当前账号已具备模块查看资格，但尚未获得本次评审的对象、版本及本人责任分配。'],
    [REVIEW_LOAD_STATES.SCOPE_DENIED]: ['当前公司或数据范围不匹配', message || '当前角色动作已登记，但授权范围不覆盖本次流程。'],
    [REVIEW_LOAD_STATES.UNAUTHENTICATED]: ['当前登录状态已失效', message || '请从正常登录入口重新登录，然后返回本页重新读取。'],
    [REVIEW_LOAD_STATES.FORBIDDEN]: ['当前身份没有查看资格', message || '当前账号缺少本页只读资格或公司数据范围。'],
    [REVIEW_LOAD_STATES.TIMEOUT]: ['评审资料读取超时', message || '请求已结束，没有把超时显示为零项目。'],
    [REVIEW_LOAD_STATES.TEMPLATE_ERROR]: ['正式评审模板配置异常', message || '没有把模板异常显示为零项目。'],
    [REVIEW_LOAD_STATES.RESPONSE_ERROR]: ['评审响应结构异常', message || '服务端返回内容不符合评审页面合同。'],
    [REVIEW_LOAD_STATES.SERVICE_ERROR]: ['评审资料读取失败', message || '服务异常已结束，没有把失败显示为零项目。'],
  }
  const [title, description] = presentations[state] || presentations[REVIEW_LOAD_STATES.SERVICE_ERROR]
  return { title, description }
}
