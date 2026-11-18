import {mesWorkOrderFilter} from './mesTestProcessNavigation.js'
// MES reporting has an independent object and authority after actual start.
export const OPERATION_REPORT_PAGE = Object.freeze({
  moduleId: 'production-operation-report', pageCode: 'production-operation-report', moduleCode: 'MES',
  businessObject: 'ProductionOperationReport', title: '工序报工',
  route: '/planning/operation-reports', routeName: 'OperationReport',
  component: 'src/meta/pages/OperationReportPage.vue', version: 'PCE-OPERATION-REPORT-V1',
  formalModel: 'planning.ProductionOperationReport', apiUrl: '/api/planning/operation-reports/',
  factContractVersion: 'PCE-PRODUCTION-OPERATION-REPORT-V1',
})
export const OPERATION_REPORT_ROUTE_META = Object.freeze({
  pageCode: OPERATION_REPORT_PAGE.pageCode, moduleCode: OPERATION_REPORT_PAGE.moduleCode,
  canonicalModuleId: OPERATION_REPORT_PAGE.moduleId, businessObject: OPERATION_REPORT_PAGE.businessObject,
  formalModel: OPERATION_REPORT_PAGE.formalModel, componentKey: OPERATION_REPORT_PAGE.component,
  dataAdapter: OPERATION_REPORT_PAGE.apiUrl, requiresServerAuthentication: true,
})
export function isOperationReportRouteIdentity(route = {}) {
  return route.path === OPERATION_REPORT_PAGE.route || route.name === OPERATION_REPORT_PAGE.routeName
    || route.meta?.canonicalModuleId === OPERATION_REPORT_PAGE.moduleId
}
export function resolveOperationReportPageState(route = {}) {
  const mismatch = detail => { throw new Error(`PAGE IDENTITY MISMATCH: operation report ${detail}`) }
  if (route.path !== OPERATION_REPORT_PAGE.route || route.name !== OPERATION_REPORT_PAGE.routeName) mismatch('route is not canonical')
  for (const [key, value] of Object.entries(OPERATION_REPORT_ROUTE_META)) {
    if (route.meta?.[key] !== value) mismatch(`route ${key} does not match the registered module`)
  }
  if (route.query?.view !== undefined && route.query.view !== 'view') mismatch('mode is not supported')
  if (route.query?.subview !== undefined) mismatch('subview is not supported')
  const taskId = route.query?.taskId
  if (taskId !== undefined && (typeof taskId !== 'string' || !/^[1-9]\d*$/.test(taskId)
    || !Number.isSafeInteger(Number(taskId)))) mismatch('taskId must identify one task')
  return Object.freeze({ domain: 'MES', moduleId: OPERATION_REPORT_PAGE.moduleId, mode: 'view',
    recordId: taskId || null, filters: Object.freeze({...mesWorkOrderFilter(route),...(taskId ? {taskId}: {})}), subview: null, identity: OPERATION_REPORT_PAGE })
}
export const OPERATION_REPORT_FILTERS = Object.freeze([
  { field: 'no', label: '工序任务编号', filterType: 'text' },
  { field: 'workOrderNo', label: '生产工单编号', filterType: 'text' },
  { field: 'operationName', label: '工序', filterType: 'text' },
  { field: 'workCenterName', label: '工作中心', filterType: 'text' },
  { field: 'quantityStatusLabel', label: '报工状态', filterType: 'select', options: [
    { label: '可分次报工', value: '可分次报工' },
    { label: '剩余量低于正式单位最小报工量', value: '剩余量低于正式单位最小报工量' },
    { label: '报工量已达任务量', value: '报工量已达任务量' },
  ] },
])
export const OPERATION_REPORT_SEARCH_FIELDS = Object.freeze(['no', 'workOrderNo', 'operationName', 'workshopName', 'workCenterName', 'positionName', 'employeeName', 'quantityStatusLabel'])
export const OPERATION_REPORT_EXPORT_COLUMNS = Object.freeze([
  { field: 'no', label: '工序任务编号' }, { field: 'workOrderNo', label: '生产工单编号' },
  { field: 'operationName', label: '工序' }, { field: 'workshopName', label: '车间' },
  { field: 'workCenterName', label: '工作中心' }, { field: 'workloadLabel', label: '任务原始作业量／单位' },
  { field: 'reportedQuantity', label: '累计已报量' }, { field: 'remainingQuantity', label: '剩余未报量' },
  { field: 'positionName', label: '执行岗位' }, { field: 'employeeName', label: '执行人员' },
  { field: 'quantityStatusLabel', label: '报工状态' }, { field: 'startedAtLabel', label: '实际开工时间' },
])
export const OPERATION_REPORT_GOVERNANCE = Object.freeze({
  pageCode: OPERATION_REPORT_PAGE.pageCode, version: OPERATION_REPORT_PAGE.version,
  frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', returnModuleCode: 'MES',
  purpose: '本人对合法已开工任务明确输入本次完成数量并分次报工；服务端核对单位精度、累计上限及正式审计。',
  allowed: ['读取本人合法已开工任务及当前报工资格', '本人明确输入本次完成数量并提交一次报工', '独立只读回查报工量、本人、实际时间与审计'],
  forbidden: ['代他人报工', '自动填入全部任务量或自动重试未知结果', '工序完工、转移、库存扣减、占用释放或排程调整'],
  flowSteps: ['车间接收', '车间任务／派工', '工序开工', '工序报工'], currentFlowStep: '工序报工',
  navigation: {
    previous: { label: '按职责进入与历史验收', pageUrl: '/planning/mes-test-execution' },
    current: { label: OPERATION_REPORT_PAGE.title, pageCode: OPERATION_REPORT_PAGE.pageCode, pageUrl: OPERATION_REPORT_PAGE.route },
    next: { label: '工序完工', pageUrl: '/planning/operation-completions' },
  },
})
