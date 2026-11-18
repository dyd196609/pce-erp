import { MES_ENTRY_PAGE,MES_ENTRY_FILTERS,MES_ENTRY_SEARCH } from './mesExecutionEntryContract.js'
import { FINISHED_GOODS_PAGE,FINISHED_GOODS_FILTERS,FINISHED_GOODS_SEARCH_FIELDS,FINISHED_GOODS_ACTIONS } from './finishedGoodsContract.js'
import { OPERATION_REPORT_PAGE, OPERATION_REPORT_FILTERS, OPERATION_REPORT_SEARCH_FIELDS } from './operationReportContract.js'
import { OPERATION_COMPLETION_PAGE, OPERATION_COMPLETION_FILTERS, OPERATION_COMPLETION_SEARCH_FIELDS } from './operationCompletionContract.js'
import { OPERATION_HANDOVER_PAGE, OPERATION_HANDOVER_FILTERS, OPERATION_HANDOVER_SEARCH_FIELDS, OPERATION_HANDOVER_ACTION_CONTRACTS } from './operationHandoverContract.js'
import { listBusinessProcessSteps } from '../process/businessProcessRegistry.js'
import {
  FINANCE_PROCESS_STRUCTURE_VERSION,
  findFinanceProcessPage,
} from '../process/financeProcessPageRegistry.js'
import { listPceBusinessModules } from './pceBusinessModuleRegistry.js'
import { listPceWideTableContracts } from './pceUiBaseline.js'
import {
  PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
  PCE_WEB_ACCEPTANCE_STRICT_MIGRATION_VERSION,
  createPceWebAcceptanceContract,
  createStandardListAcceptanceContract,
} from './pceWebAcceptanceContract.js'
import { resolveScm7GateListContract } from '../schema/scm/scm7GateListContracts.js'
import { findPdePageDefinition } from '../pages/pdePageDefinitions.js'

export const PAGE_ACCEPTANCE_REGISTRY_VERSION = PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION

export const PCE_MODULE_CATALOG = Object.freeze([
  ['SALES', '销售管理'],
  ['ERP', '企业资源计划'], ['CRM', '客户关系管理'], ['SCM', '供应链管理'], ['WMS', '仓库管理'],
  ['MRP', '物料需求计划'], ['MPS', '主生产计划'], ['APS', '高级计划排程'], ['MES', '制造执行'],
  ['QMS', '质量管理'], ['BI', '商业智能'], ['FDM', '财务数据管理'], ['PFM', '绩效财务管理'],
  ['KPI', '关键绩效指标'], ['FIN', '财务管理'], ['SYS', '系统公共页面'],
].map(([moduleCode, moduleName]) => ({
  moduleCode,
  moduleName,
  moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1',
})))

const SYSTEM_PAGES = [
  ['account-shortcuts', '快捷登录账户', '/account-shortcuts', 'AccountShortcuts', 'src/meta/pages/AccountShortcutsPage.vue', 'diagnostic'],
  ['sales-orders', '销售订单工作台', '/sales/orders', 'SalesOrders', 'src/meta/pages/SalesOrderPage.vue', 'list'],
  ['planning-requirements', '订单计划工作台', '/planning/requirements', 'PlanningRequirements', 'src/meta/pages/PlanningCenterPage.vue', 'list'],
  ['system-login', '账户登录', '/system-login', 'SystemLogin', 'src/views/Login.vue', 'diagnostic'],
  ['system-onboarding', '系统引导', '/onboarding', 'OnboardingPage', 'src/meta/pages/OnboardingPage.vue', 'preview'],
  ['system-pricing', '版本与定价', '/pricing', 'PricingPage', 'src/meta/pages/PricingPage.vue', 'preview'],
  ['system-dashboard', '企业驾驶舱', '/dashboard', 'EnterpriseDashboard', 'src/meta/pages/EnterpriseOSPage.vue', 'diagnostic'],
  ['system-process-center', '业务流程中心', '/process-center', 'BusinessProcessCenter', 'src/meta/pages/EnterpriseOSPage.vue', 'diagnostic'],
  ['system-process-designer', '流程设计中心', '/process-designer', 'ProcessDesigner', 'src/meta/pages/ProcessDesignerPage.vue', 'diagnostic'],
  ['system-work-center', '工作中心', '/work-center', 'WorkCenter', 'src/meta/pages/EnterpriseOSPage.vue', 'approval'],
  ['system-analytics', '经营分析', '/analytics', 'EnterpriseAnalytics', 'src/meta/pages/EnterpriseOSPage.vue', 'diagnostic'],
  ['system-admin', '系统管理', '/admin', 'SystemAdministration', 'src/meta/pages/EnterpriseOSPage.vue', 'diagnostic'],
]

