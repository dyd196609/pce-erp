export const SCM_PROCESS_CENTER_REGISTRY_VERSION = 'V1.14.2.8.18.10.3'
export const SCM_PURCHASE_PROCESS_CODE = 'SCM_PURCHASE_SETTLEMENT'
export const SCM_PURCHASE_PROCESS_NAME = 'SCM采购与供应商结算流程'

const definitions = [
  ['purchase-request', '采购申请', 'purchase-request', '/scm/purchase-request', 'purchaseRequestProcessAcceptanceProfile'],
  ['purchase-approval', '采购审批', 'purchase-approval', '/scm/purchase-approvals', 'purchaseRequestApprovalAcceptanceProfile'],
  ['inquiry-preparation', '询价准备', 'inquiry-preparation', '/scm/inquiry-preparations', 'PAGE-INQUIRY-PREPARATION'],
  ['purchase-inquiry', '询价', 'purchase-inquiry', '/scm/purchase-inquiry', 'purchaseInquiryProcessAcceptanceProfile'],
  ['supplier-quote', '供应商报价', 'supplier-quote-workbench', '/scm/supplier-quotation', 'supplierQuoteAcceptanceProfileV114289'],
  ['quote-comparison', '报价比较', 'quote-comparison-workbench', '/scm/quote-comparisons', 'quoteComparisonAcceptanceProfileV1142810'],
  ['price-approval', '采购核价', 'price-approval', '/scm/price-approval', 'priceApprovalPageAcceptanceProfile'],
  ['supplier-recommendation', '供应商推荐', 'supplier-recommendation', '/scm/supplier-recommendation', 'PAGE-SUPPLIER-RECOMMENDATION'],
  ['purchase-order-creation-gate', '采购订单准入', 'purchase-order-gate', '/scm/purchase-order-gate', 'PAGE-PURCHASE-ORDER-GATE'],
  ['purchase-order', '采购订单', 'purchase-order', '/scm/purchase-order', 'purchaseOrderTransactionProcessAcceptanceProfile'],
  ['goods-receipt', '收货', 'purchase-receive-preview', '/wms/purchase-receive-preview', 'scmEnterprisePageAcceptanceProfile'],
  ['quality-inspection', '质量检验', 'incoming-inspection', '/qms/incoming-inspections', 'scmEnterprisePageAcceptanceProfile'],
  ['warehouse-receipt', '入库', 'inventory-balances', '/wms/inventory-balances', 'scmEnterprisePageAcceptanceProfile'],
  ['supplier-reconciliation', '供应商对账', 'supplier-reconciliation', '/scm/supplier-reconciliations', 'supplierReconciliationPageAcceptanceProfile'],
  ['reconciliation-difference', '差异分析', 'supplier-reconciliation-differences', '/scm/supplier-reconciliation-differences', 'supplierReconciliationPageAcceptanceProfile'],
  ['supplier-confirmation', '供应商确认', 'supplier-reconciliation-confirmations', '/scm/supplier-reconciliation-confirmations', 'supplierReconciliationPageAcceptanceProfile'],
  ['supplier-payable-confirmation', '应付确认', 'supplier-payable-confirmation', '/scm/supplier-payable-confirmations', 'supplierSettlementPageAcceptanceProfile'],
  ['supplier-payment-request', '付款申请', 'supplier-payment-request', '/scm/supplier-payment-requests', 'supplierSettlementPageAcceptanceProfile'],
  ['payment-status-record', '付款状态记录', 'supplier-payment-status', '/scm/supplier-payment-status', 'supplierSettlementPageAcceptanceProfile'],
  ['supplier-settlement-completion', '供应商结算完成', 'supplier-settlement-completion', '/scm/supplier-settlement-completions', 'supplierSettlementPageAcceptanceProfile'],
  ['supplier-performance', '供应商绩效', 'supplier-performance', '/scm/supplier-performance', 'supplierPerformancePageAcceptanceProfile'],
  ['buyer-performance', '采购员绩效', 'buyer-performance', '/scm/buyer-performance', 'buyerPerformancePageAcceptanceProfile'],
]

export const SCM_PURCHASE_PRIMARY_NODE_CODES = Object.freeze(definitions.slice(0, 12).map(item => item[0]))

