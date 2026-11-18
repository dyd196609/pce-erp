const expectedScmPurchaseNodeNames = Object.freeze([
  '采购申请',
  '询价',
  '核价',
  '采购订单',
  '收货',
  '质量检验',
  '入库',
  '供应商对账',
  '差异分析',
  '供应商确认',
  '应付确认',
  '付款申请',
  '付款状态记录',
  '供应商结算完成',
  '供应商绩效',
  '采购员绩效',
])

const result = (ruleId, passed, message) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  message,
})

export function evaluateBusinessProcessRules({ registry = [], knownPageUrls = [] } = {}) {
  const boundNodes = registry.filter((node) => node.pageUrl)
  const orderedNames = [...registry]
    .sort((left, right) => left.sequence - right.sequence)
    .map((node) => node.nodeName)
  const uniquePageUrls = new Set(boundNodes.map((node) => node.pageUrl))

  return [
    result(
      'PROCESS-001',
      boundNodes.length > 0 && boundNodes.every((node) => node.moduleCode && node.processCode),
      '每个已注册业务页面必须具有模块和流程归属。',
    ),
    result(
      'PROCESS-002',
      boundNodes.every((node) => node.nodeCode && node.nodeName)
        && uniquePageUrls.size === boundNodes.length,
      '每个已注册业务页面必须唯一绑定一个流程节点。',
    ),
    result(
      'PROCESS-003',
      boundNodes.every((node) => /^V\d/.test(node.pageVersion)),
      '每个已注册业务页面必须声明版本。',
    ),
    result(
      'PROCESS-004',
      boundNodes.every((node) => node.acceptanceStatus === 'PASS'),
      '每个已注册业务页面必须具有通过的自动验收状态。',
    ),
    result(
      'PROCESS-005',
      JSON.stringify(orderedNames) === JSON.stringify(expectedScmPurchaseNodeNames)
        && boundNodes.every((node) => knownPageUrls.includes(node.pageUrl)),
      'SCM 采购结算流程顺序及页面路由必须正确。',
    ),
  ]
}

export { expectedScmPurchaseNodeNames }