const PDE_DIAGNOSTIC_PAGES = [
  ['pde-order-engineering-calculation', '工程核算 / 物料核算', '/pde/engineering-calculations', 'PdeOrderEngineeringCalculation', 'src/meta/pages/PdeOrderEngineeringCalculationPage.vue', 'diagnostic'],
  ['pce-foundation-wave2', '制造结构与工艺基础验收', '/pde/wave2-manufacturing-foundation', 'ManufacturingStructureWave2', 'src/meta/pages/ManufacturingStructureWave2Page.vue', 'diagnostic'],
]

const CROSS_FUNCTIONAL_REVIEW_PAGES = [
  ['CRM', 'crm-order-reviews', '订单评审', '/sales/order-reviews', 'CrmOrderReviews'],
  ['PDE', 'pde-product-requirement-reviews', '生产可行性评审', '/pde/product-requirement-reviews', 'PdeProductRequirementReviews'],
]

const FOUNDATION_VALIDATION_PAGES = [
  ['foundation-manufacturing-import-preview', '制造基础数据导入预览', '/foundation/import-preview', 'FoundationManufacturingImportPreview', 'src/meta/pages/FoundationManufacturingImportPreviewPage.vue', 'preview'],
]

const FILTER_LABELS = {
  requestNo: '申请编号', requesterId: '申请人', requestDepartment: '申请部门', demandDepartment: '需求部门',
  status: '业务状态', validationStatus: '校验状态', approvalStatus: '审批状态',
  nextStepReadiness: '下游资格', supplierName: '供应商', customerName: '客户',
  legalEntityName: '法人', companyName: '公司', factoryName: '工厂', departmentName: '部门',
  ledgerBookId: '账簿', currency: '币种', amountMin: '金额最小值', amountMax: '金额最大值',
  createdDateFrom: '创建日期起', createdDateTo: '创建日期止',
  plannedDateFrom: '计划日期起', plannedDateTo: '计划日期止',
  sourceModule: '来源模块', blockingType: '异常或阻断类型',
}

function chineseFilterLabel(field = {}) {
  const key = field.field || field.key || ''
  if (FILTER_LABELS[key]) return FILTER_LABELS[key]
  const original = String(field.label || '')
  if (original && /[\u4e00-\u9fff]/.test(original)) return original
  if (/no$/i.test(key)) return '业务编号'
  if (/date|time/i.test(key)) return '业务日期'
  if (/amount|quantity/i.test(key)) return '数值范围'
  if (/status|state|readiness/i.test(key)) return '业务状态'
  if (/supplier/i.test(key)) return '供应商'
  if (/customer/i.test(key)) return '客户'
  return '业务条件'
}

function filterSchemaFor(moduleRecord) {
  return (moduleRecord.advancedFilterSchema || []).map(field => ({
    field: field.field || field.key,
    key: field.key || field.field,
    label: field.label,
    type: field.type,
    displayMap: { ...(field.displayMap || {}) },
    optionsProvider: field.optionsProvider,
    controlType: field.type,
    applicable: true,
    reason: '',
  }))
}

