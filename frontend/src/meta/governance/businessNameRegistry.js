import { MES_ENTRY_PAGE } from '../runtime/mesExecutionEntryContract.js'
import { WORKSHOP_TASK_PAGE } from '../runtime/workshopTaskDispatchContract.js'
import { OPERATION_START_PAGE } from '../runtime/operationStartContract.js'
import { FINISHED_GOODS_PAGE } from '../runtime/finishedGoodsContract.js'
import { OPERATION_REPORT_PAGE } from '../runtime/operationReportContract.js'
import { OPERATION_COMPLETION_PAGE } from '../runtime/operationCompletionContract.js'
import { OPERATION_HANDOVER_PAGE } from '../runtime/operationHandoverContract.js'
import { foundationCanonicalModules } from '../master-data/foundationEntryUnificationRegistry.js'

export const BUSINESS_NAME_REGISTRY_VERSION = 'V1.14.2.8.4.27.2.42'
export const NAME_GOV_001 = Object.freeze({ ruleCode: 'NAME-GOV-001', ruleName: '业务名称唯一来源规范' })
export const NAME_GOV_002 = Object.freeze({ ruleCode: 'NAME-GOV-002', ruleName: '全局业务名称覆盖扫描规范' })

// PCE BUSINESS UI CHINESE DISPLAY CONTRACT: canonical values remain in the
// API/database; business pages project them through this single registry.
export const PCE_BUSINESS_UI_CHINESE_DISPLAY_CONTRACT_VERSION = 'V1.0'
export const BUSINESS_UI_LABELS = Object.freeze({
  uom: '计量单位', makeBuy: '自制/采购', dataProvenance: '数据来源', materialType: '物料类型',
})
export const BUSINESS_UI_ENUM_LABELS = Object.freeze({
  MAKE: '自制', BUY: '采购', UNDETERMINED: '待确认', semi: '半成品', raw: '原材料', finished: '成品', auxiliary: '辅料',
  REAL_WHOLE_HOUSE_MATERIAL: '真实整木物料', TEST_HISTORICAL: '测试/历史物料', UNMATCHED: '未匹配',
  POSSIBLE_REAL_OUTSIDE_SOURCE: '可能真实的其它来源', UNKNOWN_OUTSIDE_SOURCE: '来源未知',
  EXACT_MATCH: '精确匹配', ATTRIBUTE_MATCH: '业务属性匹配', NO_MATCH: '缺失', INVALID_SOURCE: '来源不完整',
  USER_EXCLUDED_INCOMPLETE_SOURCE: '用户排除的不完整来源', CONFLICT: '冲突', PRESENT: '已存在', MISSING: '缺失',
  STANDARD: '标准产品', TEMPLATE_ASSISTED: '模板辅助配置', ORDER_ENGINEERED: '按单工程',
  PENDING_USER_DECISION: '待用户决定', PASS: '通过', PARTIAL: '部分就绪', READY: '就绪',
  MANUAL_VALIDATION_READY: '人工验收页面已准备', UNRESOLVED_LINKAGE: '稳定关联未解决',
  UNRESOLVED_OPERATION: '来源工序未匹配', DEVELOPED: '已开发', NOT_VALIDATED: '等待人工验收',
})
export const businessUiLabel = key => BUSINESS_UI_LABELS[key] || key
export const businessUiEnumLabel = value => BUSINESS_UI_ENUM_LABELS[value] || value || '-'