export const SCM_PURCHASE_PROCESS_CENTER_NODES = Object.freeze(definitions.map((definition, index, values) => {
  const [nodeCode, configuredNodeName, pageCode, pageRoute, acceptanceProfile] = definition
  const businessName = resolveBusinessName(nodeCode)
  const nodeName = businessName?.processName || configuredNodeName
  return Object.freeze({
    nodeCode,
    nodeName,
    runtimeNodeCode: ({
      'supplier-quote': 'SCM_SUPPLIER_QUOTE',
      'quote-comparison': 'SCM_QUOTE_COMPARISON',
      'supplier-recommendation': 'SCM_SUPPLIER_RECOMMENDATION_DECISION',
    })[nodeCode] || '',
    previousNode: index ? values[index - 1][0] : null,
    nextNode: index < values.length - 1 ? values[index + 1][0] : null,
    pageCode,
    pageRoute,
    pageUrl: pageRoute,
    acceptanceProfile,
    sequence: index + 1,
    allowNewTab: true,
    statusDescription: '页面已登记，可查看业务事实并在新标签打开。',
  })
}))

export function listScmPurchaseProcessCenterNodes() {
  return SCM_PURCHASE_PROCESS_CENTER_NODES.map(node => ({ ...node }))
}

export function resolveScmPurchaseProcessNodePageUrlV11428166(node = {}) {
  if (node.nodeCode !== 'supplier-recommendation') return node.pageUrl || node.pageRoute || ''
  return supplierRecommendationProcessCenterContextProviderV11428166.buildPageUrl()
}

export function resolveScmPurchaseProcessNodePageUrlV11428167(node = {}) {
  if (node.nodeCode !== 'supplier-recommendation') return node.pageUrl || node.pageRoute || ''
  return supplierRecommendationTaskProcessCenterProviderV11428167.buildPageUrl()
}

export function resolveScmPurchaseProcessNodePageUrlV11428169(node = {}) {
  if (node.nodeCode !== 'supplier-recommendation') return node.pageUrl || node.pageRoute || ''
  return supplierRecommendationDecisionBatchStoreV11428169.buildPageUrl()
}

export function resolveScmPurchaseProcessNodePageUrlV11428171(node = {}) {
  if (node.nodeCode !== 'supplier-recommendation') return node.pageUrl || node.pageRoute || ''
  return supplierRecommendationRouteContextResolverV11428171.buildPageRoute()
}

export function validateScmPurchaseProcessCenterRegistry() {
  const nodes = SCM_PURCHASE_PROCESS_CENTER_NODES
  const linked = nodes.every((node, index) => node.sequence === index + 1
    && node.previousNode === (index ? nodes[index - 1].nodeCode : null)
    && node.nextNode === (index < nodes.length - 1 ? nodes[index + 1].nodeCode : null))
  const complete = nodes.every(node => node.nodeCode && node.nodeName && node.pageRoute
    && node.pageCode && node.acceptanceProfile && node.allowNewTab)
  const valid = linked && complete && SCM_PURCHASE_PRIMARY_NODE_CODES.join('>') === [
    'purchase-request', 'purchase-approval', 'inquiry-preparation', 'purchase-inquiry',
    'supplier-quote', 'quote-comparison', 'price-approval', 'supplier-recommendation',
    'purchase-order-creation-gate', 'purchase-order', 'goods-receipt', 'quality-inspection',
  ].join('>')
  return Object.freeze({ valid, result: valid ? 'PASS' : 'FAIL', nodeCount: nodes.length,
    primaryNodeCount: SCM_PURCHASE_PRIMARY_NODE_CODES.length })
}
import { resolveBusinessName } from '../governance/businessNameRegistry.js'
import { supplierRecommendationProcessCenterContextProviderV11428166 } from './scm/supplierRecommendation/supplierRecommendationProcessCenterContextV11428166.js'
import { supplierRecommendationTaskProcessCenterProviderV11428167 } from './scm/supplierRecommendation/supplierRecommendationTaskProcessCenterContextV11428167.js'
import { supplierRecommendationDecisionBatchStoreV11428169 } from './scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js'
import { supplierRecommendationRouteContextResolverV11428171 } from './scm/supplierRecommendation/supplierRecommendationRouteContextResolverV11428171.js'