function listContractsFor(moduleRecord, tableContracts) {
  const scmTargetContract = resolveScm7GateListContract(moduleRecord.moduleId)
  const matches = tableContracts.filter(table => (
    table.moduleId === moduleRecord.moduleId
    || table.pageRoute === moduleRecord.route
    || table.sourceFile === moduleRecord.pageComponent
  ))
  const source = matches.length ? matches : [{
    tableId: `${moduleRecord.moduleId}-main`,
    canonicalName: moduleRecord.canonicalName,
    searchableFields: moduleRecord.searchableFields,
    advancedFilterFields: moduleRecord.advancedFilterFields,
    primaryBusinessNoColumn: moduleRecord.primaryBusinessNoField,
    fixedLeftColumns: ['selection', 'index'],
    fixedRightColumns: ['operation'],
  }]
  return source.map(table => createStandardListAcceptanceContract({
    listId: table.tableId,
    listTitle: `${table.canonicalName || moduleRecord.canonicalName}列表`,
    quickSearchFields: scmTargetContract?.searchFields || table.searchableFields || moduleRecord.searchableFields,
    advancedFilterSchema: scmTargetContract
      ? scmTargetContract.filterSchema.map(field => ({ ...field, type: field.filterType, controlType: field.filterType, applicable: true, reason: '' }))
      : filterSchemaFor(moduleRecord),
    columnSchema: [
      { key: 'selection', label: '选择', fixed: 'left' },
      { key: 'index', label: '序号', fixed: 'left' },
      { key: table.primaryBusinessNoColumn || moduleRecord.primaryBusinessNoField || 'businessNo', label: table.primaryBusinessNoLabel || '业务编号' },
      { key: 'operation', label: '操作', fixed: 'right' },
    ],
    rowKey: table.primaryBusinessNoColumn || moduleRecord.primaryBusinessNoField || 'id',
    multiSelect: table.selectionColumnRequired !== false,
    stickyLeftColumns: table.fixedLeftColumns || ['selection', 'index'],
    stickyRightColumns: table.fixedRightColumns || ['operation'],
    horizontalScrollbar: true,
    singleScrollOwner: true,
    exportSupported: true,
    importSupported: false,
    importUnsupportedReason: '当前业务页面仅开放服务端受控操作，不支持直接批量导入',
  }))
}

function processContract(step, stepsById) {
  const previous = stepsById.get(step?.previousStepId)
  const next = stepsById.get(step?.defaultNextStepId)
  return {
    previousModuleCode: previous?.stepId || null,
    previousCanonicalName: previous?.pageTitle || '',
    previousRoute: previous?.routePath || '',
    currentModuleCode: step?.stepId || null,
    currentCanonicalName: step?.pageTitle || '',
    currentRoute: step?.routePath || '',
    nextModuleCode: next?.stepId || null,
    nextCanonicalName: next?.pageTitle || '',
    nextRoute: next?.routePath || '',
  }
}

