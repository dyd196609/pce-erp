export const SCM_PAGE_GOVERNANCE_COMPLIANCE_VERSION = 'V1.14.2.8.18.10.3.1'

export const SCM_PAGE_GOVERNANCE_RULES = Object.freeze([
  { ruleCode: 'PAGE-IDENTITY', ruleName: '页面身份完整性', evidenceKey: 'identity' },
  { ruleCode: 'PAGE-TEMPLATE', ruleName: 'PCE Enterprise Page V2 顶部与流程区', evidenceKey: 'pageTemplate' },
  { ruleCode: 'PAGE-REGION', ruleName: '业务上下文、核心业务、动作和下一动作区域', evidenceKey: 'businessRegions' },
  { ruleCode: 'LIST-TEMPLATE', ruleName: '企业列表通用能力', evidenceKey: 'listTemplate', listOnly: true },
  { ruleCode: 'ACTION-TEMPLATE', ruleName: '按钮到动作结果闭环', evidenceKey: 'actionTemplate' },
  { ruleCode: 'STATE-TEMPLATE', ruleName: '业务、流程与审批状态业务化展示', evidenceKey: 'stateTemplate' },
  { ruleCode: 'NODE-PAGE-001', ruleName: '节点页面唯一映射', evidenceKey: 'uniqueMapping' },
  { ruleCode: 'PROCESS-011', ruleName: '节点页面路由验收', evidenceKey: 'routeMapping' },
  { ruleCode: 'PROCESS-009', ruleName: '一页一验收证据', evidenceKey: 'acceptanceRecord' },
])

export const SCM_PAGE_GOVERNANCE_TARGETS = Object.freeze([
  ['PAGE-001','purchase-request','采购申请','/scm/purchase-request',true],
  ['PAGE-002','purchase-approval','采购审批','/scm/purchase-approvals',false],
  ['PAGE-003','inquiry-preparation','询价准备','/scm/inquiry-preparations',true],
  ['PAGE-004','purchase-inquiry','采购询价','/scm/purchase-inquiry',true],
  ['PAGE-005','supplier-quote-workbench','供应商报价','/scm/supplier-quotation',true],
  ['PAGE-006','quote-comparison-workbench','报价比较工作台','/scm/quote-comparisons',true],
  ['PAGE-007','price-approval','采购核价','/scm/price-approval',true],
  ['PAGE-008','supplier-recommendation','供应商推荐','/scm/supplier-recommendation',true],
  ['PAGE-009','purchase-order-gate','采购订单准入','/scm/purchase-order-gate',true],
].map(([acceptanceCode,pageCode,pageName,route,listPage])=>Object.freeze({acceptanceCode,pageCode,pageName,route,listPage})))

export const SCM_NODE_SEMANTIC_MAPPINGS = Object.freeze({
  'purchase-approval': Object.freeze({ pageCode:'purchase-approval', businessObject:'PurchaseRequestApproval',
    semantic:'采购申请审批实例执行', forbiddenPageCodes:Object.freeze(['approval-flow-config']),
    forbiddenNodeCodes:Object.freeze(['purchase-order-approval','purchase-order-creation-gate']) }),
})

export function evaluateScmPageGovernanceCompliance(evidenceByPage={}) {
  const pageResults=SCM_PAGE_GOVERNANCE_TARGETS.map(page=>{
    const evidence=evidenceByPage[page.pageCode]||{}
    const checks=SCM_PAGE_GOVERNANCE_RULES.map(rule=>{
      const notApplicable=rule.listOnly&&!page.listPage
      const passed=notApplicable||evidence[rule.evidenceKey]===true
      return Object.freeze({ruleCode:rule.ruleCode,evidenceKey:rule.evidenceKey,notApplicable,passed,result:passed?'PASS':'FAIL'})
    })
    const passed=checks.every(check=>check.passed)
    return Object.freeze({...page,checks:Object.freeze(checks),passed,result:passed?'PASS':'FAIL'})
  })
  const passed=pageResults.every(page=>page.passed)
  return Object.freeze({version:SCM_PAGE_GOVERNANCE_COMPLIANCE_VERSION,pageResults:Object.freeze(pageResults),passed,result:passed?'PASS':'FAIL'})
}