// The first five fields identify the business page. Every user-visible name is
// projected from canonicalName below so consumers cannot create a second title.
const definitions = [
  ['EnterpriseHome','enterprise-home','本人首页','enterprise-home','/home','SYSTEM','企业操作'],
  [MES_ENTRY_PAGE.businessObject,MES_ENTRY_PAGE.moduleId,MES_ENTRY_PAGE.title,MES_ENTRY_PAGE.pageCode,MES_ENTRY_PAGE.route,'MES','制造运营中心'],
  [WORKSHOP_TASK_PAGE.businessObject,WORKSHOP_TASK_PAGE.moduleId,WORKSHOP_TASK_PAGE.title,WORKSHOP_TASK_PAGE.pageCode,WORKSHOP_TASK_PAGE.route,'MES','制造运营中心'],
  [OPERATION_START_PAGE.businessObject,OPERATION_START_PAGE.moduleId,OPERATION_START_PAGE.title,OPERATION_START_PAGE.pageCode,OPERATION_START_PAGE.route,'MES','制造运营中心'],
  [FINISHED_GOODS_PAGE.businessObject,FINISHED_GOODS_PAGE.moduleId,FINISHED_GOODS_PAGE.title,FINISHED_GOODS_PAGE.pageCode,FINISHED_GOODS_PAGE.route,FINISHED_GOODS_PAGE.moduleCode,'制造运营中心'],
  [OPERATION_REPORT_PAGE.businessObject, OPERATION_REPORT_PAGE.moduleId, OPERATION_REPORT_PAGE.title, OPERATION_REPORT_PAGE.pageCode, OPERATION_REPORT_PAGE.route, OPERATION_REPORT_PAGE.moduleCode, '制造运营中心'],
  [OPERATION_COMPLETION_PAGE.businessObject, OPERATION_COMPLETION_PAGE.moduleId, OPERATION_COMPLETION_PAGE.title, OPERATION_COMPLETION_PAGE.pageCode, OPERATION_COMPLETION_PAGE.route, OPERATION_COMPLETION_PAGE.moduleCode, '制造运营中心'],
  [OPERATION_HANDOVER_PAGE.businessObject, OPERATION_HANDOVER_PAGE.moduleId, OPERATION_HANDOVER_PAGE.title, OPERATION_HANDOVER_PAGE.pageCode, OPERATION_HANDOVER_PAGE.route, OPERATION_HANDOVER_PAGE.moduleCode, '制造运营中心'],

  ['WorkflowProcessDesigner','workflow-process-designer','流程设计中心','workflow-process-designer','/process-designer','SYSTEM'],
  ['SystemConfig','system-config','系统配置','system-config','/admin','SYSTEM'],
  ['SystemRolePermission','system-role-permission','角色权限配置','system-role-permission','/admin/role-permission','SYSTEM'],
  ['SystemMenuConfig','system-menu-config','菜单配置','system-menu-config','/admin/config/menu','SYSTEM'],
  ['SystemProcessTemplate','system-process-template','流程模板配置','system-process-template','/admin/process-template','SYSTEM'],
  ['SystemTenantSetting','system-tenant-setting','租户参数配置','system-tenant-setting','/admin/tenant-setting','SYSTEM'],
  ['AccessControlFoundation','access-control-foundation','组织与权限基础','erp-access-control','/organization','EMD'],
  ['OrganizationDirectory','organization-directory','组织目录','organization-directory-v1','/organization-directory','SYSTEM'],
  ['EnterpriseOrganizationModel','enterprise-organization-model','企业组织经营模型','enterprise-organization-model-v1','/organization-model','SYSTEM'],
  ['EnterpriseDepartmentModel','enterprise-department-model','部门体系','enterprise-department-model-v1','/organization-model/departments','SYSTEM'],
  ['EnterprisePositionModel','enterprise-position-model','岗位与职责体系','enterprise-position-model-v1','/organization-model/positions','SYSTEM'],
  ['MasterDataExecutorDecision','master-data-executor-decision','基础资料执行人确认','master-data-executor-preview','/organization/master-data-executor-preview','SYSTEM'],
  ['ApprovalConfiguration','approval-configuration','审批规则配置','approval-flow-config','/admin/approval-flow-config','SCM'],
  ['PurchaseRequest','purchase-request','采购申请','purchase-request','/scm/purchase-request','SCM'],
  ['AgreedPricePurchaseFoundation','agreed-price-purchase-foundation','既定价格采购','agreed-price-purchase-foundation','/scm/purchase-request/agreed-price','SCM'],
  ['AgreedPricePurchaseConfirmation','agreed-price-purchase-confirmation','既定价格采购确认','agreed-price-purchase-confirmation','/scm/purchase-request/:id/agreed-price-confirmation','SCM'],
  ['PurchaseRequestApproval','purchase-approval','采购审批','purchase-approval','/scm/purchase-approvals','SCM'],
  ['InquiryPreparationContext','inquiry-preparation','询价准备','inquiry-preparation','/scm/inquiry-preparations','SCM'],
  ['PurchaseInquiry','purchase-inquiry','采购询价','purchase-inquiry','/scm/purchase-inquiry','SCM'],
  ['SupplierQuotation','supplier-quote','供应商报价','supplier-quote-workbench','/scm/supplier-quotation','SCM'],
  ['QuoteComparison','quote-comparison','报价比较','quote-comparison-workbench','/scm/quote-comparisons','SCM'],
  ['PriceApprovalPreparation','price-approval','采购核价','price-approval','/scm/price-approval','SCM'],
  ['SupplierRecommendationDecisionBatch','supplier-recommendation','供应商推荐','supplier-recommendation','/scm/supplier-recommendation','SCM'],
  ['PurchaseOrderCreationGateDecision','purchase-order-creation-gate','采购订单准入','purchase-order-gate','/scm/purchase-order-gate','SCM'],
  ['PurchaseOrder','purchase-order','采购订单','purchase-order','/scm/purchase-order','SCM'],
  ['PurchaseOrderDetail','purchase-order-detail','采购订单详情','purchase-order-detail','/scm/purchase-order/:id','SCM'],
  ['PurchaseReceipt','goods-receipt','收货','purchase-receive-preview','/wms/purchase-receive-preview','WMS'],
  ['PurchaseInspection','quality-inspection','来料检验','incoming-inspection','/qms/incoming-inspections','QMS'],
  ['InventoryBalance','inventory-balance','库存余额','inventory-balances','/wms/inventory-balances','WMS'],
  ['MasterDataOrganizations','organization-data','组织数据','master-data-organizations','/master-data/organizations','EMD'],
  ['MasterDataCustomers','customer-data','客户数据','master-data-customers','/master-data/customers','EMD'],
  ['MasterDataSuppliers','supplier-data','供应商数据','master-data-suppliers','/master-data/suppliers','EMD'],
  ['MasterDataMaterials','material-data','物料数据','master-data-materials','/master-data/materials','EMD'],
  ['MasterDataBoms','bom-data','BOM数据','master-data-boms','/master-data/boms','EMD'],
  ['MasterDataRoutings','routing-data','工艺路线','master-data-routings','/master-data/routings','EMD'],
  ['MasterDataWarehouses','warehouse-data','仓库数据','master-data-warehouses','/master-data/warehouses','EMD'],
  ['EnterpriseFoundation','enterprise-foundation','企业基础资料','enterprise-foundation','/foundation','EMD'],
  ['FoundationImportPreview','foundation-manufacturing-import-preview','制造基础数据导入预览','foundation-manufacturing-import-preview','/foundation/import-preview','PDE'],
  ['BaseDataComparison','base-data-comparison-preview','基础数据来源对照','base-data-comparison-preview','/foundation/base-data-comparison/:entity','EMD'],
  ['Group2Comparison','group2-comparison-preview','Group 2基础数据来源对照','group2-comparison-preview','/foundation/group2-comparison/:entity','EMD'],
  ['Group2MaterialTargetedRevalidation','group2-material-targeted-revalidation','物料定向整改人工复验','group2-material-targeted-revalidation','/foundation/group2-material-targeted-revalidation','EMD'],
  ['ManufacturingEngineeringAcceptance','group3-manufacturing-engineering-acceptance','第3组制造工程人工验收','group3-manufacturing-engineering-acceptance','/foundation/group3-acceptance/:entity','PDE'],
  ['OperationTargetedRevalidation','group3a-operation-targeted-revalidation','工序定向复验','group3a-operation-targeted-revalidation','/foundation/group3a-operation-targeted-revalidation','PDE'],
  ['BaseDataReadiness','base-data-manual-acceptance','基础数据人工验收中心','base-data-manual-acceptance-center','/foundation/manual-acceptance-center','EMD'],
  ['ProductionBatch','production-batch-foundation','生产批次与转序排程预览','production-batch-foundation-preview','/planning/production-batch-foundation','PLAN'],
  ['FoundationFormalOperations','formal-operation-data','工序资料','foundation-formal-operations','/foundation/master-data/operations','EMD'],
  ['FoundationFormalRoutings','formal-routing-data','工艺路线','foundation-formal-routings','/foundation/master-data/routings','EMD'],
  ['FoundationFormalRoutingSteps','formal-routing-step-data','路线步骤','foundation-formal-routing-steps','/foundation/master-data/routing-steps','EMD'],
  ['EnterpriseFoundationFormalMaintenance','enterprise-foundation-maintenance','企业基础资料正式维护','enterprise-foundation-master-data','/foundation/master-data/:entity','EMD'],
  ['ProductionFoundationGate','production-foundation-gate','生产基础完整性检查','pce-production-a1','/pde/a1-foundation','PDE'],
  ['ManufacturingStructureWave2','manufacturing-structure-wave2','制造结构与工艺基础验收','pce-foundation-wave2','/pde/wave2-manufacturing-foundation','PDE'],
  ['SalesOrder','sales-order','销售订单工作台','sales-orders','/sales/orders','SALES'],
  ['CrmOrderReview','crm-order-review-page','订单评审','crm-order-reviews','/sales/order-reviews','CRM'],
  ['PlanningRequirement','order-planning-chain','订单计划工作台','planning-requirements','/planning/requirements','MRP'],
  ['FoundationEmployees','employee-data','员工档案','foundation-employees','/foundation/pfm/employees','EMD'],
  ['FoundationMaterials','foundation-material-data','物料档案','foundation-materials','/foundation/erp/materials','EMD'],
  ['FoundationSuppliers','foundation-supplier-data','供应商档案','foundation-suppliers','/foundation/erp/suppliers','EMD'],
  ['FoundationSupplierMaterialPrices','supplier-material-price-data','供应商物料价格','foundation-supplier-material-prices','/foundation/erp/supplier-material-prices','EMD'],
  ['FoundationSupplierPriceFacts','supplier-price-fact-data','供应商价格事实','foundation-supplier-price-facts','/foundation/erp/supplier-price-facts','EMD'],
  ['FoundationSupplierPriceAnalysis','supplier-price-analysis','供应商价格分析','foundation-supplier-price-analysis','/foundation/erp/supplier-price-analysis','EMD'],
  ['PurchasePriceReviewAssistant','price-review-assistant','供应商核价智能辅助','price-review-assistant','/scm/price-review-assistant','SCM'],
  ['FoundationMaterialSuppliers','material-supplier-relation-data','物料供应商关系','foundation-material-suppliers','/foundation/erp/material-suppliers','EMD'],
  ['FoundationProcesses','process-data','工序资料','foundation-processes','/foundation/manufacturing/processes','EMD'],
  ['FoundationRoutings','foundation-routing-data','工艺资料','foundation-routings','/foundation/manufacturing/routings','EMD'],
  ['FoundationEquipment','equipment-data','设备资料','foundation-equipment','/foundation/manufacturing/equipment','EMD'],
  ['PdeProductEngineeringWorkbench','pde-product-engineering-workbench','PDE产品工程工作台','pde-product-engineering-workbench','/pde/workbench','PDE'],
  ['EngineeringCalculationRecord','engineering-material-calculation','工程核算 / 物料核算','pde-order-engineering-calculation','/pde/engineering-calculations','PDE'],
  ['PdeProductRequirements','product-order-demand','客户订单需求','pde-product-requirements','/pde/product-requirements','PDE'],
  ['PdeEngineeringReadiness','engineering-readiness-control','PDE工程准备','pde-engineering-readiness','/pde/engineering-readiness','PDE'],
  ['PdeProductRequirementReviews','product-requirement-review','生产可行性评审','pde-product-requirement-reviews','/pde/product-requirement-reviews','PDE'],
  ['PdeProductDefinitions','product-design-management','产品设计','pde-product-definitions','/pde/product-definitions','PDE'],
  ['PdeProductVersions','product-version-management','产品版本管理','pde-product-versions','/pde/product-versions','PDE'],
  ['PdeBomVersions','bom-version-management','BOM版本管理','pde-bom-versions','/pde/bom-versions','PDE'],
  ['PdeProductBoms','bom-management','BOM管理','pde-product-boms','/pde/product-boms','PDE'],
  ['PdeRoutings','routing-management','工艺路线管理','pde-routings','/pde/routings','PDE','PDE产品研发与工程管理中心'],
  ['PdeRoutingVersions','routing-version-management','工艺路线版本管理','pde-routing-versions','/pde/routing-versions','PDE'],
  ['PdeEngineeringDocuments','engineering-data-release','工程资料发布','pde-engineering-documents','/pde/engineering-documents','PDE'],
  ['PdeEngineeringChanges','engineering-change-ecn','工程变更ECN','pde-engineering-changes','/pde/engineering-changes','PDE'],
  ['PdeTrialProductionValidations','trial-production-validation','试制验证','pde-trial-production-validations','/pde/trial-production-validations','PDE'],
  ['PdeMassProductionIntroductions','mass-production-introduction','量产导入','pde-mass-production-introductions','/pde/mass-production-introductions','PDE'],
  ['PdeManufacturingOutputs','manufacturing-output-confirmation','工程输出确认','pde-manufacturing-outputs','/pde/manufacturing-outputs','PDE'],
  ['SalesOrderManufacturingAdmission','manufacturing-admission-confirmation','制造承接确认','pde-manufacturing-admissions','/pde/manufacturing-admissions','PDE'],
  ['PdeMrpInputSource','mrp-input-preparation','MRP输入准备','pde-mrp-input-preparation','/pde/mrp-input-preparation','PDE'],
  ['SupplierReconciliation','supplier-reconciliation','供应商对账','supplier-reconciliation','/scm/supplier-reconciliations','SCM'],
  ['SupplierReconciliationDifferences','reconciliation-difference','差异分析','supplier-reconciliation-differences','/scm/supplier-reconciliation-differences','SCM'],
  ['SupplierReconciliationConfirmations','supplier-confirmation','供应商确认','supplier-reconciliation-confirmations','/scm/supplier-reconciliation-confirmations','SCM'],
  ['SupplierPayableConfirmation','supplier-payable-confirmation','应付确认','supplier-payable-confirmation','/scm/supplier-payable-confirmations','SCM'],
  ['SupplierPaymentRequest','supplier-payment-request','付款申请','supplier-payment-request','/scm/supplier-payment-requests','SCM'],
  ['SupplierPaymentStatus','payment-status-record','付款状态记录','supplier-payment-status','/scm/supplier-payment-status','SCM'],
  ['SupplierSettlementCompletion','supplier-settlement-completion','供应商结算完成','supplier-settlement-completion','/scm/supplier-settlement-completions','SCM'],
  ['SupplierPerformance','supplier-performance','供应商绩效','supplier-performance','/scm/supplier-performance','SCM'],
  ['BuyerPerformance','buyer-performance','采购员绩效','buyer-performance','/scm/buyer-performance','SCM'],
  ['PurchaseInquiryLegacy','purchase-inquiry-scm-purchase-inquiries','采购询价','purchase-inquiry-scm-purchase-inquiries','/scm/purchase-inquiries','SCM'],
  ['PriceApprovalLegacy','price-approval-scm-price-approvals','采购核价','price-approval-scm-price-approvals','/scm/price-approvals','SCM'],
  ['PurchaseOrderLegacy','purchase-order-scm-purchase-orders','采购订单','purchase-order-scm-purchase-orders','/scm/purchase-orders','SCM'],
  ['PayablePrepare','payable-prepare','采购应付预备','payable-prepare','/finance/payable-prepares','FIN'],
  ['PayableCheck','payable-check','采购应付核对','payable-check','/finance/payable-checks','FIN'],
  ['SupplierSettlement','supplier-settlement','供应商结算','supplier-settlement','/scm/supplier-settlements','SCM'],
  ['PurchaseReconciliation','purchase-reconciliation','采购对账','purchase-reconciliation','/scm/purchase-reconciliations','SCM'],
  ['InvoicePrepare','invoice-prepare','采购发票准备','invoice-prepare','/finance/purchase-invoice-prepares','FIN'],
  ['AccountPayableDraft','account-payable-draft','采购应付账款草稿','account-payable-draft','/finance/ap-drafts','FIN'],
  ['AccountPayableConfirm','account-payable-confirm','应付确认准备','account-payable-confirm','/finance/account-payable-confirms','FIN'],
  ['PaymentApplication','payment-application','付款申请准备','payment-application','/finance/payment-applications','FIN'],
  ['PaymentRequest','payment-request','付款申请','payment-request','/finance/payment-requests','FIN'],
  ['PaymentInstructionPrepare','payment-instruction-prepare','付款指令准备','payment-instruction-prepare','/finance/payment-order-prepares','FIN'],
  ['PaymentOrderPrepare','payment-order-prepare','正式付款单预备','payment-order-prepare','/finance/payment-prepares','FIN'],
  ['PaymentOrderDraft','payment-order-draft','正式付款单草稿','payment-order-draft','/finance/payment-order-drafts','FIN'],
  ['PaymentRiskReview','payment-risk-review','真实付款风险评审','payment-risk-review','/finance/payment-risk-reviews','FIN'],
  ['FormalPaymentOrder','formal-payment-order','正式付款单','formal-payment-order','/finance/formal-payment-orders','FIN'],
  ['BankSendPreparation','bank-send-preparation','银行发送准备','bank-send-preparation','/finance/bank-send-prepares','FIN'],
  ['BankSendTask','bank-send-task','银行发送任务','bank-send-task','/finance/bank-send-tasks','FIN'],
  ['BankSendExecutionGate','bank-send-execution-gate','银行发送执行授权','bank-send-execution-gate','/finance/bank-send-execution-gates','FIN'],
  ['BankSendRequest','bank-send-request','银行发送请求准备','bank-send-request','/finance/bank-send-requests','FIN'],
  ['BankSendSimulation','bank-send-simulation','银行发送执行模拟','bank-send-simulation','/finance/bank-send-simulations','FIN'],
  ['BankSendSimulationAudit','bank-send-simulation-audit','银行发送模拟审计','bank-send-simulation-audit','/finance/bank-send-simulation-audits','FIN'],
  ['BankSendIsolationGate','bank-send-isolation-gate','银行发送生产隔离门禁','bank-send-isolation-gate','/finance/bank-send-isolation-gates','FIN'],
  ['BankSendChainTrace','bank-send-chain-trace','银行发送全链路追踪','bank-send-chain-trace','/finance/bank-send-chain-traces','FIN'],
  ['BankSendFinalApproval','bank-send-final-approval','银行发送最终审批','bank-send-final-approval','/finance/bank-send-final-approvals','FIN'],
  ['BankSendDualIsolationCheck','bank-send-dual-isolation-check','银行发送双重隔离检查','bank-send-dual-isolation-check','/finance/bank-send-dual-isolation-checks','FIN'],
  ['BankSendProductionReleaseReview','bank-send-production-release-review','真实银行发送前生产隔离评审','bank-send-production-release-review','/finance/bank-send-production-release-reviews','FIN'],
  ['BankSendExecutionFrameworkReview','bank-send-execution-framework-review','银行发送执行框架评审','bank-send-execution-framework-review','/finance/bank-send-execution-framework-reviews','FIN'],
  ['BankConnectorAdapterReview','bank-connector-adapter-review','银行接口适配评审','bank-connector-adapter-review','/finance/bank-connector-adapter-reviews','FIN'],
  ['PaymentExecutionPrepare','payment-execution-prepare','付款执行准备','payment-execution-prepare','/finance/payment-execution-prepares','FIN'],
  ['PaymentExecution','payment-execution','付款执行','payment-execution','/finance/payment-executions','FIN'],
  ['PaymentVoucherDraft','payment-voucher-draft','付款凭证草稿','payment-voucher-draft','/finance/payment-voucher-drafts','FIN'],
  ['PaymentVoucherReview','payment-voucher-review','付款凭证复核','payment-voucher-review','/finance/payment-voucher-reviews','FIN'],
  ['PaymentRecordReview','payment-record-review','付款记录复核','payment-record-review','/finance/payment-record-reviews','FIN'],
  ['FormalPaymentVoucher','formal-payment-voucher','正式付款凭证','formal-payment-voucher','/finance/formal-payment-vouchers','FIN'],
  ['PurchaseInquiryAcceptance','purchase-inquiry-acceptance','询价下一流程验收','purchase-inquiry-acceptance','/scm/purchase-inquiry/acceptance/:inquiryNo','SCM'],
  ['PurchaseInquiryDetail','purchase-inquiry-detail','询价详情','purchase-inquiry-detail','/scm/purchase-inquiry/detail/:inquiryNo','SCM'],
  ['PurchaseInquiryEdit','purchase-inquiry-edit','编辑询价','purchase-inquiry-edit','/scm/purchase-inquiry/edit/:inquiryNo','SCM'],
  ['PurchaseOrderCreate','purchase-order-create','直接采购工作台','purchase-order-create','/scm/purchase-order/create','SCM'],
  ['SupplierPaymentDraft','supplier-payment-draft','供应商付款草稿','supplier-payment-draft','/finance/payment-drafts','FIN'],
  ['BuyerExceptionAnalysis','buyer-exception-analysis','采购异常责任分析','buyer-exception-analysis','/scm/buyer-exception-analysis','SCM'],
]