export function buildPageAcceptanceRegistry() {
  const modules = listPceBusinessModules()
  const steps = listBusinessProcessSteps()
  const stepsById = new Map(steps.map(step => [step.stepId, step]))
  for (const step of steps) stepsById.set(step.moduleId, step)
  const tableContracts = listPceWideTableContracts()
  const businessPages = modules.map(moduleRecord => {
    const step = stepsById.get(moduleRecord.moduleId)
    const financePage = findFinanceProcessPage(moduleRecord.moduleId)
    const declaredPageType = ({
      business_form: 'create', business_list: 'list', business_detail: 'detail',
    })[moduleRecord.pageType] || moduleRecord.pageType
    const pageType = ['list', 'detail', 'create', 'edit', 'approval', 'plan', 'preview', 'diagnostic']
      .includes(declaredPageType) ? declaredPageType : 'list'
    return createPceWebAcceptanceContract({
      moduleCode: financePage?.moduleCode || moduleRecord.moduleCode,
      moduleLayoutVersion: moduleRecord.moduleCode === 'FIN'
        ? FINANCE_PROCESS_STRUCTURE_VERSION
        : 'PCE-MODULE-LAYOUT-V1.1',
      pageCode: moduleRecord.moduleId,
      pageType,
      canonicalName: moduleRecord.canonicalName,
      route: moduleRecord.route,
      routeName: step?.routeName || moduleRecord.moduleId,
      component: moduleRecord.pageComponent,
      businessVersion: financePage?.runtimeBusinessVersion || step?.introducedInVersion || 'registered-current-business-version',
      acceptanceMigrationVersion: financePage ? PCE_WEB_ACCEPTANCE_STRICT_MIGRATION_VERSION : '',
      enforcementMode: financePage ? 'strict' : 'audit',
      acceptanceLevel: financePage ? 5 : 0,
      moduleFramework: financePage ? 'financeProcessPageRegistry' : 'pceBusinessModuleRegistry',
      inheritanceContract: financePage ? {
        systemFramework: financePage.outerShellComponent,
        moduleFramework: 'financeProcessPageRegistry',
        pageTypeFramework: 'list',
        pageBusinessContract: moduleRecord.moduleId,
      } : {},
      process: processContract(step, stepsById),
      buttonWhitelist: [...(step?.primaryActionCodes || []), ...(step?.secondaryActionCodes || [])],
      stateButtonMatrix: financePage ? [{
        state: 'server-derived',
        allowedActions: [...(step?.primaryActionCodes || []), ...(step?.secondaryActionCodes || [])],
        forbiddenActions: ['create-downstream-on-navigation'],
      }] : [],
      listContracts: pageType === 'list' ? listContractsFor(moduleRecord, tableContracts) : [],
      dataProtectionContract: {
        downstreamZeroObjectRequirements: ['payment-order-prepare', 'payment-order-draft', 'formal-payment-order'].includes(moduleRecord.moduleId)
          ? ['formalPaymentOrderDrafts', 'formalPaymentOrders', 'paymentExecutions', 'paymentVouchers', 'ledgerEntries', 'bankTransactions']
          : [],
      },
    })
  })
  const systemPages = SYSTEM_PAGES.map(([pageCode, canonicalName, route, routeName, component, pageType]) => (
    createPceWebAcceptanceContract({
      moduleCode: 'SYS',
      pageCode,
      pageType,
      canonicalName,
      route,
      routeName,
      component,
      businessVersion: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
      process: {
        currentModuleCode: 'SYS',
        currentCanonicalName: canonicalName,
        currentRoute: route,
      },
      listContracts: pageType === 'list' ? listContractsFor({
        moduleId: pageCode, canonicalName, route, pageComponent: component,
        searchableFields: ['orderNo', 'customerName', 'projectReference', 'materialCode'],
        advancedFilterFields: ['status', 'customerName', 'departmentName', 'orderDate'],
        primaryBusinessNoField: 'orderNo',
        advancedFilterSchema: [
          { field: 'status', label: '业务状态', type: 'select' },
          { field: 'customerName', label: '客户', type: 'text' },
          { field: 'departmentName', label: '销售组织', type: 'text' },
          { field: 'orderDate', label: '订单日期', type: 'daterange' },
        ],
      }, tableContracts) : [],
      responsiveContract: { operationColumnAlwaysVisible: false },
    })
  ))
  const pdeDiagnosticPages = PDE_DIAGNOSTIC_PAGES.map(([pageCode, canonicalName, route, routeName, component, pageType]) => (
    createPceWebAcceptanceContract({
      moduleCode: 'PDE',
      moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1',
      pageCode,
      pageType,
      canonicalName,
      route,
      routeName,
      component,
      businessVersion: 'PCE-A1.9-DO1-V1.0',
      enforcementMode: 'audit',
      acceptanceLevel: 0,
      moduleFramework: 'pcePageAcceptanceRegistry',
      process: {
        previousModuleCode: 'pde-product-requirements',
        previousCanonicalName: '客户订单需求',
        previousRoute: '/pde/product-requirements',
        currentModuleCode: pageCode,
        currentCanonicalName: canonicalName,
        currentRoute: route,
        nextModuleCode: 'pde-product-requirement-reviews',
        nextCanonicalName: '生产可行性评审',
        nextRoute: '/pde/product-requirement-reviews',
      },
      buttonWhitelist: [],
      responsiveContract: { operationColumnAlwaysVisible: false },
      dataProtectionContract: { downstreamZeroObjectRequirements: ['EngineeringCalculationRecord'] },
    })
  ))
  const foundationValidationPages = FOUNDATION_VALIDATION_PAGES.map(([pageCode, canonicalName, route, routeName, component, pageType]) => (
    createPceWebAcceptanceContract({
      moduleCode: 'PDE',
      moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1',
      pageCode,
      pageType,
      canonicalName,
      route,
      routeName,
      component,
      businessVersion: 'PCE-FOUNDATION-WAVE1-PREVIEW-V1.0',
      enforcementMode: 'audit',
      acceptanceLevel: 0,
      moduleFramework: 'pcePageAcceptanceRegistry',
      process: {
        previousModuleCode: 'enterprise-foundation-operator-portal',
        previousCanonicalName: '企业基础资料',
        previousRoute: '/foundation',
        currentModuleCode: pageCode,
        currentCanonicalName: canonicalName,
        currentRoute: route,
      },
      buttonWhitelist: ['production.master_data.view'],
      responsiveContract: { operationColumnAlwaysVisible: false },
      dataProtectionContract: {
        downstreamZeroObjectRequirements: ['Material', 'UnitOfMeasure', 'ProductDefinition', 'Process', 'Workshop', 'WorkCenter'],
      },
    })
  ))
  const crossFunctionalReviewPages = CROSS_FUNCTIONAL_REVIEW_PAGES.map(([moduleCode, pageCode, canonicalName, route, routeName]) => (
    createPceWebAcceptanceContract({
      moduleCode, moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1', pageCode,
      pageType: 'approval', canonicalName, route, routeName,
      component: 'src/meta/pages/CrossFunctionalReviewPage.vue',
      businessVersion: 'PCE-FLOW-REVIEW-SEPARATION-V1.0', enforcementMode: 'audit', acceptanceLevel: 0,
      moduleFramework: 'pcePageAcceptanceRegistry',
      process: { currentModuleCode: pageCode, currentCanonicalName: canonicalName, currentRoute: route },
      buttonWhitelist: moduleCode === 'CRM' ? ['sales.order.view', 'sales.order.update'] : ['production.master_data.view', 'production.engineering.readiness.maintain'],
      responsiveContract: { operationColumnAlwaysVisible: false },
    })
  ))
  const pdeFormalReadPages = ['manufacturingAdmissions', 'mrpInputPreparation'].map(kind => {
    const page = findPdePageDefinition(kind)
    return createPceWebAcceptanceContract({
      moduleCode: 'PDE', moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1',
      pageCode: page.pageCode, pageType: 'list', canonicalName: page.title,
      route: page.governance.navigation.current.pageUrl,
      routeName: kind === 'manufacturingAdmissions' ? 'PdeManufacturingAdmissions' : 'PdeMrpInputPreparation',
      component: 'src/meta/pages/PdeFoundationPage.vue', businessVersion: page.governance.version,
      moduleFramework: 'pdePageDefinitions', enforcementMode: 'audit', acceptanceLevel: 0,
      process: { currentModuleCode: page.pageCode, currentCanonicalName: page.title,
        currentRoute: page.governance.navigation.current.pageUrl,
        previousCanonicalName: page.governance.navigation.previous.label,
        previousRoute: page.governance.navigation.previous.pageUrl,
        nextCanonicalName: page.governance.navigation.next.label,
        nextRoute: page.governance.navigation.next.pageUrl },
      buttonWhitelist: [],
      listContracts: listContractsFor({moduleId: page.pageCode, canonicalName: page.title,
        primaryBusinessNoField: page.primaryField, searchableFields: page.searchFields,
        advancedFilterFields: page.filterSchema.map(field => field.field),
        advancedFilterSchema: page.filterSchema.map(field => ({...field, key: field.field, type: field.filterType}))}, tableContracts),
      dataProtectionContract: {downstreamZeroObjectRequirements: ['Demand', 'PlanningRequirement', 'ApprovalTask']},
    })
  })
  const operationReportPage = createPceWebAcceptanceContract({
    moduleCode: OPERATION_REPORT_PAGE.moduleCode, moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1',
    pageCode: OPERATION_REPORT_PAGE.pageCode, pageType: 'list', canonicalName: OPERATION_REPORT_PAGE.title,
    route: OPERATION_REPORT_PAGE.route, routeName: OPERATION_REPORT_PAGE.routeName, component: OPERATION_REPORT_PAGE.component,
    businessVersion: OPERATION_REPORT_PAGE.version, moduleFramework: 'operationReportContract',
    enforcementMode: 'audit', acceptanceLevel: 0,
    process: { previousModuleCode: 'routing-management', previousCanonicalName: '本人任务开工',
      previousRoute: '/pde/routings', currentModuleCode: OPERATION_REPORT_PAGE.moduleId,
      currentCanonicalName: OPERATION_REPORT_PAGE.title, currentRoute: OPERATION_REPORT_PAGE.route },
    buttonWhitelist: ['production.operation.report', 'production.operation.confirm_execution'],
    listContracts: listContractsFor({ moduleId: OPERATION_REPORT_PAGE.moduleId, canonicalName: OPERATION_REPORT_PAGE.title,
      primaryBusinessNoField: 'no', searchableFields: OPERATION_REPORT_SEARCH_FIELDS,
      advancedFilterFields: OPERATION_REPORT_FILTERS.map(field => field.field),
      advancedFilterSchema: OPERATION_REPORT_FILTERS.map(field => ({ ...field, key: field.field, type: field.filterType })) }, tableContracts),
    dataProtectionContract: { downstreamZeroObjectRequirements: ['ProductionCompletion', 'InventoryTransaction', 'ScheduleRelease'] },
  })
  const operationCompletionPage = createPceWebAcceptanceContract({
    moduleCode: OPERATION_COMPLETION_PAGE.moduleCode, moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1',
    pageCode: OPERATION_COMPLETION_PAGE.pageCode, pageType: 'list', canonicalName: OPERATION_COMPLETION_PAGE.title,
    route: OPERATION_COMPLETION_PAGE.route, routeName: OPERATION_COMPLETION_PAGE.routeName, component: OPERATION_COMPLETION_PAGE.component,
    businessVersion: OPERATION_COMPLETION_PAGE.version, moduleFramework: 'operationCompletionContract',
    enforcementMode: 'audit', acceptanceLevel: 0,
    process: { previousModuleCode: OPERATION_REPORT_PAGE.moduleId, previousCanonicalName: OPERATION_REPORT_PAGE.title,
      previousRoute: OPERATION_REPORT_PAGE.route, currentModuleCode: OPERATION_COMPLETION_PAGE.moduleId,
      currentCanonicalName: OPERATION_COMPLETION_PAGE.title, currentRoute: OPERATION_COMPLETION_PAGE.route },
    buttonWhitelist: ['production.operation.complete.request', 'production.operation.complete.approve',
      'production.operation.complete.v3.request', 'production.operation.complete.v3.approve', 'production.operation.complete.withdraw_replace'],
    listContracts: listContractsFor({ moduleId: OPERATION_COMPLETION_PAGE.moduleId, canonicalName: OPERATION_COMPLETION_PAGE.title,
      primaryBusinessNoField: 'no', searchableFields: OPERATION_COMPLETION_SEARCH_FIELDS,
      advancedFilterFields: OPERATION_COMPLETION_FILTERS.map(field => field.field),
      advancedFilterSchema: OPERATION_COMPLETION_FILTERS.map(field => ({ ...field, key: field.field, type: field.filterType })) }, tableContracts),
    dataProtectionContract: { downstreamZeroObjectRequirements: ['InventoryTransaction', 'ScheduleRelease', 'OperationTransfer'] },
  })
  const operationHandoverPage = createPceWebAcceptanceContract({
    moduleCode: OPERATION_HANDOVER_PAGE.moduleCode, moduleLayoutVersion: 'PCE-MODULE-LAYOUT-V1.1',
    pageCode: OPERATION_HANDOVER_PAGE.pageCode, pageType: 'list', canonicalName: OPERATION_HANDOVER_PAGE.title,
    route: OPERATION_HANDOVER_PAGE.route, routeName: OPERATION_HANDOVER_PAGE.routeName, component: OPERATION_HANDOVER_PAGE.component,
    businessVersion: OPERATION_HANDOVER_PAGE.version, moduleFramework: 'operationHandoverContract',
    enforcementMode: 'audit', acceptanceLevel: 0,
    process: { previousModuleCode: OPERATION_REPORT_PAGE.moduleId, previousCanonicalName: OPERATION_REPORT_PAGE.title,
      previousRoute: OPERATION_REPORT_PAGE.route, currentModuleCode: OPERATION_HANDOVER_PAGE.moduleId,
      currentCanonicalName: OPERATION_HANDOVER_PAGE.title, currentRoute: OPERATION_HANDOVER_PAGE.route },
    buttonWhitelist: Object.values(OPERATION_HANDOVER_ACTION_CONTRACTS).map(action => action.actionCode),
    listContracts: listContractsFor({ moduleId: OPERATION_HANDOVER_PAGE.moduleId, canonicalName: OPERATION_HANDOVER_PAGE.title,
      primaryBusinessNoField: 'no', searchableFields: OPERATION_HANDOVER_SEARCH_FIELDS,
      advancedFilterFields: OPERATION_HANDOVER_FILTERS.map(field => field.field),
      advancedFilterSchema: OPERATION_HANDOVER_FILTERS.map(field => ({ ...field, key: field.field, type: field.filterType })) }, tableContracts),
    dataProtectionContract: { downstreamZeroObjectRequirements: ['InventoryTransaction', 'ScheduleRelease', 'ProductionOperationStart'] },
  })
  const finishedGoodsPage=createPceWebAcceptanceContract({moduleCode:'MES',moduleLayoutVersion:'PCE-MODULE-LAYOUT-V1.1',pageCode:FINISHED_GOODS_PAGE.pageCode,pageType:'list',canonicalName:FINISHED_GOODS_PAGE.title,route:FINISHED_GOODS_PAGE.route,routeName:FINISHED_GOODS_PAGE.routeName,component:FINISHED_GOODS_PAGE.component,businessVersion:FINISHED_GOODS_PAGE.version,moduleFramework:'finishedGoodsContract',enforcementMode:'audit',acceptanceLevel:0,process:{previousModuleCode:OPERATION_HANDOVER_PAGE.moduleId,previousCanonicalName:OPERATION_HANDOVER_PAGE.title,previousRoute:OPERATION_HANDOVER_PAGE.route,currentModuleCode:FINISHED_GOODS_PAGE.moduleId,currentCanonicalName:FINISHED_GOODS_PAGE.title,currentRoute:FINISHED_GOODS_PAGE.route},buttonWhitelist:Object.values(FINISHED_GOODS_ACTIONS).map(x=>x.actionCode),listContracts:listContractsFor({moduleId:FINISHED_GOODS_PAGE.moduleId,canonicalName:FINISHED_GOODS_PAGE.title,primaryBusinessNoField:'no',searchableFields:FINISHED_GOODS_SEARCH_FIELDS,advancedFilterFields:FINISHED_GOODS_FILTERS.map(x=>x.field),advancedFilterSchema:FINISHED_GOODS_FILTERS.map(x=>({...x,key:x.field,type:x.filterType}))},tableContracts),dataProtectionContract:{downstreamZeroObjectRequirements:['ScheduleRelease','FormalProductionPlan']}})
  const mesEntryPage=createPceWebAcceptanceContract({moduleCode:'MES',moduleLayoutVersion:'PCE-MODULE-LAYOUT-V1.1',pageCode:MES_ENTRY_PAGE.pageCode,pageType:'list',canonicalName:MES_ENTRY_PAGE.title,route:MES_ENTRY_PAGE.route,routeName:MES_ENTRY_PAGE.routeName,component:MES_ENTRY_PAGE.component,businessVersion:MES_ENTRY_PAGE.version,moduleFramework:'mesExecutionEntryContract',enforcementMode:'audit',acceptanceLevel:0,process:{currentModuleCode:MES_ENTRY_PAGE.moduleId,currentCanonicalName:MES_ENTRY_PAGE.title,currentRoute:MES_ENTRY_PAGE.route},buttonWhitelist:[],listContracts:listContractsFor({moduleId:MES_ENTRY_PAGE.moduleId,canonicalName:MES_ENTRY_PAGE.title,primaryBusinessNoField:'no',searchableFields:MES_ENTRY_SEARCH,advancedFilterFields:MES_ENTRY_FILTERS.map(x=>x.field),advancedFilterSchema:MES_ENTRY_FILTERS.map(x=>({...x,key:x.field,type:x.filterType}))},tableContracts),dataProtectionContract:{downstreamZeroObjectRequirements:['ScheduleRelease','FormalProductionPlan']}})
  const operationReportPageList = [mesEntryPage,finishedGoodsPage,operationReportPage, operationCompletionPage, operationHandoverPage]
  return [...operationReportPageList, ...businessPages, ...pdeDiagnosticPages, ...foundationValidationPages, ...crossFunctionalReviewPages, ...systemPages, ...pdeFormalReadPages]
}

