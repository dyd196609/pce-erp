import {
  ENTERPRISE_PAGE_ACCEPTANCE_STANDARD_VERSION,
  ENTERPRISE_PAGE_TEMPLATE,
  createEnterprisePageAcceptanceChecks,
  evaluateEnterprisePageReleaseGate,
} from './enterprisePageAcceptanceStandard.js'
import { resolveScmEnterpriseReadinessPage } from '../process/scmEnterpriseReadinessRegistry.js'
import { resolveScmProcessNavigation } from '../process/scmProcessNavigationContract.js'

const DEFINITIONS = Object.freeze([
  ['purchase-request', 'purchase-request', '采购申请', 'PurchaseRequest', 'PurchaseInquiry'],
  ['purchase-inquiry', 'purchase-inquiry', '询价', 'PurchaseInquiry', 'PriceApproval'],
  ['price-approval', 'price-approval', '采购核价', 'PriceApprovalPreparation', 'SupplierRecommendationDecisionContext'],
  ['purchase-order', 'purchase-order', '采购订单', 'PurchaseOrder', 'PurchaseReceipt'],
  ['purchase-receive', 'purchase-receive-preview', '收货', 'PurchaseReceipt', 'PurchaseInspection'],
  ['purchase-inspection', 'incoming-inspection', '质量检验', 'PurchaseInspection', 'WarehouseInbound'],
  ['warehouse-inbound', 'inventory-balances', '库存', 'InventoryBalance', null],
  ['supplier-reconciliation', 'supplier-reconciliation', '供应商对账', 'SupplierReconciliation', 'SupplierReconciliationDifference'],
  ['supplier-difference', 'supplier-reconciliation-differences', '差异分析', 'SupplierReconciliationDifference', 'SupplierReconciliationConfirmation'],
  ['supplier-confirmation', 'supplier-reconciliation-confirmations', '供应商确认', 'SupplierReconciliationConfirmation', 'SupplierPayableConfirmation'],
  ['supplier-payable-confirmation', 'supplier-payable-confirmation', '应付确认', 'SupplierPayableConfirmation', 'SupplierPaymentRequest'],
  ['payment-request', 'supplier-payment-request', '付款申请', 'SupplierPaymentRequest', 'SupplierPaymentStatus'],
  ['payment-status', 'supplier-payment-status', '付款状态记录', 'SupplierPaymentStatus', 'SupplierSettlementCompletion'],
  ['supplier-settlement', 'supplier-settlement-completion', '供应商结算完成', 'SupplierSettlementCompletion', 'SupplierPerformance'],
  ['supplier-performance', 'supplier-performance', '供应商绩效', 'SupplierPerformance', 'BuyerPerformance'],
  ['buyer-performance', 'buyer-performance', '采购员绩效', 'BuyerPerformance', null],
])

const BUTTON_RULES = Object.freeze({
  'purchase-request': [{ buttonName: '转询价', allowedStatus: ['approved'], actionType: 'create-downstream', writeScope: 'scm_purchase_inquiry' }],
  'purchase-inquiry': [{ buttonName: '转核价', allowedStatus: ['approved'], actionType: 'create-downstream', writeScope: 'scm_price_approval' }],
  'price-approval': [{ buttonName: '生成采购订单', allowedStatus: ['approved'], actionType: 'create-downstream', writeScope: 'purchase_order,purchase_order_item' }],
  'purchase-order': [{ buttonName: '确认收货', allowedStatus: ['final_approved'], actionType: 'create-downstream', writeScope: 'scm_purchase_receipt' }],
  'purchase-receive': [{ buttonName: '创建质量检验', allowedStatus: ['received'], actionType: 'create-downstream', writeScope: 'scm_purchase_inspection' }],
  'purchase-inspection': [
    { buttonName: '开始检验', allowedStatus: ['pending'], actionType: 'state-transition', writeScope: 'scm_purchase_inspection.status' },
    { buttonName: '检验合格', allowedStatus: ['inspecting'], actionType: 'state-transition', writeScope: 'scm_purchase_inspection.status,qualified_quantity' },
    { buttonName: '确认入库', allowedStatus: ['qualified'], actionType: 'create-downstream', writeScope: 'scm_warehouse_inbound' },
  ],
})

const READ_ONLY_BUTTON = Object.freeze({
  buttonName: '查看详情',
  allowedStatus: ['*'],
  actionType: 'read',
  writeScope: 'none',
})

export const SCMEnterpriseAcceptanceMatrixV11428141 = Object.freeze(DEFINITIONS.map(([
  pageCode,
  runtimePageCode,
  pageName,
  sourceObject,
  targetObject,
], index) => {
  const runtime = resolveScmEnterpriseReadinessPage(runtimePageCode)
  const navigation = resolveScmProcessNavigation(runtimePageCode)
  const buttons = BUTTON_RULES[pageCode] || [READ_ONLY_BUTTON]
  return Object.freeze({
    standardVersion: ENTERPRISE_PAGE_ACCEPTANCE_STANDARD_VERSION,
    pageCode,
    runtimePageCode,
    pageName,
    module: 'SCM',
    moduleCode: 'SCM',
    businessObject: runtime?.businessObject,
    version: ENTERPRISE_PAGE_ACCEPTANCE_STANDARD_VERSION,
    template: ENTERPRISE_PAGE_TEMPLATE,
    pageUrl: runtime?.pageUrl,
    schema: runtime?.schema,
    apiEndpoint: runtime?.apiEndpoint,
    factSource: 'server',
    sourceObject: index === 0 ? null : sourceObject,
    targetObject,
    navigation: {
      previousPage: navigation?.previousPage || null,
      currentPage: navigation?.currentPage || null,
      nextPage: navigation?.nextPage || null,
    },
    apiMethodPolicy: {
      GET: 'allowed-read',
      POST: buttons.some((button) => button.actionType !== 'read') ? 'explicit-action-with-permission' : 'forbidden',
      PUT: 'forbidden-unless-page-action-registry-allows',
      DELETE: 'forbidden-unless-page-action-registry-allows',
    },
    buttonRules: buttons.map((button) => ({ ...button })),
    checks: createEnterprisePageAcceptanceChecks(pageCode),
    automaticAcceptance: 'PENDING',
    manualAcceptance: 'PENDING',
    archiveStatus: 'NOT_ARCHIVED',
    nextPageAllowed: false,
  })
}))

export function listEnterprisePageAcceptanceMatrix(moduleCode = '') {
  const pages = moduleCode
    ? SCMEnterpriseAcceptanceMatrixV11428141.filter((page) => page.moduleCode === moduleCode)
    : SCMEnterpriseAcceptanceMatrixV11428141
  return pages.map((page) => ({ ...page }))
}

export function resolveEnterprisePageAcceptance(pageCode) {
  const page = SCMEnterpriseAcceptanceMatrixV11428141.find((item) => item.pageCode === pageCode || item.runtimePageCode === pageCode)
  return page ? { ...page } : null
}

export function enterprisePageReleaseGate(pageCode, evidence = {}) {
  if (!resolveEnterprisePageAcceptance(pageCode)) throw new Error(`PCE_PAGE_ACCEPTANCE_NOT_REGISTERED:${pageCode}`)
  return evaluateEnterprisePageReleaseGate(evidence)
}
