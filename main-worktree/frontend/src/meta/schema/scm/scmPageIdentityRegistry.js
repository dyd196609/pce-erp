export const SCM_PAGE_IDENTITY_REGISTRY_VERSION = 'V1.14.2.8.18.10.3'

const SCM_PAGE_IDENTITY_DEFINITIONS = [
  Object.freeze({
    pageCode: 'inquiry-preparation', pageName: '询价准备', moduleCode: 'SCM',
    businessObject: 'InquiryPreparationContext', route: '/scm/inquiry-preparations',
    previousModule: 'purchase-approval', currentModule: 'inquiry-preparation', nextModule: 'purchase-inquiry',
    routePattern: /^\/scm\/inquiry-preparations\/?$/, tableId: 'inquiry_preparation',
    schema: 'InquiryPreparationSchema', pageType: 'business_list',
  }),
  Object.freeze({
    pageCode: 'supplier-recommendation', pageName: '供应商推荐', moduleCode: 'SCM',
    businessObject: 'SupplierRecommendationDecisionBatch', route: '/scm/supplier-recommendation',
    previousModule: 'quote-comparison', currentModule: 'supplier-recommendation', nextModule: 'purchase-order-gate',
    routePattern: /^\/scm\/supplier-recommendation\/?$/, tableId: 'supplier_recommendation',
    schema: 'SupplierRecommendationDecisionBatchSchema', pageType: 'business_workbench',
  }),
  Object.freeze({
    pageCode: 'purchase-order-gate', pageName: '采购订单准入', moduleCode: 'SCM',
    businessObject: 'PurchaseOrderCreationGateDecision', route: '/scm/purchase-order-gate',
    previousModule: 'supplier-recommendation', currentModule: 'purchase-order-gate', nextModule: 'purchase-order',
    routePattern: /^\/scm\/purchase-order-gate\/?$/, tableId: 'purchase_order_gate',
    schema: 'PurchaseOrderCreationGateSchema', pageType: 'business_list',
  }),
  Object.freeze({
    pageCode: 'quote-comparison-workbench',
    pageName: '报价比较工作台',
    moduleCode: 'SCM',
    businessObject: 'QuoteComparison',
    route: '/scm/quote-comparisons',
    previousModule: 'supplier-quote',
    currentModule: 'quote-comparison',
    nextModule: 'supplier-recommendation-decision-preparation',
    routePattern: /^\/scm\/quote-comparison(?:s)?\/?$/,
    tableId: 'quote_comparison',
    schema: 'QuoteComparisonSchema',
    pageType: 'business_workbench',
  }),
  Object.freeze({
    pageCode: 'supplier-quote-workbench',
    pageName: '供应商报价工作台',
    moduleCode: 'SCM',
    businessObject: 'SupplierQuote',
    route: '/scm/supplier-quotes',
    previousModule: 'price-approval-preparation',
    currentModule: 'supplier-quote',
    nextModule: 'quote-comparison-preparation',
    routePattern: /^\/scm\/supplier-quote(?:s)?\/?$/,
    tableId: 'supplier_quote',
    schema: 'SupplierQuoteSchema',
    pageType: 'business_workbench',
  }),
  Object.freeze({
    pageCode: 'approval-flow-config',
    pageName: '审批规则配置',
    moduleCode: 'SCM',
    businessObject: 'ApprovalConfiguration',
    route: '/admin/approval-flow-config',
    routePattern: /^\/admin\/approval-flow-config\/?$/,
    tableId: 'approval_flow_config',
    schema: 'ApprovalContractSchema',
    pageType: 'business_config',
  }),
  Object.freeze({
    pageCode: 'purchase-approval', pageName: '采购审批', moduleCode: 'SCM',
    businessObject: 'PurchaseRequestApproval', route: '/scm/purchase-approvals',
    previousModule: 'purchase-request', currentModule: 'purchase-approval', nextModule: 'inquiry-preparation',
    routePattern: /^\/scm\/purchase-approvals\/?$/, tableId: 'purchase_approval',
    schema: 'PurchaseRequestApprovalSchema', pageType: 'business_execution',
  }),
  Object.freeze({
    pageCode: 'purchase-request',
    pageName: '采购申请',
    moduleCode: 'SCM',
    businessObject: 'PurchaseRequest',
    route: '/scm/purchase-request',
    routePattern: /^\/scm\/purchase-request(?:s|\/[^/]+)?$/,
    tableId: 'purchase_request',
    schema: 'PurchaseRequestSchema',
    pageType: 'business_list',
  }),
  Object.freeze({
    pageCode: 'purchase-inquiry',
    pageName: '采购询价',
    moduleCode: 'SCM',
    businessObject: 'PurchaseInquiry',
    route: '/scm/purchase-inquiry',
    previousModule: 'inquiry-preparation',
    currentModule: 'purchase-inquiry',
    nextModule: 'supplier-quote',
    routePattern: /^\/scm\/purchase-inquir(?:ies|y)\/?$/,
    tableId: 'purchase_inquiry',
    schema: 'PurchaseInquirySchema',
    pageType: 'business_list',
  }),
  Object.freeze({
    pageCode: 'purchase-inquiry-detail', pageName: '询价详情', moduleCode: 'SCM', businessObject: 'PurchaseInquiry',
    route: '/scm/purchase-inquiry/detail/:inquiryNo',
    routePattern: /^\/scm\/purchase-inquiry\/detail\/[^/]+$/,
    tableId: 'purchase_inquiry', schema: 'PurchaseInquirySchema', pageType: 'business_detail',
  }),
  Object.freeze({
    pageCode: 'purchase-inquiry-edit', pageName: '编辑询价', moduleCode: 'SCM', businessObject: 'PurchaseInquiry',
    route: '/scm/purchase-inquiry/edit/:inquiryNo',
    routePattern: /^\/scm\/purchase-inquiry\/edit\/[^/]+$/,
    tableId: 'purchase_inquiry', schema: 'PurchaseInquirySchema', pageType: 'business_form',
  }),
  Object.freeze({
    pageCode: 'purchase-inquiry-acceptance', pageName: '询价下一流程验收', moduleCode: 'SCM', businessObject: 'PurchaseInquiry',
    route: '/scm/purchase-inquiry/acceptance/:inquiryNo',
    routePattern: /^\/scm\/purchase-inquiry\/acceptance\/[^/]+$/,
    tableId: 'purchase_inquiry', schema: 'PurchaseInquirySchema', pageType: 'business_acceptance',
  }),
  Object.freeze({
    pageCode: 'price-approval',
    pageName: '采购核价',
    moduleCode: 'SCM',
    businessObject: 'PriceApproval',
    route: '/scm/price-approval',
    routePattern: /^\/scm\/price-approval(?:s|\/[^/]+)?$/,
    tableId: 'price_approval',
    schema: 'PriceApprovalSchema',
    pageType: 'business_list',
  }),
  Object.freeze({
    pageCode: 'agreed-price-purchase-foundation',
    pageName: '既定价格采购',
    moduleCode: 'SCM',
    businessObject: 'PurchaseRequest',
    route: '/scm/purchase-request/agreed-price',
    routePattern: /^\/scm\/purchase-request\/agreed-price$/,
    tableId: 'supplier_material_price',
    schema: 'PurchaseRequestSchema',
    pageType: 'business_form',
  }),
  Object.freeze({
    pageCode: 'agreed-price-purchase-confirmation',
    pageName: '既定价格采购确认',
    moduleCode: 'SCM',
    businessObject: 'PurchaseRequest',
    route: '/scm/purchase-request/:id/agreed-price-confirmation',
    routePattern: /^\/scm\/purchase-request\/[^/]+\/agreed-price-confirmation$/,
    tableId: 'supplier_material_price',
    schema: 'PurchaseOrderSchema',
    pageType: 'business_form',
  }),
  Object.freeze({
    pageCode: 'purchase-order-create',
    pageName: '直接采购工作台',
    moduleCode: 'SCM',
    routePattern: /^\/scm\/purchase-order\/create$/,
    route: '/scm/purchase-order/create',
    tableId: 'purchase_order',
    schema: 'PurchaseOrderSchema',
    pageType: 'business_form',
  }),
  Object.freeze({
    pageCode: 'purchase-order',
    pageName: '采购订单',
    moduleCode: 'SCM',
    routePattern: /^\/scm\/purchase-order(?:s|\/[^/]+)?$/,
    route: '/scm/purchase-orders',
    tableId: 'purchase_order',
    schema: 'PurchaseOrderSchema',
    pageType: 'business_list',
  }),
]

const SCM_PAGE_IDENTITIES = Object.freeze(SCM_PAGE_IDENTITY_DEFINITIONS.map(definition => {
  const name = resolveBusinessName({ pageCode: definition.pageCode, route: definition.route })
  return Object.freeze({ ...definition, pageName: name?.pageTitle || definition.pageName })
}))

export function listScmPageIdentityDefinitions() {
  return SCM_PAGE_IDENTITIES.map(({ routePattern, ...definition }) => ({ ...definition }))
}

export function resolveScmPageIdentity(routePath = '') {
  const normalized = String(routePath || '').split('?')[0]
  const definition = SCM_PAGE_IDENTITIES.find((item) => item.routePattern.test(normalized))
  if (!definition) return null
  const { routePattern, ...identity } = definition
  return { ...identity }
}
import { resolveBusinessName } from '../../governance/businessNameRegistry.js'
