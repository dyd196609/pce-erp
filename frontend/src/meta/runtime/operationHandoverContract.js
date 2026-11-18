export const OPERATION_HANDOVER_PAGE = Object.freeze({
  moduleId: 'production-operation-handover', pageCode: 'production-operation-handover', moduleCode: 'MES',
  businessObject: 'OperationHandover', title: '工序交接单', route: '/planning/operation-handovers',
  routeName: 'OperationHandover', component: 'src/meta/pages/OperationHandoverPage.vue',
  version: 'PCE-OPERATION-HANDOVER-V1', formalModel: 'planning.OperationHandover+OperationCustodyEvent+OperationOutputEvidence',
  apiUrl: '/api/planning/operation-handovers/', outputApiUrl: '/api/planning/operation-outputs/',
  factContractVersion: 'PCE-PRODUCTION-OPERATION-HANDOVER-V1', outputFactContractVersion: 'PCE-PRODUCTION-OPERATION-OUTPUT-V1',
})
export const OPERATION_HANDOVER_ROUTE_META = Object.freeze({
  pageCode: OPERATION_HANDOVER_PAGE.pageCode, moduleCode: OPERATION_HANDOVER_PAGE.moduleCode,
  canonicalModuleId: OPERATION_HANDOVER_PAGE.moduleId, businessObject: OPERATION_HANDOVER_PAGE.businessObject,
  formalModel: OPERATION_HANDOVER_PAGE.formalModel, componentKey: OPERATION_HANDOVER_PAGE.component,
  dataAdapter: OPERATION_HANDOVER_PAGE.apiUrl, requiresServerAuthentication: true,
})
export const OPERATION_RANGE_RECEIVE_API = '/api/planning/operation-handovers/ranges/receive/'
const handoverActions = [
  ['prepare', '确认备交并占用份额', 'prepare/', null],
  ['dispatch', '确认实际交出', '{objectId}/dispatch/', 'selectedHandover'],
  ['cancel', '取消尚未交出的备交', '{objectId}/cancel/', 'selectedHandover'],
  ['receive', '确认本次实际收讫', '{objectId}/receive/', 'selectedHandover'],
  ['forward', '备交转送', 'forward/', null],
  ['return', '备交退回', 'return/', null],
  ['exception.submit', '登记关联异常', 'exceptions/', null],
  ['exception.confirm', '确认异常处置', 'exceptions/{objectId}/resolve/', 'selectedException'],
  ['input.confirm', '确认实际投入范围', 'inputs/confirm/', 'selectedOutput'],
  ['range.release', '确认已有批次范围用途', 'ranges/release/', null],
]
const outputActions = [
  ['confirm', '确认本批实际产出', 'confirm/', null],
  ['excess.report', '提交超计划补充报工', 'excess-reports/', null],
  ['excess.review', '审核超计划补充报工', 'excess-reports/{objectId}/review/', 'selectedOutput'],
  ['correct', '确认产出关联更正', 'corrections/', 'selectedException'],
]
export const OPERATION_HANDOVER_ACTION_CONTRACTS = Object.freeze(Object.fromEntries([
  ...handoverActions.map(row => [row, false]), ...outputActions.map(row => [row, true]),
].map(([[key, displayName, suffix, objectField], output]) => {
  const actionCode = `production.operation.${output ? 'output' : 'handover'}.${key}`
  return [key, Object.freeze({ key, actionCode, actionId: actionCode, actionName: displayName, displayName,
    moduleCode: output ? 'production-operation-output' : OPERATION_HANDOVER_PAGE.moduleId,
    actionType: 'command', handlerType: 'emit', scope: 'single', singleOrBatch: 'single',
    permission: actionCode, requiredPermission: actionCode, serverPermission: actionCode,
    role: Object.freeze([]), allowedRoles: Object.freeze([]), roleSource: 'server', organizationScope: 'legal_entity',
    serverValidator: output ? 'planning.operation_output_service.execute_output' : 'planning.operation_handover_service.execute_handover',
    allowedStatuses: Object.freeze(['open', 'declared', 'pending', 'confirmed', 'prepared', 'in_transit', 'partially_received', 'discrepancy_pending', 'U', 'S', 'V', 'Q']),
    serverEligibilityCheck: true, requiresEligibility: true, executionAvailabilitySource: 'availableActions',
    httpMethod: 'POST', apiPathTemplate: `${output ? OPERATION_HANDOVER_PAGE.outputApiUrl : OPERATION_HANDOVER_PAGE.apiUrl}${suffix}`,
    objectField, createsObject: objectField === null,
  })]
})))
export function isOperationHandoverRouteIdentity(route = {}) {
  return route.path === OPERATION_HANDOVER_PAGE.route || route.name === OPERATION_HANDOVER_PAGE.routeName
    || route.meta?.canonicalModuleId === OPERATION_HANDOVER_PAGE.moduleId
}
export function resolveOperationHandoverPageState(route = {}) {
  const fail = detail => { throw new Error(`PAGE IDENTITY MISMATCH: operation handover ${detail}`) }
  if (route.path !== OPERATION_HANDOVER_PAGE.route || route.name !== OPERATION_HANDOVER_PAGE.routeName) fail('route differs')
  for (const [key, value] of Object.entries(OPERATION_HANDOVER_ROUTE_META)) if (route.meta?.[key] !== value) fail(key)
  if (route.query?.view !== undefined && !['view', 'maintain'].includes(route.query.view)) fail('mode differs')
  if (route.query?.screen !== undefined && !['list','detail'].includes(route.query.screen)) fail('screen differs')
  const ids = {}
  for (const key of ['workOrderId', 'taskId', 'outputId', 'handoverId', 'exceptionId', 'custodyWorkCenterId']) {
    const value = route.query?.[key]
    if (value !== undefined && (typeof value !== 'string' || !/^[1-9]\d*$/.test(value) || !Number.isSafeInteger(Number(value)))) fail(key)
    if (value !== undefined) ids[key] = value
  }
  if (route.query?.direction !== undefined && !['incoming','outgoing'].includes(route.query.direction)) fail('direction differs')
  if (route.query?.businessNo !== undefined && (typeof route.query.businessNo !== 'string' || !route.query.businessNo || route.query.businessNo.length>80)) fail('businessNo')
  if(route.query?.businessNo)ids.businessNo=route.query.businessNo
  const subview = route.query?.subview || 'outgoing'
  if (!['outgoing', 'incoming', 'storage', 'history', 'output'].includes(subview)) fail('subview differs')
  return Object.freeze({ domain: 'MES', moduleId: OPERATION_HANDOVER_PAGE.moduleId, mode: route.query?.view || 'view',
    recordId: ids.exceptionId || ids.handoverId || ids.outputId || ids.taskId || null, filters: Object.freeze(ids), subview, identity: OPERATION_HANDOVER_PAGE })
}
export const OPERATION_HANDOVER_FILTERS = Object.freeze([
  { field: 'businessNo', label: '交接业务编号', filterType: 'text' },
  { field: 'no', label: '原交接编号', filterType: 'text' },
  { field: 'workOrderNo', label: '生产工单编号', filterType: 'text' },
  { field: 'sourceWorkCenterName', label: '历史来源工作中心（当时记录）', filterType: 'text' },
  { field: 'targetWorkCenterName', label: '历史接收工作中心（当时记录）', filterType: 'text' },
  { field: 'statusLabel', label: '交接状态', filterType: 'select', options: [],
    optionsProvider: Object.freeze({ source: 'server', factKey: 'operationHandoverFacts.filterOptions.statusLabels' }) },
])
export const OPERATION_HANDOVER_SEARCH_FIELDS = Object.freeze(['no', 'workOrderNo', 'operationName', 'sourceWorkCenterName', 'targetWorkCenterName', 'batchLabel', 'statusLabel'])
export const OPERATION_HANDOVER_EXPORT_COLUMNS = Object.freeze([
  { field: 'businessNo', label: '交接业务编号' }, { field: 'sourceOperationName', label: '交出工序' }, { field: 'targetOperationName', label: '接收工序' },
  { field: 'no', label: '交接单编号' }, { field: 'workOrderNo', label: '生产工单编号' },
  { field: 'sourceWorkCenterName', label: '历史来源工作中心（当时记录）' }, { field: 'targetWorkCenterName', label: '历史接收工作中心（当时记录）' },
  { field: 'sentQuantity', label: '本腿实际交出量' }, { field: 'uomLabel', label: '来源单位' },
  { field: 'rawDeclaredReceiveQuantity', label: '原申报实收量' }, { field: 'correctedMatchedReceiveQuantity', label: '历史净匹配实收量（关联更正后）' },
  { field: 'receiptDifferenceQuantity', label: '本腿当前未收范围' }, { field: 'statusLabel', label: '交接状态' },
])
export const OPERATION_HANDOVER_METRICS = Object.freeze([
  ['P', '冻结计划标准', '原任务工序作业量；不会因超产增大。'],
  ['R', '原正式累计报工', '原数量报工验真累计，不等于已定位可交实物。'],
  ['E', '有效实际产出', '经正式依据有效覆盖的去重数量；搬运和接收不增加产出。'],
  ['W', '有效但尚未定位批次', '已有效数量尚未绑定实物批次，不能直接交出；定位后不再增加产出。'],
  ['U', '来源当前在手', '含首次未交和实际退回在手，不能统称从未交过。'],
  ['S', '暂存保管余额', '真实工作中心承担的暂存责任量，不是库存可用余额。'],
  ['V', '生产去处保管余额', '已匹配实收且仍在目标保管范围的量。'],
  ['I', '已知在途', '已交出且尚未签收、仍明确在途的份额。'],
  ['Q', '差额待核', '所在或责任待核，不自动回源、损失或变成可交量。'],
  ['Z', '正式核定损失份额', '需真实责任处置证明，不自动修改产量。'],
  ['C', '正式投入或转化封闭份额', '需要真实范围证据，不按任务已开工推定全部投入。'],
  ['H', '已备交占用', '在手的占用子集，未知结果或超时不自动释放。'],
  ['F', '受控冻结', '在手的冻结子集，冻结份额不可再次移交。'],
  ['availableSource', '来源车间可交余额（本定量根）', '服务端扣除本根相应占用与冻结后的余额；不等于当前工作中心全部可处置，仍按正式责任范围及准确份额办理。'],
  ['availableStorage', '暂存可转余额（本定量根）', '本根暂存保管范围的正式余额；当前中心只能办理其真实可支配份额，不能拿账户总量代替明细。'],
  ['availableDestination', '生产去处可返或转余额（本定量根）', '本根去处余额，仍须核本中心责任及尚未投入转化；此显示不授予跨范围操作权。'],
  ['unconfirmedReportedQuantity', '已报待确认量', '已报而尚未有效确认，不显示成确定未生产。'],
  ['planDeficit', '有效产出欠数', '与报工未达和产量待确认分列，不推断现场尚未生产。'],
  ['excessQuantity', '多生产余数', '按有效产出比较原标准，不能用超计划交出推导。'],
  ['D', '当前离源净额', '正式服务按有效产出、未定位和来源当前在手范围核实；实际退回来源会改变净额，不是生产量或历史毛交出总量。'],
  ['plannedDispatchDeficit', '计划交出欠数', '按原冻结工序标准与当前离源净额核实，不是确定目标欠收；产量待确认、有效产出欠数及各目标计划和接收分别查看。'],
  ['O', '全路径毛交出流量', '同一定量来源经过转送、暂存和退回可重复流经；毛流量可以大于有效产出，不能当作生产量或用来比较是否超产。'],
  ['A', '全路径累计匹配实收（关联更正净额）', '仅累计有真实来源匹配的实收，关联更正按净额；未匹配X另列。路径可重复经过，不等于当前保管余额或有效产出。'],
  ['X', '当前实收未匹配余数', '原始多收记录保留，找到真实未收来源并正式匹配前不能增加有效产出或先计匹配实收。'],
].map(([field, label, explanation]) => Object.freeze({ field, label, explanation })))
export const OPERATION_HANDOVER_GOVERNANCE = Object.freeze({
  pageCode: OPERATION_HANDOVER_PAGE.pageCode, version: OPERATION_HANDOVER_PAGE.version,
  frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', returnModuleCode: 'MES',
  purpose: '依据正式报工及产出证明，按来源份额办理跨车间实物交出、分次收讫、暂存、转送和退回。',
  allowed: ['读取职责范围内产出与交接事实', '责任人明确确认实际产出及分批交接', '按原请求独立只读核查'],
  forbidden: ['自动接收、派工、开工或完工', '库存、排程或排程占用释放', '工程参考量冒充产量', '未知结果重复提交或换标识重发'],
  flowSteps: ['车间任务／派工', '工序开工', '工序报工', '部分产出确认', '工序交接单'], currentFlowStep: '工序交接单',
  navigation: { previous: { label: '工序报工', pageUrl: '/planning/operation-reports' },
    current: { label: OPERATION_HANDOVER_PAGE.title, pageCode: OPERATION_HANDOVER_PAGE.pageCode, pageUrl: OPERATION_HANDOVER_PAGE.route },
    next: { label: '后序本人任务开工（核验前置及接收）', pageUrl: '/pde/routings' } },
})
