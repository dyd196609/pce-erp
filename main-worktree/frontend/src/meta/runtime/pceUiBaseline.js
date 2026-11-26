import { findPceBusinessModuleById } from './pceBusinessModuleRegistry.js'

export const PCE_UI_BASELINE_VERSION = 'V1.14.2.8.4.4'

export const pceUiBaselineRules = [
  { code: 'moduleCanonicalNameRegistered', severity: 'blocker', description: '每个业务列表页面必须登记唯一 canonicalName。' },
  { code: 'processCenterNameExactMatch', severity: 'blocker', description: '业务流程中心模块名称必须与 canonicalName 完全一致。' },
  { code: 'routeRegistryNameExactMatch', severity: 'blocker', description: '路由身份必须由 BusinessNameRegistry 解析为 canonicalName，禁止使用 route.meta.title 作为第二名称源。' },
  { code: 'browserTitleExactMatch', severity: 'blocker', description: '浏览器 document.title 必须直接使用 canonicalName。' },
  { code: 'pageH1ExactMatch', severity: 'blocker', description: '页面顶部主标题必须与 canonicalName 完全一致。' },
  { code: 'pageInternalTitleExactMatch', severity: 'blocker', description: '页面内部主题标题必须与 canonicalName 完全一致。' },
  { code: 'moduleNameNoAbbreviation', severity: 'blocker', description: '不得使用未登记简称替代标准全名。' },
  { code: 'moduleNameNoLegacyAlias', severity: 'blocker', description: '不得残留旧业务阶段名称。' },
  { code: 'moduleNameAllSurfacesConsistent', severity: 'blocker', description: '流程中心、路由、浏览器标题、页面标题和内部主题必须同名。' },
  { code: 'standardListToolbarRequired', severity: 'blocker', description: '列表页必须提供标准工具栏。' },
  { code: 'fuzzySearchEffective', severity: 'blocker', description: '模糊查找必须接入真实当前结果。' },
  { code: 'advancedFilterEffective', severity: 'blocker', description: '高级筛选必须可展开、可收起、可组合生效。' },
  { code: 'clearFilterEffective', severity: 'blocker', description: '清空筛选必须恢复当前结果。' },
  { code: 'clearSortEffective', severity: 'blocker', description: '清除排序必须恢复默认排序。' },
  { code: 'exportCurrentResultEffective', severity: 'blocker', description: '导出当前结果必须按当前筛选排序结果导出。' },
  { code: 'toolbarAdjacentToTable', severity: 'blocker', description: '工具栏、高级筛选和数据表格必须连续排列。' },
  { code: 'wideTableSingleScrollOwner', severity: 'blocker', description: '宽业务表格只能有一个横向滚动拥有者。' },
  { code: 'selectionColumnRequired', severity: 'blocker', description: '支持批量操作或未来可能支持批量操作的业务列表默认需要选择列。' },
  { code: 'selectionColumnFixedLeft', severity: 'blocker', description: '选择列必须固定在最左侧。' },
  { code: 'selectAllScopeCurrentPage', severity: 'blocker', description: '表头全选默认只表示当前页全选。' },
  { code: 'indexColumnRequired', severity: 'blocker', description: '宽业务列表需要独立序号列。' },
  { code: 'primaryBusinessNoFixedLeft', severity: 'blocker', description: '主业务编号列需要在左侧固定。' },
  { code: 'operationColumnFixedRight', severity: 'blocker', description: '业务记录列表必须具备右侧固定操作列。' },
  { code: 'fixedColumnOpaqueBackground', severity: 'blocker', description: '固定列背景必须不透明，避免普通列穿透。' },
  { code: 'fixedColumnCoordinateStable', severity: 'blocker', description: '固定列在横向滚动前、中、右坐标误差不得超过 1px。' },
  { code: 'finalColumnReachable', severity: 'blocker', description: '表格最后一列必须能到达并完整可见。' },
  { code: 'operationVisibleWithoutScroll', severity: 'blocker', description: '右侧操作入口在无需横向滚动时也应可见。' },
  { code: 'operationClickableAtMaxScroll', severity: 'blocker', description: '最大横向滚动位置下操作按钮仍必须可点击。' },
  { code: 'technicalValueHiddenFromBusinessPage', severity: 'blocker', description: '业务主页面不得泄露内部字段名、英文状态码或 .js 文件名。' },
  { code: 'rawValuePreservedInDiagnostic', severity: 'major', description: '原始技术值需要保留在复制诊断数据中。' },
  { code: 'pageChineseDisplayRequired', severity: 'blocker', description: '业务主展示必须使用中文业务口径。' },
  { code: 'acceptanceMaximumManualChecks', severity: 'blocker', description: '每轮人工复核项目不得超过 3 项。' },
  { code: 'noDuplicateHorizontalScrollbar', severity: 'blocker', description: '同一业务表格不得出现双横向滚动条。' },
  { code: 'noCustomScrollbarWhenNativeBaselineUsed', severity: 'blocker', description: '采用原生基线时不得重新引入自定义蓝色滑块。' },
  { code: 'workflowNavigationReachable', severity: 'blocker', description: '流程导航必须能到达当前业务步骤和后续业务步骤。' },
  { code: 'actionReachabilityRequired', severity: 'blocker', description: '当前业务步骤的主动作、来源查看和下一步入口必须在页面可达。' },
  { code: 'baselineCoverageRegistered', severity: 'blocker', description: '纳入基础操作治理的页面必须登记基线契约或合法例外。' },
  { code: 'developmentAcceptanceCollapsed', severity: 'blocker', description: '开发验收信息必须默认收起，不得隔断业务工具栏与表格。' },
  { code: 'mainSidebarFixedAndCollapsible', severity: 'blocker', description: '软件左侧主菜单必须固定，并支持收起、展开和内容区宽度联动。' },
]

