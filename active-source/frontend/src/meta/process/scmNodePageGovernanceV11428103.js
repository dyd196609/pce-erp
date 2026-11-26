export const SCM_NODE_PAGE_GOVERNANCE_VERSION = 'V1.14.2.8.18.10.3'

export const NODE_PAGE_001 = Object.freeze({
  ruleCode: 'NODE-PAGE-001',
  ruleName: '节点页面唯一映射',
  requirement: '一个独立业务节点必须对应唯一 Page Contract、Page Identity 和主 Route。',
})

export const PROCESS_011 = Object.freeze({
  ruleCode: 'PROCESS-011',
  ruleName: '节点页面映射验收',
  chain: Object.freeze(['Node', 'PageContract', 'PageIdentity', 'Route', 'Acceptance']),
})

export const SCM_NODE_PAGE_MAPPINGS_V11428103 = Object.freeze([
  ['purchase-request', '采购申请', 'purchase-request', '采购申请', '/scm/purchase-request', 'PurchaseRequest', 'ScmPurchaseRequestPage', 'PAGE-PURCHASE-REQUEST.md'],
  ['purchase-approval', '采购审批', 'purchase-approval', '采购审批', '/scm/purchase-approvals', 'PurchaseRequestApproval', 'PurchaseApprovalExecutionPage', 'PAGE-PURCHASE-APPROVAL.md'],
  ['inquiry-preparation', '询价准备', 'inquiry-preparation', '询价准备', '/scm/inquiry-preparations', 'InquiryPreparationContext', 'ScmInquiryPreparationPage', 'PAGE-INQUIRY-PREPARATION.md'],
  ['purchase-inquiry', '询价', 'purchase-inquiry', '采购询价', '/scm/purchase-inquiry', 'PurchaseInquiry', 'ScmPurchaseInquiryNodePage', 'PAGE-PURCHASE-INQUIRY.md'],
  ['supplier-quote', '供应商报价', 'supplier-quote-workbench', '供应商报价', '/scm/supplier-quotation', 'SupplierQuotation', 'ScmSupplierQuoteWorkbenchPage', 'PAGE-SUPPLIER-QUOTE.md'],
  ['quote-comparison', '报价比较', 'quote-comparison-workbench', '报价比较', '/scm/quote-comparisons', 'QuoteComparison', 'ScmQuoteComparisonWorkbenchPage', 'QUOTE-COMPARISON-PAGE.md'],
  ['price-approval', '核价', 'price-approval', '采购核价', '/scm/price-approval', 'PriceApprovalPreparation', 'ScmPriceApprovalRuntimePage', 'SCM-PRICE-APPROVAL-ACT-001.md'],
  ['supplier-recommendation', '供应商推荐', 'supplier-recommendation', '供应商推荐', '/scm/supplier-recommendation', 'SupplierRecommendationDecisionBatch', 'ScmSupplierRecommendationDecisionWorkbenchPage', 'PAGE-SUPPLIER-RECOMMENDATION.md'],
  ['purchase-order-creation-gate', '采购订单准入', 'purchase-order-gate', '采购订单准入', '/scm/purchase-order-gate', 'PurchaseOrderCreationGateDecision', 'ScmPurchaseOrderGatePage', 'PAGE-PURCHASE-ORDER-GATE.md'],
].map(([nodeCode, nodeName, pageCode, pageName, route, businessObject, componentName, acceptanceFile]) => Object.freeze({
  nodeCode, nodeName,
  pageContract: Object.freeze({ pageCode, pageName, route, moduleCode: 'SCM', businessObject }),
  pageIdentity: Object.freeze({ pageCode, pageName, route, moduleCode: 'SCM', businessObject }),
  route: Object.freeze({ path: route, componentName, pageCode }),
  acceptanceFile,
})))

export function listScmNodePageMappingsV11428103() {
  return SCM_NODE_PAGE_MAPPINGS_V11428103.map(mapping => ({
    ...mapping,
    pageContract: { ...mapping.pageContract },
    pageIdentity: { ...mapping.pageIdentity },
    route: { ...mapping.route },
  }))
}

export function validateScmNodePageGovernanceV11428103() {
  const mappings = SCM_NODE_PAGE_MAPPINGS_V11428103
  const pageCodes = mappings.map(item => item.pageContract.pageCode)
  const routes = mappings.map(item => item.pageContract.route)
  const unique = new Set(pageCodes).size === mappings.length && new Set(routes).size === mappings.length
  const complete = mappings.every(item => {
    const contract = item.pageContract
    const identity = item.pageIdentity
    return item.nodeCode && item.nodeName && item.acceptanceFile
      && ['pageCode', 'pageName', 'route', 'moduleCode', 'businessObject'].every(field => contract[field])
      && ['pageCode', 'pageName', 'route', 'moduleCode', 'businessObject'].every(field =>
        identity[field] === contract[field])
      && item.route.path === contract.route && item.route.pageCode === contract.pageCode
      && item.route.componentName
  })
  const valid = unique && complete
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', nodePage001: unique,
    process011: complete, mappingCount: mappings.length })
}
