export const SCM_STANDARD_PAGE_CONTRACT_VERSION = 'V1.14.2.8.18.10.3.1'
export const SCM_STANDARD_PAGE_TEMPLATE = 'PCE Enterprise Page V2'
import {
  listScmProcessFlowPages,
  resolveScmProcessNavigation,
} from '../../process/scmProcessNavigationContract.js'
import { resolveBusinessName } from '../../governance/businessNameRegistry.js'

const FLOW = Object.freeze(listScmProcessFlowPages().map((page) => Object.freeze({
  pageStepId: page.pageCode,
  pageCode: page.pageCode,
  canonicalName: page.pageName,
  pageUrl: page.pageUrl,
  sequence: page.sequence,
})))

const factApiEndpoint = (pageCode) => `/api/procurement/scm-page-facts/${pageCode}/`

const definitions = [
  {
    pageCode: 'purchase-request', pageName: '采购申请', route: '/scm/purchase-request', routePattern: /^\/scm\/purchase-request(?:s|\/[^/]+)?$/,
    businessObject: 'PurchaseRequest', workflowNode: 'purchase-request', schemaId: 'PurchaseRequestSchema', tableId: 'purchase_request',
    sourceObjectType: '逐记录 PurchaseRequest.sourceType', targetObjectType: '逐记录 PurchaseInquiry / PurchaseOrder 正式关系',
    traceAuthority: 'SCM Standard Page Facts API', traceStatus: '服务端逐记录事实',
    purpose: '形成经审批的采购需求，并向询价节点提供可追踪来源。',
    allowedActions: ['查看', '维护草稿', '提交', '审批', '转询价'], forbiddenActions: ['跳过审批生成采购订单', '直接收货', '直接入库', '直接付款', '自动修改历史单据'],
  },
  {
    pageCode: 'approval-flow-config', pageName: '审批规则配置', route: '/admin/approval-flow-config', routePattern: /^\/admin\/approval-flow-config$/,
    businessObject: 'ApprovalConfiguration', workflowNode: 'approval-configuration', schemaId: 'ApprovalContractSchema', tableId: 'approval-flow-config',
    sourceObjectType: 'PurchaseRequest', targetObjectType: 'InquiryPreparationContext',
    purpose: '配置并验证采购申请的一至三级审批关卡；该配置页不代表采购订单审批。',
    allowedActions: ['查看审批关卡', '配置一至三级审批', '保存审批配置'], forbiddenActions: ['作为采购订单审批页', '绕过审批结果回写'],
  },
  {
    pageCode: 'purchase-approval', pageName: '采购审批', route: '/scm/purchase-approvals', routePattern: /^\/scm\/purchase-approvals$/,
    businessObject: 'PurchaseRequestApproval', workflowNode: 'purchase-approval', schemaId: 'PurchaseRequestApprovalSchema', tableId: 'purchase-approval',
    sourceObjectType: 'PurchaseRequest', targetObjectType: 'InquiryPreparationContext',
    purpose: '执行采购申请审批实例和审批任务，并在完成后受控回写采购申请审批状态。',
    allowedActions: ['查看审批策略', '执行当前审批任务', '查看审批结果'], forbiddenActions: ['修改审批规则', '跳过审批关卡', '自动生成询价准备'],
  },
  {
    pageCode: 'inquiry-preparation', pageName: '询价准备', route: '/scm/inquiry-preparations', routePattern: /^\/scm\/inquiry-preparations$/,
    businessObject: 'InquiryPreparationContext', workflowNode: 'inquiry-preparation', schemaId: 'InquiryPreparationSchema', tableId: 'inquiry-preparation-main',
    sourceObjectType: 'PurchaseRequest', targetObjectType: 'PurchaseInquiry',
    purpose: '承接已审批采购申请，核对物料与供应商候选后人工启动询价。',
    allowedActions: ['查看准备事实', '选择准备记录', '启动询价'], forbiddenActions: ['自动创建供应商报价', '自动创建采购订单'],
  },
  {
    pageCode: 'purchase-inquiry', pageName: '询价', route: '/scm/purchase-inquiry', routePattern: /^\/scm\/purchase-inquir(?:ies|y(?:\/[^/]+)?)$/,
    businessObject: 'PurchaseInquiry', workflowNode: 'purchase-inquiry', schemaId: 'PurchaseInquirySchema', tableId: 'purchase_inquiry',
    sourceObjectType: 'PurchaseRequest', targetObjectType: 'PriceApproval',
    purpose: '承接已审批采购申请，记录供应商询价和报价确认。',
    allowedActions: ['查看来源采购申请', '发送询价', '确认报价', '转核价'], forbiddenActions: ['无来源新增询价', '自动生成采购订单'],
  },
  {
    pageCode: 'supplier-quote-workbench', pageName: '供应商报价工作台', route: '/scm/supplier-quotes', routePattern: /^\/scm\/supplier-quotes$/,
    businessObject: 'SupplierQuote', workflowNode: 'supplier-quote', schemaId: 'SupplierQuoteSchema', tableId: 'supplier-quote-main',
    sourceObjectType: 'QuotePreparationContext', targetObjectType: 'QuoteComparisonContext',
    purpose: '承接报价准备事实，人工录入供应商报价并形成比较准备。',
    allowedActions: ['进入供应商报价', '录入报价', '保存报价', '完成报价收集'], forbiddenActions: ['调用供应商接口', '自动生成采购订单'],
  },
  {
    pageCode: 'quote-comparison-workbench', pageName: '报价比较工作台', route: '/scm/quote-comparisons', routePattern: /^\/scm\/quote-comparisons$/,
    businessObject: 'QuoteComparison', workflowNode: 'quote-comparison', schemaId: 'QuoteComparisonSchema', tableId: 'quote-comparison-main',
    sourceObjectType: 'SupplierQuote', targetObjectType: 'SupplierRecommendationContext',
    purpose: '比较供应商报价的价格、交期与有效期事实。',
    allowedActions: ['查看报价事实', '生成报价比较', '保存比较结果'], forbiddenActions: ['自动推荐供应商', '自动创建采购订单'],
  },
  {
    pageCode: 'price-approval', pageName: '采购核价', route: '/scm/price-approval', routePattern: /^\/scm\/price-approval(?:s|\/[^/]+)?$/,
    businessObject: 'PriceApprovalPreparation', workflowNode: 'price-approval', schemaId: 'PriceApprovalPreparationSchema', tableId: 'price_approval_preparation',
    sourceObjectType: 'QuoteComparisonFact', targetObjectType: 'SupplierRecommendationDecisionContext',
    purpose: '承接正式报价比较事实，由采购人员完成人工核价并形成供应商推荐上下文。',
    allowedActions: ['查看报价依据', '生成核价准备', '人工选择供应商', '填写核价意见', '人工核准或驳回'], forbiddenActions: ['自动选择最低报价', '自动推荐供应商', '自动审批', '自动生成采购订单'],
  },
  {
    pageCode: 'supplier-recommendation', pageName: '供应商推荐', route: '/scm/supplier-recommendation', routePattern: /^\/scm\/supplier-recommendation\/?$/,
    businessObject: 'SupplierRecommendationDecisionBatch', workflowNode: 'supplier-recommendation', schemaId: 'SupplierRecommendationDecisionBatchSchema', tableId: 'supplier-recommendation-decision-items',
    sourceObjectType: 'PriceApprovalBatch', targetObjectType: 'PurchaseOrderCreationGateDecision',
    purpose: '承接核价与报价比较批次，由采购人员逐物料选择供应商并批量确认推荐决策。',
    allowedActions: ['查看比较证据', '逐物料选择供应商', '填写推荐理由', '批量确认推荐结果', '进入订单准入'],
    forbiddenActions: ['自动推荐供应商', 'AI自动决策', '自动生成采购订单'],
  },
  {
    pageCode: 'purchase-order-gate', pageName: '采购订单准入', route: '/scm/purchase-order-gate', routePattern: /^\/scm\/purchase-order-gate$/,
    businessObject: 'PurchaseOrderCreationGateDecision', workflowNode: 'purchase-order-creation-gate', schemaId: 'PurchaseOrderGateSchema', tableId: 'purchase-order-gate',
    sourceObjectType: 'SupplierRecommendationDecision', targetObjectType: 'PurchaseOrder',
    purpose: '检查采购订单创建前的推荐、证据、成本与来源链准入条件。',
    allowedActions: ['查看准入事实', '执行准入检查', '创建采购订单请求', '人工确认创建采购订单草稿'],
    forbiddenActions: ['自动创建采购订单', '发布采购订单'],
  },
  {
    pageCode: 'purchase-order', pageName: '采购订单', route: '/scm/purchase-order', routePattern: /^\/scm\/purchase-order(?:s|\/[^/]+)?$/,
    businessObject: 'PurchaseOrder', workflowNode: 'purchase-order', schemaId: 'PurchaseOrderSchema', tableId: 'purchase_order',
    sourceObjectType: 'PriceApproval', targetObjectType: 'PurchaseReceipt',
    purpose: '由已审批核价和采购订单资格承接正式采购执行。',
    allowedActions: ['查看来源核价', '用户确认生成', '提交', '审批', '下达'], forbiddenActions: ['无资格创建', '自动下达', '自动收货'],
  },
  {
    pageCode: 'purchase-receive-preview', pageName: '收货', route: '/wms/purchase-receive-preview', routePattern: /^\/wms\/purchase-receive-preview(?:\/[^/]+)?$/,
    businessObject: 'PurchaseReceipt', workflowNode: 'purchase-receive-preview', schemaId: 'PurchaseReceiveSchema', tableId: 'purchase-receive-preview-main',
    sourceObjectType: 'PurchaseOrder', targetObjectType: 'PurchaseInspection',
    purpose: '按已下达采购订单记录实收数量并形成检验来源。',
    allowedActions: ['查看来源采购订单', '确认收货', '提交检验'], forbiddenActions: ['无订单收货', '直接增加库存'],
  },
  {
    pageCode: 'incoming-inspection', pageName: '质量检验', route: '/qms/incoming-inspections', routePattern: /^\/qms\/incoming-inspection(?:s|\/[^/]+)?$/,
    businessObject: 'PurchaseInspection', workflowNode: 'incoming-inspection', schemaId: 'IncomingInspectionSchema', tableId: 'incoming-inspections-main',
    sourceObjectType: 'PurchaseReceipt', targetObjectType: 'WarehouseInbound',
    purpose: '检验收货对象并为合格数量提供受控入库资格。',
    allowedActions: ['查看来源收货', '记录检验结果', '形成入库预备'], forbiddenActions: ['跳过收货', '不合格直接入库'],
  },
  {
    pageCode: 'inventory-balances', pageName: '入库', route: '/wms/inventory-balances', routePattern: /^\/wms\/(?:inventory-balances|warehouse-tasks)(?:\/[^/]+)?$/,
    businessObject: 'InventoryBalance', workflowNode: 'inventory-balances', schemaId: 'InventoryBalanceSchema', tableId: 'inventory-balances-main',
    sourceObjectType: 'WarehouseInbound', targetObjectType: null,
    purpose: '读取正式库存余额与库存流水；不存在经治理的下游追踪时显示正式空态。',
    allowedActions: ['查看正式库存余额', '查看正式库存流水', '查看来源入库'], forbiddenActions: ['执行入库', '编造下游对账关系', '自动对账'],
  },
]