export const pceWideTableDefaults = {
  selectionColumnRequired: true,
  selectionMode: 'multiple',
  selectAllScope: 'current_page',
  showIndexColumn: true,
  fixedLeftColumns: ['selection', 'index', 'primaryBusinessNo'],
  fixedRightColumns: ['operation'],
  scrollOwner: 'element-plus-native',
  allowTechnicalText: false,
  requiresStandardToolbar: true,
  requiresFuzzySearch: true,
  requiresAdvancedFilter: true,
  requiresExportCurrentResult: true,
  operationColumn: 'operation',
  expectedLastColumn: 'operation',
}

function moduleContract(moduleId, overrides = {}) {
  const module = findPceBusinessModuleById(moduleId)
  if (!module) throw new Error(`PCE baseline module not registered: ${moduleId}`)
  return {
    ...pceWideTableDefaults,
    tableId: `${moduleId}-main`,
    moduleId,
    canonicalName: module.canonicalName,
    pageRoute: module.route,
    sourceFile: module.pageComponent,
    searchableFields: module.searchableFields,
    advancedFilterFields: module.advancedFilterFields,
    primaryBusinessNoColumn: module.primaryBusinessNoField,
    primaryBusinessNoLabel: `${module.canonicalName}单号`,
    operationMode: module.operationMode,
    ...overrides,
  }
}