export const pageAcceptanceRegistry = Object.freeze(buildPageAcceptanceRegistry())

export function listPageAcceptanceContracts() {
  return pageAcceptanceRegistry.map(contract => ({
    ...contract,
    process: { ...contract.process },
    listContracts: contract.listContracts.map(list => ({ ...list })),
  }))
}

export function findPageAcceptanceContract(routeOrPageCode = '') {
  const value = String(routeOrPageCode).split('?')[0]
  return pageAcceptanceRegistry.find(contract => contract.route === value || contract.pageCode === value) || null
}

export function summarizePageAcceptanceRegistry() {
  const pages = listPageAcceptanceContracts()
  return {
    contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
    registryVersion: PAGE_ACCEPTANCE_REGISTRY_VERSION,
    totalModuleCount: PCE_MODULE_CATALOG.length,
    totalPageCount: pages.length,
    registeredPageCount: pages.length,
    unregisteredPageCount: 0,
    businessPageCount: pages.filter(page => page.moduleCode !== 'SYS').length,
    systemPageCount: pages.filter(page => page.moduleCode === 'SYS').length,
    pageTypeSummary: pages.reduce((summary, page) => {
      summary[page.pageType] = (summary[page.pageType] || 0) + 1
      return summary
    }, {}),
  }
}
