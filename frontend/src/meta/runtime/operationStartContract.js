// The MES start page has its own canonical identity; it is not master data.
export const OPERATION_START_PAGE = Object.freeze({
  moduleId: 'production-operation-start', pageCode: 'production-operation-start', moduleCode: 'MES',
  businessObject: 'ProductionOperationStart', title: '工序开工',
  route: '/planning/operation-starts', routeName: 'OperationStart',
  component: 'src/meta/pages/OperationStartPage.vue', version: 'PCE-OPERATION-START-V1',
  formalModel: 'planning.ProductionOperationStart', apiUrl: '/api/planning/operation-starts/',
  factContractVersion: 'PCE-PRODUCTION-OPERATION-START-V1',
})
export const OPERATION_START_ROUTE_META = Object.freeze({
  pageCode: OPERATION_START_PAGE.pageCode, moduleCode: OPERATION_START_PAGE.moduleCode,
  canonicalModuleId: OPERATION_START_PAGE.moduleId, businessObject: OPERATION_START_PAGE.businessObject,
  formalModel: OPERATION_START_PAGE.formalModel, componentKey: OPERATION_START_PAGE.component,
  dataAdapter: OPERATION_START_PAGE.apiUrl, requiresServerAuthentication: true,
})
export function isOperationStartRouteIdentity(route = {}) {
  return route.path === OPERATION_START_PAGE.route || route.name === OPERATION_START_PAGE.routeName
    || route.meta?.canonicalModuleId === OPERATION_START_PAGE.moduleId
}
export function resolveOperationStartPageState(route = {}) {
  const mismatch = detail => { throw new Error(`PAGE IDENTITY MISMATCH: operation start ${detail}`) }
  if (route.path !== OPERATION_START_PAGE.route || route.name !== OPERATION_START_PAGE.routeName) mismatch('route is not canonical')
  for (const [key, value] of Object.entries(OPERATION_START_ROUTE_META)) {
    if (route.meta?.[key] !== value) mismatch(`route ${key} does not match the registered module`)
  }
  if (route.query?.view !== undefined && route.query.view !== 'view') mismatch('mode is not supported')
  if (route.query?.subview !== undefined) mismatch('subview is not supported')
  const taskId = route.query?.taskId
  if (taskId !== undefined && (typeof taskId !== 'string' || !/^[1-9]\d*$/.test(taskId)
    || !Number.isSafeInteger(Number(taskId)))) mismatch('taskId must identify one task')
  return Object.freeze({ domain: 'MES', moduleId: OPERATION_START_PAGE.moduleId, mode: 'view',
    recordId: taskId || null, filters: Object.freeze(taskId ? { taskId } : {}), subview: null, identity: OPERATION_START_PAGE })
}
export const OPERATION_START_FILTERS = Object.freeze([
  { field: 'no', label: '工序任务编号', filterType: 'text' },
  { field: 'workOrderNo', label: '生产工单编号', filterType: 'text' },
  { field: 'operationName', label: '工序', filterType: 'text' },
  { field: 'workCenterName', label: '工作中心', filterType: 'text' },
  { field: 'executionStatusLabel', label: '执行状态', filterType: 'select', options: [
    { label: '待开工', value: '待开工' }, { label: '已开工', value: '已开工' },
  ] },
])
export const OPERATION_START_SEARCH_FIELDS = Object.freeze(['no', 'workOrderNo', 'operationName', 'workshopName', 'workCenterName', 'positionName', 'employeeName', 'executionStatusLabel'])
export const OPERATION_START_EXPORT_COLUMNS = Object.freeze([
  { field: 'no', label: '工序任务编号' }, { field: 'workOrderNo', label: '生产工单编号' },
  { field: 'operationName', label: '工序' }, { field: 'workshopName', label: '车间' },
  { field: 'workCenterName', label: '工作中心' }, { field: 'workloadLabel', label: '正式作业量／单位' },
  { field: 'positionName', label: '执行岗位' }, { field: 'employeeName', label: '执行人员' },
  { field: 'executionStatusLabel', label: '执行状态' }, { field: 'startedByLabel', label: '开工人' },
  { field: 'startedAtLabel', label: '实际开工时间' },
])
export const OPERATION_START_GOVERNANCE = Object.freeze({
  pageCode: OPERATION_START_PAGE.pageCode, version: OPERATION_START_PAGE.version,
  frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', returnModuleCode: 'MES',
  purpose: '由已派工任务指定的执行人本人核对正式来源、前序条件及资格后人工开工，记录服务端实际开工时间。',
  allowed: ['读取本人合法获派任务和当前开工资格', '读取全部必需前序的正式审核完工证明及未满足原因', '执行人本人明确点击开工', '只读回查执行人、实际时间与审计'],
  forbidden: ['代他人开工', '自动开工或重复提交未知结果', '报工、完工、转移、库存扣减、占用释放或排程调整'],
  flowSteps: ['车间接收', '车间任务／派工', '工序开工', '报工'], currentFlowStep: '工序开工',
  navigation: {
    previous: { label: '车间任务／派工', pageUrl: '/planning/workshop-tasks' },
    current: { label: OPERATION_START_PAGE.title, pageCode: OPERATION_START_PAGE.pageCode, pageUrl: OPERATION_START_PAGE.route },
    next: { label: '工序报工', pageUrl: '/planning/operation-reports' },
  },
})