const records = definitions.map(([businessObject, nodeCode, canonicalName, pageCode, route, moduleCode, moduleDisplayName = '']) => Object.freeze({
  businessObject,
  nodeCode,
  processName: canonicalName,
  pageName: canonicalName,
  pageTitle: canonicalName,
  browserTitle: canonicalName,
  displayName: canonicalName,
  pageCode,
  route,
  moduleCode,
  moduleDisplayName,
}))

export const BUSINESS_NAME_REGISTRY = Object.freeze(records)

function normalizeRoute(value = '') {
  return String(value || '').split('?')[0].split('#')[0].replace(/\/$/, '') || '/'
}

function routeMatches(template = '', actual = '') {
  const expectedParts = normalizeRoute(template).split('/').filter(Boolean)
  const actualParts = normalizeRoute(actual).split('/').filter(Boolean)
  return expectedParts.length === actualParts.length
    && expectedParts.every((part, index) => part.startsWith(':') || part === actualParts[index])
}

export function listBusinessNames() {
  return BUSINESS_NAME_REGISTRY.map(item => ({ ...item }))
}

export function resolveBusinessName(input = '') {
  const value = typeof input === 'string' ? input : ''
  const query = typeof input === 'object' && input ? input : {}
  const requestedRoute = query.route || (value.startsWith('/') ? value : '')
  const canonicalModule = foundationCanonicalModules.find(item => requestedRoute && normalizeRoute(item.routePath) === normalizeRoute(requestedRoute))
  if (canonicalModule) return {
    businessObject: canonicalModule.routeName,
    nodeCode: canonicalModule.moduleId,
    processName: canonicalModule.displayName,
    pageName: canonicalModule.displayName,
    pageTitle: canonicalModule.displayName,
    browserTitle: canonicalModule.displayName,
    displayName: canonicalModule.displayName,
    pageCode: canonicalModule.pageKey,
    route: canonicalModule.routePath,
    moduleCode: 'EMD',
    nameSource: 'FoundationCanonicalModuleRegistry',
  }
  const record = BUSINESS_NAME_REGISTRY.find(item => (
    requestedRoute && (normalizeRoute(item.route) === normalizeRoute(requestedRoute) || routeMatches(item.route, requestedRoute))
  ) || item.nodeCode === (query.nodeCode || value)
    || item.pageCode === (query.pageCode || value)
    || item.businessObject === (query.businessObject || value))
  return record ? { ...record } : null
}

export function validateBusinessNameRegistry() {
  const unique = key => new Set(BUSINESS_NAME_REGISTRY.map(item => item[key])).size === BUSINESS_NAME_REGISTRY.length
  const requiredFields = ['businessObject','nodeCode','processName','pageName','pageTitle','browserTitle','displayName','pageCode','route','moduleCode']
  const complete = BUSINESS_NAME_REGISTRY.every(item => requiredFields.every(key => item[key]))
  const aligned = BUSINESS_NAME_REGISTRY.every(item => [item.processName,item.pageName,item.pageTitle,item.browserTitle,item.displayName].every(value => value === item.displayName))
  const uniqueness = unique('nodeCode') && unique('pageCode') && unique('route')
  return Object.freeze({
    result: uniqueness && complete && aligned ? 'PASS' : 'FAIL',
    unique: uniqueness,
    complete,
    aligned,
    recordCount: BUSINESS_NAME_REGISTRY.length,
  })
}
