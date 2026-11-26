export const PDE_ENGINEERING_READINESS_RULES_VERSION = 'V1.14.2.8.4.10.4'

export const pdeEngineeringReadinessRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-READY-001', title: '工程准备对象字段与状态完整' }),
  Object.freeze({ ruleId: 'PDE-READY-002', title: '工程准备页面接入统一治理' }),
  Object.freeze({ ruleId: 'PDE-READY-003', title: '所有PDE页面三段导航可点击' }),
  Object.freeze({ ruleId: 'PDE-READY-004', title: 'CRM与PDE流程入口绑定正确' }),
  Object.freeze({ ruleId: 'PDE-READY-005', title: '采购付款财务边界保持关闭' }),
  Object.freeze({ ruleId: 'PDE-READY-006', title: '冻结基线Hash保持不变' }),
])

const result = (ruleId, passed, evidence) => {
  const rule = pdeEngineeringReadinessRules.find(item => item.ruleId === ruleId)
  return Object.freeze({
    ...rule,
    status: passed === true ? 'PASS' : passed === false ? 'FAIL' : 'UNKNOWN',
    evidence,
  })
}

export function evaluatePdeEngineeringReadinessRules({
  modelSource,
  readinessPage,
  pdePages,
  workbenchGovernance,
  shellSource,
  baselineChecks,
}) {
  const requiredFields = [
    'order_no', 'product', 'delivery_date', 'engineering_status', 'bom_status',
    'routing_status', 'document_status', 'manufacturing_output_status',
    'mrp_ready_status', 'delivery_risk',
  ]
  const statuses = [
    'not_started', 'engineering_preparing', 'bom_completed', 'routing_completed',
    'document_completed', 'manufacturing_ready', 'mrp_ready', 'completed',
  ]
  const modelComplete = modelSource.includes('class ProductEngineeringReadiness')
    && requiredFields.every(field => modelSource.includes(field))
    && statuses.every(status => modelSource.includes(status))
  const pageReady = readinessPage?.pageCode === 'pde-engineering-readiness'
    && readinessPage?.resource === 'engineering-readiness'
    && readinessPage?.governance?.frameworkVersion === 'PCE Enterprise Page V2'
    && readinessPage?.columns?.length >= 9
  const allPages = [...pdePages, { governance: workbenchGovernance }]
  const navigationComplete = allPages.every(page => (
    ['previous', 'current', 'next'].every(position => {
      const target = page.governance?.navigation?.[position]
      return Boolean(target?.pageCode && target?.pageUrl)
    })
  )) && shellSource.includes('data-pde-navigation-link="previous"')
    && shellSource.includes('data-pde-navigation-link="current"')
    && shellSource.includes('data-pde-navigation-link="next"')
  const crmAndPdeLinks = workbenchGovernance.navigation.previous.pageUrl === '/process-center?module=CRM'
    && workbenchGovernance.navigation.next.pageUrl === '/process-center?module=PDE'
  const boundaryClosed = readinessPage?.boundaryFacts?.length === 3
    && readinessPage.boundaryFacts.every(fact => fact.value === '否')
    && !modelSource.includes('PurchaseOrder')
  const baselinesUnchanged = baselineChecks.length >= 2 && baselineChecks.every(check => check.unchanged)
  return Object.freeze([
    result('PDE-READY-001', modelComplete, { requiredFields, statuses }),
    result('PDE-READY-002', pageReady, { pageCode: readinessPage?.pageCode, columnCount: readinessPage?.columns?.length }),
    result('PDE-READY-003', navigationComplete, { pageCount: allPages.length, positions: ['previous', 'current', 'next'] }),
    result('PDE-READY-004', crmAndPdeLinks, { crm: workbenchGovernance.navigation.previous, pde: workbenchGovernance.navigation.next }),
    result('PDE-READY-005', boundaryClosed, { boundaryFacts: readinessPage?.boundaryFacts }),
    result('PDE-READY-006', baselinesUnchanged, { baselineChecks }),
  ])
}
