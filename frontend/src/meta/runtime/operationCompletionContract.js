import {mesWorkOrderFilter} from './mesTestProcessNavigation.js'
export const OPERATION_COMPLETION_PAGE = Object.freeze({
  moduleId: 'production-operation-completion', pageCode: 'production-operation-completion', moduleCode: 'MES',
  businessObject: 'ProductionOperationCompletion', title: '工序完工',
  route: '/planning/operation-completions', routeName: 'OperationCompletion',
  component: 'src/meta/pages/OperationCompletionPage.vue', version: 'PCE-OPERATION-COMPLETION-V1',
  formalModel: 'workflow_runtime.BusinessStateTransition+WorkflowInstance+ApprovalTask+ApprovalDecision',
  apiUrl: '/api/planning/operation-completions/', factContractVersion: 'PCE-PRODUCTION-OPERATION-COMPLETION-V1',
})
export const OPERATION_COMPLETION_ROUTE_META = Object.freeze({
  pageCode: OPERATION_COMPLETION_PAGE.pageCode, moduleCode: OPERATION_COMPLETION_PAGE.moduleCode,
  canonicalModuleId: OPERATION_COMPLETION_PAGE.moduleId, businessObject: OPERATION_COMPLETION_PAGE.businessObject,
  formalModel: OPERATION_COMPLETION_PAGE.formalModel, componentKey: OPERATION_COMPLETION_PAGE.component,
  dataAdapter: OPERATION_COMPLETION_PAGE.apiUrl, requiresServerAuthentication: true,
})
export function isOperationCompletionRouteIdentity(route = {}) {
  return route.path === OPERATION_COMPLETION_PAGE.route || route.name === OPERATION_COMPLETION_PAGE.routeName
    || route.meta?.canonicalModuleId === OPERATION_COMPLETION_PAGE.moduleId
}
export function resolveOperationCompletionPageState(route = {}) {
  const fail = message => { throw new Error(`PAGE IDENTITY MISMATCH: operation completion ${message}`) }
  if (route.path !== OPERATION_COMPLETION_PAGE.route || route.name !== OPERATION_COMPLETION_PAGE.routeName) fail('route is not canonical')
  for (const [key, value] of Object.entries(OPERATION_COMPLETION_ROUTE_META)) if (route.meta?.[key] !== value) fail(`${key} differs`)
  if (route.query?.view !== undefined && route.query.view !== 'view' || route.query?.subview !== undefined) fail('unsupported mode')
  const taskId = route.query?.taskId
  if (taskId !== undefined && (typeof taskId !== 'string' || !/^[1-9]\d*$/.test(taskId) || !Number.isSafeInteger(Number(taskId)))) fail('invalid task identity')
  return Object.freeze({ domain: 'MES', moduleId: OPERATION_COMPLETION_PAGE.moduleId, mode: 'view',
    recordId: taskId || null, filters: Object.freeze({...mesWorkOrderFilter(route),...(taskId ? {taskId}: {})}), subview: null, identity: OPERATION_COMPLETION_PAGE })
}
export const OPERATION_COMPLETION_FILTERS = Object.freeze([
  { field: 'no', label: '工序任务编号', filterType: 'text' },
  { field: 'workOrderNo', label: '生产工单编号', filterType: 'text' },
  { field: 'operationName', label: '工序', filterType: 'text' },
  { field: 'completionStatusLabel', label: '工序整体正式状态', filterType: 'select', options: [
    { label: '尚未申请完工', value: '尚未申请完工' }, { label: '待生产跟单员审核', value: '待生产跟单员审核' },
    { label: '工序完工已生效', value: '工序完工已生效' },
  ] },
])
export const OPERATION_COMPLETION_SEARCH_FIELDS = Object.freeze(['no', 'workOrderNo', 'operationName', 'workshopName', 'workCenterName',
  'requestRecordId', 'submissionProgressLabel', 'reviewProgressLabel', 'overallProgressLabel', 'completionStatusLabel'])
export const OPERATION_COMPLETION_EXPORT_COLUMNS = Object.freeze([
  { field: 'no', label: '工序任务编号' }, { field: 'workOrderNo', label: '生产工单编号' },
  { field: 'operationName', label: '工序' }, { field: 'workshopName', label: '车间' },
  { field: 'workCenterName', label: '工作中心' }, { field: 'workloadQuantity', label: '原始作业量' },
  { field: 'reportedQuantity', label: '累计报工量' }, { field: 'remainingQuantity', label: '剩余量' },
  { field: 'workloadUomLabel', label: '单位' }, { field: 'requestRecordId', label: '本次申请记录标识' },
  { field: 'submissionProgressLabel', label: '本次提交进度' }, { field: 'reviewProgressLabel', label: '本次审核进度' },
  { field: 'overallProgressLabel', label: '工序整体正式状态' },
])
export const OPERATION_COMPLETION_GOVERNANCE = Object.freeze({
  pageCode: OPERATION_COMPLETION_PAGE.pageCode, version: OPERATION_COMPLETION_PAGE.version,
  frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', returnModuleCode: 'MES',
  purpose: '执行人提交完工申请，生产跟单员审核完工数据；逐笔显示正式提交与审核进度，并分别展示工序整体正式状态。',
  allowed: ['读取当前公司职责范围内任务与本次申请进度', '本人提交完工申请', '生产跟单员审核完工数据', '独立回读申请身份、共享审批、状态与审计'],
  forbidden: ['申请人审核本人申请', '以报齐或原因文字代替完工确认', '未知结果自动重试', '工序转移、库存、后序放行、自动开工、排程或占用释放'],
  flowSteps: ['车间任务／派工', '工序开工', '工序报工', '工序完工'], currentFlowStep: '工序完工',
  navigation: {
    previous: { label: '工序报工', pageUrl: '/planning/operation-reports' },
    current: { label: OPERATION_COMPLETION_PAGE.title, pageCode: OPERATION_COMPLETION_PAGE.pageCode, pageUrl: OPERATION_COMPLETION_PAGE.route },
    next: { label: '工序交接单', pageCode: 'production-operation-handover', pageUrl: '/planning/operation-handovers' },
  },
})
