import {
  PCE_PAGE_TYPE_PROFILES,
  PCE_PAGE_TYPE_REQUIRED_REGIONS,
} from './pcePageTypeProfiles.js'
import {
  PCE_WRITE_INTENT_CONTRACT_VERSION,
  WriteIntentCategory,
} from './pceWriteIntentContract.js'

export const PCE_WEB_ACCEPTANCE_CONTRACT_VERSION = 'PCE-WEB-ACCEPTANCE-V1.1'
export const PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION = 'V1.14.2.8.4.7.50.2'
export const PCE_WEB_ACCEPTANCE_STRICT_MIGRATION_VERSION = 'V1.14.2.8.4.7.50.3'
export const PCE_PAGE_FRAMEWORK_VERSION = 'PCE-PAGE-FRAMEWORK-V1.1'
export const PCE_OPERATION_FRAMEWORK_VERSION = 'PCE-OPERATION-FRAMEWORK-V1.1'

export const PCE_PAGE_TYPE_CONTRACTS = PCE_PAGE_TYPE_REQUIRED_REGIONS
export { PCE_PAGE_TYPE_PROFILES }

export const PCE_STANDARD_PAGE_ACTIONS = Object.freeze([
  { actionId: 'refresh-page', label: '刷新', kind: 'readonly', writeAllowed: false },
  { actionId: 'copy-diagnostics', label: '复制诊断数据', kind: 'readonly', writeAllowed: false },
  { actionId: 'return-process-center', label: '返回业务流程中心', kind: 'navigation', writeAllowed: false },
])

export const contractVersion = PCE_WEB_ACCEPTANCE_CONTRACT_VERSION
export const requiredPageActions = PCE_STANDARD_PAGE_ACTIONS
export const requiredRegions = Object.freeze(['页面框架标题区', '业务流程导航', '页面动作栏', '后续边界'])
export const standardToolbarContract = Object.freeze({
  quickSearch: true, advancedFilter: true, multiSelect: true, sorting: true,
  clearSorting: true, exportCurrentResult: true,
})
export const standardListContract = Object.freeze({
  stickyLeftColumns: ['selection', 'index'],
  stickyRightColumns: ['operation'],
  horizontalScrollbar: true,
  singleScrollOwner: true,
})
export const diagnosticsContract = Object.freeze({
  readOnly: true,
  currentStateSource: 'server',
  sensitiveDataAllowed: false,
  writeIntentContractVersion: PCE_WRITE_INTENT_CONTRACT_VERSION,
  requiredWriteIntentFields: [
    'previewPreparationWriteCount',
    'auditWriteCount',
    'forbiddenBusinessProgressWriteCount',
  ],
})
export const geometryContract = Object.freeze({
  requiredWidths: [366, 920, 1366, 1920], pageHorizontalOverflowAllowed: false,
})
export const reportContract = Object.freeze({
  identityFields: ['version', 'contractVersion', 'moduleCode', 'pageCode', 'canonicalName', 'route', 'status', 'failureReason'],
  failureFields: ['fullUrl', 'regionTitle', 'relativePosition', 'fieldOrControl', 'expected', 'actual', 'ctrlFKeyword'],
})

export const PCE_TECHNICAL_ENUM_DISPLAY_MAP = Object.freeze({
  prepared: '已准备',
  approved: '已批准',
  blocked: '已阻断',
  validated: '已验证',
  draft: '草稿',
  committed: '已提交',
  failed: '失败',
  pending: '待处理',
  completed: '已完成',
  cancelled: '已取消',
})

