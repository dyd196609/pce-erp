// Single canonical identity consumed by route, process, naming and page contracts.
export const WORKSHOP_TASK_PAGE = Object.freeze({
  moduleId: 'production-workshop-task', pageCode: 'production-workshop-task',
  moduleCode: 'MES', businessObject: 'ProductionWorkshopTask',
  title: '车间任务／派工', route: '/planning/workshop-tasks', routeName: 'WorkshopTaskDispatch',
  component: 'src/meta/pages/WorkshopTaskDispatchPage.vue', version: 'PCE-WORKSHOP-TASK-DISPATCH-V1',
  formalModel: 'planning.ProductionWorkshopTask',
  apiUrl: '/api/planning/workshop-tasks/', factContractVersion: 'PCE-PRODUCTION-WORKSHOP-TASK-DISPATCH-V1',
})

// This MES operator page is not enterprise master data. The route guard must
// resolve its own formal identity instead of looking it up as a foundation page.
export const WORKSHOP_TASK_ROUTE_META = Object.freeze({
  pageCode: WORKSHOP_TASK_PAGE.pageCode,
  moduleCode: WORKSHOP_TASK_PAGE.moduleCode,
  canonicalModuleId: WORKSHOP_TASK_PAGE.moduleId,
  businessObject: WORKSHOP_TASK_PAGE.businessObject,
  formalModel: WORKSHOP_TASK_PAGE.formalModel,
  componentKey: WORKSHOP_TASK_PAGE.component,
  dataAdapter: WORKSHOP_TASK_PAGE.apiUrl,
  requiresServerAuthentication: true,
})

export function isWorkshopTaskRouteIdentity(route = {}) {
  return route.path === WORKSHOP_TASK_PAGE.route
    || route.name === WORKSHOP_TASK_PAGE.routeName
    || route.meta?.canonicalModuleId === WORKSHOP_TASK_PAGE.moduleId
}

export function resolveWorkshopTaskPageState(route = {}) {
  const mismatch = detail => { throw new Error(`PAGE IDENTITY MISMATCH: workshop task ${detail}`) }
  if (route.path !== WORKSHOP_TASK_PAGE.route) mismatch('path is not canonical')
  if (route.name !== WORKSHOP_TASK_PAGE.routeName) mismatch('route name is not canonical')
  for (const [key, expected] of Object.entries(WORKSHOP_TASK_ROUTE_META)) {
    if (route.meta?.[key] !== expected) mismatch(`route ${key} does not match the registered module`)
  }
  const rawMode = route.query?.view
  if (rawMode !== undefined && rawMode !== 'view') mismatch('mode is not supported')
  if (route.query?.subview !== undefined) mismatch('subview is not supported')
  const filters = {}
  for (const key of ['workOrderId', 'operationId']) {
    const value = route.query?.[key]
    if (value === undefined) continue
    if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value))) {
      mismatch(`${key} must be one positive record identity`)
    }
    filters[key] = value
  }
  return Object.freeze({
    domain: WORKSHOP_TASK_PAGE.moduleCode,
    moduleId: WORKSHOP_TASK_PAGE.moduleId,
    mode: 'view', recordId: filters.operationId || null,
    filters: Object.freeze(filters), subview: null, identity: WORKSHOP_TASK_PAGE,
  })
}

export const WORKSHOP_TASK_FILTERS = Object.freeze([
  { field: 'no', label: '工序任务编号', filterType: 'text' },
  { field: 'workOrderNo', label: '生产工单编号', filterType: 'text' },
  { field: 'operationName', label: '工序', filterType: 'text' },
  { field: 'employeeName', label: '执行人员', filterType: 'text' },
  { field: 'statusLabel', label: '任务状态', filterType: 'select', options: [
    { label: '草稿', value: '草稿' }, { label: '已派工', value: '已派工' },
  ] },
])
export const WORKSHOP_TASK_SEARCH_FIELDS = Object.freeze(['no', 'workOrderNo', 'operationName', 'workshopName', 'workCenterName', 'positionName', 'employeeName', 'statusLabel'])
export const WORKSHOP_TASK_EXPORT_COLUMNS = Object.freeze([
  { field: 'no', label: '工序任务编号' }, { field: 'workOrderNo', label: '生产工单编号' },
  { field: 'operationName', label: '工序' }, { field: 'workshopName', label: '车间' },
  { field: 'workCenterName', label: '工作中心' }, { field: 'workloadLabel', label: '正式作业量／单位' },
  { field: 'positionName', label: '执行岗位' }, { field: 'employeeName', label: '执行人员' },
  { field: 'statusLabel', label: '任务状态' }, { field: 'dispatchedByLabel', label: '派工人' },
  { field: 'dispatchedAtLabel', label: '派工时间' },
])
export const WORKSHOP_TASK_GOVERNANCE = Object.freeze({
  pageCode: WORKSHOP_TASK_PAGE.pageCode, version: WORKSHOP_TASK_PAGE.version,
  frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', returnModuleCode: 'MES',
  purpose: '将已接收的正式工序形成车间任务，由本车间主任明确指定执行岗位和人员后人工派工。',
  allowed: ['读取已接收工序和合法人员候选', '保存任务草稿', '由有权主任正式派工并读取保存结果'],
  forbidden: ['自动选择执行人', '修改冻结工单工序或排程占用', '自动派工', '开工或报工'],
  flowSteps: ['车间接收', '车间任务／派工', '工序开工', '报工'], currentFlowStep: '车间任务／派工',
  navigation: {
    previous: { label: '车间接收', pageUrl: '/planning/requirements?section=work-order-reception' },
    current: { label: WORKSHOP_TASK_PAGE.title, pageCode: WORKSHOP_TASK_PAGE.pageCode, pageUrl: WORKSHOP_TASK_PAGE.route },
    next: { label: '工序开工', pageCode: 'production-operation-start', pageUrl: '/planning/operation-starts' },
  },
})
