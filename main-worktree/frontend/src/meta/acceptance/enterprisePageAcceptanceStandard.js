export const ENTERPRISE_PAGE_ACCEPTANCE_STANDARD_VERSION = 'V1.14.2.8.4.14.1'
export const ENTERPRISE_PAGE_TEMPLATE = 'PCE Enterprise Page V2'

export const ENTERPRISE_PAGE_ACCEPTANCE_DIMENSIONS = Object.freeze([
  { id: 'A', code: 'identity', name: '页面身份', expected: ['pageCode', 'pageName', 'moduleCode', 'businessObject', 'version'], type: 'automatic' },
  { id: 'B', code: 'template', name: '页面模板', expected: ['页面身份区域', '当前业务动作说明', '流程导航', '服务端事实', '业务列表', '业务边界保护'], type: 'automatic+manual' },
  { id: 'C', code: 'route', name: '路由验收', expected: ['URL', 'router', 'pageCode绑定', '刷新可打开'], type: 'automatic+manual' },
  { id: 'D', code: 'navigation', name: '流程导航', expected: ['previousPage URL', 'currentPage URL', 'nextPage URL', '真实跳转'], type: 'automatic+manual' },
  { id: 'E', code: 'facts', name: '数据来源', expected: ['factSource=server', '禁止mock', '禁止localStorage假数据'], type: 'automatic' },
  { id: 'F', code: 'api', name: 'API验收', expected: ['GET权限', 'POST权限', 'PUT权限', 'DELETE权限'], type: 'automatic' },
  { id: 'G', code: 'relationship', name: '对象关系', expected: ['sourceObject', 'targetObject'], type: 'automatic+manual' },
  { id: 'H', code: 'state', name: '状态机', expected: ['状态枚举', '合法状态转换', '非法状态阻断'], type: 'automatic' },
  { id: 'I', code: 'button', name: '按钮动作', expected: ['buttonName', 'allowedStatus', 'actionType', 'writeScope'], type: 'automatic+manual' },
  { id: 'J', code: 'boundary', name: '业务边界', expected: ['禁止越权动作', '禁止付款', '禁止总账写入'], type: 'automatic+manual' },
  { id: 'K', code: 'exception', name: '异常验收', expected: ['无数据', '数据不存在', '状态异常', '权限不足', '接口失败', '页面不崩溃'], type: 'automatic+manual' },
  { id: 'L', code: 'performance', name: '性能验收', expected: ['routeLoadTime', 'schemaLoadTime', 'apiTime', 'renderTime', 'totalTime'], type: 'automatic+manual' },
  { id: 'M', code: 'data-protection', name: '数据保护', expected: ['productionUserDataWritten=false', '数据库Hash', '业务写入数量=0'], type: 'automatic' },
])

export const ENTERPRISE_PAGE_ACCEPTANCE_LIFECYCLE = Object.freeze([
  'PAGE_DEVELOPMENT',
  'AUTOMATIC_ACCEPTANCE',
  'MANUAL_ACCEPTANCE',
  'ACCEPTANCE_ARCHIVE',
  'NEXT_PAGE_ALLOWED',
])

export const ENTERPRISE_PAGE_PERFORMANCE_BUDGET = Object.freeze({
  normalPageMs: 1000,
  complexPageMs: 3000,
})

export const ENTERPRISE_PAGE_DATA_PROTECTION_POLICY = Object.freeze({
  factSource: 'server',
  productionUserDataWritten: false,
  automaticBusinessObjectCreation: false,
  automaticBusinessStateTransition: false,
  automaticHistoricalBackfill: false,
  mockBusinessFactAccepted: false,
})

export function createEnterprisePageAcceptanceChecks(pageCode) {
  return ENTERPRISE_PAGE_ACCEPTANCE_DIMENSIONS.map((dimension) => ({
    id: `${pageCode}-${dimension.id}`,
    dimension: dimension.id,
    name: dimension.name,
    expected: [...dimension.expected],
    type: dimension.type,
  }))
}

export function evaluateEnterprisePageReleaseGate(evidence = {}) {
  const automaticPassed = evidence.automaticAcceptance === 'PASS'
  const manualPassed = evidence.manualAcceptance === 'PASS'
  const archived = evidence.archiveStatus === 'ARCHIVED'
  return Object.freeze({
    automaticPassed,
    manualPassed,
    archived,
    nextPageAllowed: automaticPassed && manualPassed && archived,
    blockingReason: !automaticPassed
      ? '自动验收未通过'
      : !manualPassed
        ? '人工验收未通过或未执行'
        : !archived
          ? '验收记录未归档'
          : '',
  })
}

export function assertSinglePageAcceptanceScope(pageCodes = []) {
  const unique = [...new Set(pageCodes.filter(Boolean))]
  if (unique.length !== 1) throw new Error('PCE_PAGE_ACCEPTANCE_SCOPE_MUST_BE_SINGLE_PAGE')
  return unique[0]
}