function navigationFor(index) {
  const resolved = resolveScmProcessNavigation(FLOW[index]?.pageCode)
  return Object.freeze({
    previous: resolved?.previousPage || null,
    current: resolved?.currentPage || null,
    next: resolved?.nextPage || null,
  })
}

const CONTRACTS = Object.freeze(definitions.map((rawDefinition) => {
  const businessName = resolveBusinessName({ pageCode: rawDefinition.pageCode, route: rawDefinition.route })
  const definition = { ...rawDefinition, pageName: businessName?.pageTitle || rawDefinition.pageName }
  const flowIndex = FLOW.findIndex((step) => step.pageCode === definition.workflowNode)
  return Object.freeze({
    ...definition,
    version: SCM_STANDARD_PAGE_CONTRACT_VERSION,
    frameworkVersion: SCM_STANDARD_PAGE_TEMPLATE,
    moduleCode: 'SCM',
    businessModule: 'SCM供应链管理中心',
    apiEndpoint: factApiEndpoint(definition.pageCode),
    factSource: 'server',
    flowSteps: FLOW,
    currentFlowStep: definition.workflowNode,
    navigation: navigationFor(flowIndex),
    allowed: Object.freeze([...definition.allowedActions]),
    forbidden: Object.freeze([...definition.forbiddenActions]),
    dangerousActionCount: 0,
    businessProgressWriteCount: 0,
  })
}))

export function listScmStandardPageContracts() {
  return CONTRACTS.map((contract) => ({ ...contract }))
}

export function resolveScmStandardPageContract(routeOrPageCode = '') {
  const normalized = String(routeOrPageCode || '').split('?')[0]
  const contract = CONTRACTS.find((item) => item.pageCode === normalized || item.routePattern.test(normalized))
  return contract ? { ...contract } : null
}

export function listScmStandardFlowSteps() {
  return FLOW.map((step) => ({ ...step }))
}