export const PCE_PLAN_COLOR_RULES = Object.freeze([
  { code: 'overdue', color: 'red', label: '已逾期', condition: 'overdueDays > 0' },
  { code: 'urgent', color: 'orange', label: '紧急', condition: 'remainingDays >= 0 && remainingDays <= 3' },
  { code: 'warning', color: 'yellow', label: '预警', condition: 'remainingDays >= 4 && remainingDays <= 7' },
  { code: 'normal', color: 'default', label: '正常', condition: 'remainingDays > 7' },
  { code: 'completed', color: 'green', label: '已完成', condition: 'progressPercent === 100' },
  { code: 'cancelled', color: 'gray', label: '已取消', condition: 'status === cancelled' },
])

const BASE_REQUIRED_REGIONS = Object.freeze([
  '页面框架标题区',
  '业务流程导航',
  '页面动作栏',
  '后续边界',
])

export function createPceWebAcceptanceContract(input = {}) {
  const pageType = PCE_PAGE_TYPE_CONTRACTS[input.pageType] ? input.pageType : 'list'
  const regionSequence = input.regionSequence || PCE_PAGE_TYPE_CONTRACTS[pageType]
  const pageActions = input.pageActions || PCE_STANDARD_PAGE_ACTIONS
  return {
    contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
    governanceVersion: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
    moduleCode: input.moduleCode,
    moduleLayoutVersion: input.moduleLayoutVersion || 'PCE-MODULE-LAYOUT-V1.1',
    pageCode: input.pageCode,
    pageType,
    canonicalName: input.canonicalName,
    route: input.route,
    routeName: input.routeName || input.pageCode,
    component: input.component,
    businessVersion: input.businessVersion || 'registered-current-business-version',
    acceptanceMigrationVersion: input.acceptanceMigrationVersion || '',
    enforcementMode: input.enforcementMode || 'audit',
    acceptanceLevel: Number(input.acceptanceLevel || 0),
    pageFrameworkVersion: input.pageFrameworkVersion || PCE_PAGE_FRAMEWORK_VERSION,
    operationFrameworkVersion: input.operationFrameworkVersion || PCE_OPERATION_FRAMEWORK_VERSION,
    inheritanceContract: {
      systemFramework: 'ProfitCockpit',
      moduleFramework: input.moduleFramework || 'registered-module-framework',
      pageTypeFramework: pageType,
      pageBusinessContract: input.pageCode,
      fourLevelInheritanceRequired: true,
      ...(input.inheritanceContract || {}),
    },
    process: {
      previousModuleCode: null,
      previousCanonicalName: '',
      previousRoute: '',
      currentModuleCode: input.moduleCode,
      currentCanonicalName: input.canonicalName,
      currentRoute: input.route,
      nextModuleCode: null,
      nextCanonicalName: '',
      nextRoute: '',
      ...(input.process || {}),
    },
    requiredRegions: [...new Set([...BASE_REQUIRED_REGIONS, ...regionSequence])],
    regionSequence: [...regionSequence],
    pageActions: pageActions.map(action => ({ ...action })),
    buttonWhitelist: [...new Set([
      ...pageActions.map(action => action.actionId),
      'view-detail',
      ...(input.buttonWhitelist || []),
    ])],
    buttonBlacklist: [...new Set([
      'execute-payment',
      'write-ledger',
      'post-ledger',
      'reveal-sensitive-data',
      ...(input.buttonBlacklist || []),
    ])],
    stateButtonMatrix: (input.stateButtonMatrix || []).map(row => ({ ...row })),
    listContracts: (input.listContracts || []).map(contract => ({ ...contract })),
    languageContract: {
      preferChineseLabels: true,
      technicalEnglishAllowedAreas: ['业务编号', '系统代码', '币种代码', '国际标准代码', '诊断原始枚举'],
      enumDisplayMap: { ...PCE_TECHNICAL_ENUM_DISPLAY_MAP },
      ...(input.languageContract || {}),
    },
    diagnosticsContract: {
      requiredSections: ['版本', '完整URL', '模块与页面', '上下游', '当前查询', '当前筛选', '当前排序', '结果与选择', '业务状态', '校验与审批', '幂等、编号、事务与审计', '下游对象数量'],
      sensitiveFields: ['authorization', 'cookie', 'jwt', 'password', 'privateKey', 'secret', 'fullBankAccount', 'fullIdentityNo'],
      readOnly: true,
      currentStateSource: 'server',
      writeIntentContractVersion: PCE_WRITE_INTENT_CONTRACT_VERSION,
      requiredWriteIntentFields: [
        'previewPreparationWriteCount',
        'auditWriteCount',
        'forbiddenBusinessProgressWriteCount',
      ],
      ...(input.diagnosticsContract || {}),
    },
    planContract: {
      enabled: pageType === 'plan',
      progressField: 'progressPercent',
      plannedDateField: 'plannedDate',
      dueDateField: 'dueDate',
      urgencyField: 'urgency',
      overdueField: 'overdueDays',
      colorRules: PCE_PLAN_COLOR_RULES.map(rule => ({ ...rule })),
      legendRequired: pageType === 'plan',
      serverDerivedBusinessDateRequired: true,
      ...(input.planContract || {}),
    },
    planRules: pageType === 'plan'
      ? { notApplicable: false, reason: '' }
      : { notApplicable: true, reason: '当前页面不是计划排程页面' },
    responsiveContract: {
      requiredWidths: [366, 920, 1366, 1920],
      pageHorizontalOverflowAllowed: false,
      operationColumnAlwaysVisible: pageType === 'list',
      recommendedZoomPercent: [100, 125],
      ...(input.responsiveContract || {}),
    },
    dataProtectionContract: {
      navigationWriteAllowed: false,
      refreshWriteAllowed: false,
      diagnosticsWriteAllowed: false,
      productionWriteAllowed: false,
      safePreparationWriteAllowed: true,
      allowedWriteIntentCategories: [
        WriteIntentCategory.PREVIEW_PREPARATION_WRITE,
        WriteIntentCategory.SEND_TASK_PREPARATION_WRITE,
        WriteIntentCategory.AUDIT_WRITE,
      ],
      forbiddenWriteIntentCategories: [
        WriteIntentCategory.BANK_SEND_EXECUTION_WRITE,
        WriteIntentCategory.BUSINESS_PROGRESS_WRITE,
      ],
      downstreamZeroObjectRequirements: [],
      ...(input.dataProtectionContract || {}),
    },
  }
}

