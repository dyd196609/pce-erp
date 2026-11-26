const result = (ruleId, passed, message) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  message,
})

export function evaluateSupplierSettlementRules({
  routerSource = '',
  pageSource = '',
  processRegistry = [],
  facts = {},
} = {}) {
  const boundUrls = new Set(processRegistry.filter((node) => node.pageUrl).map((node) => node.pageUrl))
  return [
    result('SETTLEMENT-001', routerSource.includes("scm/supplier-payment-status"), '付款状态页面必须存在。'),
    result('SETTLEMENT-002', routerSource.includes("scm/supplier-settlement-completions"), '结算完成页面必须存在。'),
    result(
      'SETTLEMENT-003',
      boundUrls.has('/scm/supplier-payment-status') && boundUrls.has('/scm/supplier-settlement-completions'),
      '页面必须绑定 SCM 供应商结算流程。',
    ),
    result(
      'SETTLEMENT-004',
      ['待提交', '审核中', '已批准', '付款安排中', '付款完成', '结算完成']
        .every((label) => pageSource.includes(label)),
      '状态必须中文显示。',
    ),
    result('SETTLEMENT-005', !pageSource.includes('>银行发送<'), '禁止出现银行发送按钮。'),
    result('SETTLEMENT-006', !pageSource.includes('>执行付款<'), '禁止出现付款执行按钮。'),
    result(
      'SETTLEMENT-007',
      facts.factSource === 'server' && facts.factLoadContractVersion === 'PCE-FACT-LOAD-CONTRACT-V1.0',
      '必须存在服务端事实来源。',
    ),
    result(
      'SETTLEMENT-008',
      processRegistry.some((node) => node.nodeCode === 'supplier-settlement-completion'),
      '必须注册业务流程中心。',
    ),
  ]
}