export const pceWideTableContracts = [
  moduleContract('purchase-receive-preview', { tableId: 'purchase-receive-preview-main', primaryBusinessNoColumn: 'receiveNo', primaryBusinessNoLabel: '收货预备单号' }),
  moduleContract('incoming-inspection', { tableId: 'incoming-inspections-main', primaryBusinessNoLabel: '检验单号' }),
  moduleContract('payable-prepare', { tableId: 'payable-prepare-main', primaryBusinessNoLabel: '应付预备单号' }),
  moduleContract('payable-check', { tableId: 'payable-check-main', primaryBusinessNoColumn: 'primaryBusinessNo', primaryBusinessNoLabel: '主业务编号 / 来源编号' }),
  moduleContract('supplier-settlement', { tableId: 'supplier-settlement-main', primaryBusinessNoLabel: '供应商结算单号' }),
  moduleContract('purchase-reconciliation', { tableId: 'purchase-reconciliation-main', primaryBusinessNoLabel: '采购对账编号', operationMode: 'readonly' }),
  moduleContract('invoice-prepare', { tableId: 'invoice-prepare-main', primaryBusinessNoLabel: '发票准备单号' }),
  moduleContract('account-payable-draft', { tableId: 'account-payable-draft-main', primaryBusinessNoLabel: '采购应付账款草稿编号', operationMode: 'workflow' }),
  moduleContract('account-payable-confirm', { tableId: 'account-payable-confirm-main', primaryBusinessNoLabel: '应付确认准备编号' }),
  moduleContract('payment-application', { tableId: 'payment-application-main', primaryBusinessNoLabel: '付款申请准备编号' }),
  moduleContract('payment-instruction-prepare', { tableId: 'payment-instruction-prepare-main', primaryBusinessNoLabel: '付款指令准备编号' }),
  moduleContract('payment-order-prepare', { tableId: 'payment-order-prepare-source', primaryBusinessNoColumn: 'sourcePaymentInstructionPrepareNo', primaryBusinessNoLabel: '付款指令准备编号', canonicalName: '正式付款单预备', pageRoute: '/finance/payment-prepares' }),
  moduleContract('payment-order-prepare', { tableId: 'payment-order-prepare-main', primaryBusinessNoLabel: '正式付款单预备单号' }),
  moduleContract('payment-order-draft', { tableId: 'payment-order-draft-main', primaryBusinessNoColumn: 'draftNo', primaryBusinessNoLabel: '正式付款单草稿编号', canonicalName: '正式付款单草稿', pageRoute: '/finance/payment-order-drafts' }),
  moduleContract('payment-risk-review', { tableId: 'payment-risk-reviews-source', primaryBusinessNoColumn: 'sourcePaymentOrderDraftNo', primaryBusinessNoLabel: '正式付款单草稿号', canonicalName: '真实付款风险评审', pageRoute: '/finance/payment-risk-reviews' }),
  moduleContract('payment-risk-review', { tableId: 'payment-risk-reviews-main', primaryBusinessNoLabel: '风险评审编号', canonicalName: '真实付款风险评审', pageRoute: '/finance/payment-risk-reviews' }),
  moduleContract('supplier-payment-draft', { tableId: 'supplier-payment-draft-source', primaryBusinessNoColumn: 'apDraftNo', primaryBusinessNoLabel: '应付草稿单号', canonicalName: '供应商付款草稿' }),
  moduleContract('supplier-payment-draft', { tableId: 'supplier-payment-draft-main', primaryBusinessNoLabel: '供应商付款草稿单号' }),
  moduleContract('payment-execution-prepare', { tableId: 'payment-execution-prepare-list', primaryBusinessNoLabel: '付款执行准备编号' }),
  moduleContract('payment-execution', { tableId: 'payment-execution-source', primaryBusinessNoColumn: 'riskReviewNo', primaryBusinessNoLabel: '风险评审号' }),
  moduleContract('payment-execution', { tableId: 'payment-execution-main', primaryBusinessNoLabel: '付款执行草稿号' }),
  moduleContract('payment-record-review', { tableId: 'payment-record-review-source', primaryBusinessNoColumn: 'paymentExecutionNo', primaryBusinessNoLabel: '付款执行草稿号' }),
  moduleContract('payment-record-review', { tableId: 'payment-record-review-main', primaryBusinessNoLabel: '付款记录复核单号' }),
  moduleContract('payment-voucher-review', { tableId: 'payment-voucher-review-source', primaryBusinessNoColumn: 'voucherDraftNo', primaryBusinessNoLabel: '付款凭证草稿号' }),
  moduleContract('payment-voucher-review', { tableId: 'payment-voucher-review-main', primaryBusinessNoLabel: '付款凭证复核单号' }),
  moduleContract('bank-send-simulation', {
    tableId: 'bank-send-simulations-main',
    primaryBusinessNoColumn: 'simulationNo',
    primaryBusinessNoLabel: '模拟编号',
  }),
  moduleContract('bank-send-simulation-audit', {
    tableId: 'bank-send-simulation-audits-main',
    primaryBusinessNoColumn: 'auditNo',
    primaryBusinessNoLabel: '审计编号',
  }),
  moduleContract('bank-send-isolation-gate', {
    tableId: 'bank-send-isolation-gates-main',
    primaryBusinessNoColumn: 'gateNo',
    primaryBusinessNoLabel: '门禁编号',
  }),
  moduleContract('bank-send-chain-trace', {
    tableId: 'bank-send-chain-traces-main',
    primaryBusinessNoColumn: 'traceNo',
    primaryBusinessNoLabel: '追踪编号',
  }),
  moduleContract('bank-send-final-approval', {
    tableId: 'bank-send-final-approvals-main',
    primaryBusinessNoColumn: 'approvalNo',
    primaryBusinessNoLabel: '审批编号',
  }),
  moduleContract('bank-send-dual-isolation-check', {
    tableId: 'bank-send-dual-isolation-checks-main',
    primaryBusinessNoColumn: 'checkNo',
    primaryBusinessNoLabel: '检查编号',
  }),
  moduleContract('bank-send-production-release-review', {
    tableId: 'bank-send-production-release-reviews-main',
    primaryBusinessNoColumn: 'reviewNo',
    primaryBusinessNoLabel: '评审编号',
  }),
  moduleContract('bank-send-execution-framework-review', {
    tableId: 'bank-send-execution-framework-reviews-main',
    primaryBusinessNoColumn: 'frameworkNo',
    primaryBusinessNoLabel: '框架编号',
  }),
  moduleContract('bank-connector-adapter-review', {
    tableId: 'bank-connector-adapter-reviews-main',
    primaryBusinessNoColumn: 'interfaceName',
    primaryBusinessNoLabel: '接口名称',
  }),
]

export const pceGoldenPageBaselines = [
  {
    code: 'standard-wide-business-list',
    route: '/finance/payment-execution-prepares',
    tableId: 'payment-execution-prepare-list',
    columnOrder: ['selection', 'index', 'paymentExecutionPrepareNo', 'targetObjectNo', 'paymentExecutionStatus', 'operation'],
    fixedLeftColumns: ['selection', 'index', 'paymentExecutionPrepareNo'],
    fixedRightColumns: ['operation'],
    scrollMode: 'single-native-scroll-owner',
    emptyState: '当前浏览器还没有付款执行准备真实记录。',
    domContract: 'data-acceptance-id + fixed column class names',
  },
  {
    code: 'standard-source-trace-table',
    route: '/finance/payment-voucher-prepare-preview/PEP2026071311191257',
    tableId: 'target-evidence-trace-table',
    expectedLastColumn: '建议检查方向',
    scrollMode: 'single-native-scroll-owner',
    domContract: 'suggestion column after blocking column',
  },
]

export function listPceUiBaselineRules() {
  return pceUiBaselineRules.map((item) => ({ ...item }))
}

export function listPceWideTableContracts() {
  return pceWideTableContracts.map((item) => ({ ...item }))
}

export function listPceGoldenPageBaselines() {
  return pceGoldenPageBaselines.map((item) => ({ ...item }))
}