export function createStandardListAcceptanceContract(input = {}) {
  return {
    listId: input.listId,
    listTitle: input.listTitle,
    quickSearchFields: [...(input.quickSearchFields || [])],
    advancedFilterSchema: (input.advancedFilterSchema || []).map(field => ({
      applicable: field.applicable !== false,
      reason: field.applicable === false ? field.reason : '',
      ...field,
    })),
    columnSchema: (input.columnSchema || []).map(column => ({ ...column })),
    defaultSort: input.defaultSort || { prop: input.rowKey || 'id', order: 'ascending' },
    rowKey: input.rowKey || 'id',
    multiSelect: input.multiSelect !== false,
    stickyLeftColumns: input.stickyLeftColumns || ['selection', 'index'],
    stickyRightColumns: input.stickyRightColumns || ['operation'],
    horizontalScrollbar: input.horizontalScrollbar !== false,
    singleScrollOwner: input.singleScrollOwner !== false,
    exportSupported: input.exportSupported !== false,
    importSupported: input.importSupported === true,
    importUnsupportedReason: input.importSupported === true ? '' : (input.importUnsupportedReason || '当前页面未开放批量导入'),
    sensitiveExportFields: input.sensitiveExportFields || ['fullBankAccount', 'password', 'token', 'cookie', 'jwt', 'privateKey', 'secret', 'fullIdentityNo'],
    emptyState: input.emptyState || '暂无符合条件的业务数据',
    errorState: input.errorState || '读取页面数据失败，请刷新后重试',
    loadingState: input.loadingState || '正在读取服务端数据',
  }
}
