import { canAccessModule, canPerformAction } from '../runtime/permissionEngine.js'
import {
  getFoundationCanonicalModule,
  getFoundationCanonicalModuleByAcceptanceCode,
  serializeFoundationMode,
} from './foundationEntryUnificationRegistry.js'

const canonicalPath = (moduleId, mode = 'view') => {
  const identity = getFoundationCanonicalModule(moduleId)
  if (!identity) throw new Error(`PAGE IDENTITY MISMATCH: navigation module ${moduleId} is not registered`)
  const view = serializeFoundationMode(mode)
  return view ? `${identity.routePath}?view=${view}` : identity.routePath
}

export const FOUNDATION_ROUTES = Object.freeze({
  enterpriseFoundation: '/foundation',
  acceptanceCenter: '/foundation/manual-acceptance-center',
  operationFormal: canonicalPath('operation'),
  operationComparison: canonicalPath('operation', 'source_compare'),
  group3OperationAcceptance: canonicalPath('operation', 'acceptance'),
  routingFormal: canonicalPath('routing'),
  routingComparison: canonicalPath('routing', 'source_compare'),
  group3RoutingAcceptance: canonicalPath('routing', 'acceptance'),
})

export const FOUNDATION_FORMAL_ENTITY_CONTRACT = Object.freeze({
  operations: getFoundationCanonicalModule('operation'),
  routings: getFoundationCanonicalModule('routing'),
  routingSteps: getFoundationCanonicalModule('routing-step'),
})

export const enterpriseFoundationNavigation = Object.freeze({
  key: 'enterprise-foundation', moduleKey: 'admin', label: '企业基础资料', icon: 'Collection',
  path: FOUNDATION_ROUTES.enterpriseFoundation, requiredAction: 'READ',
})

const GROUP_LABELS = Object.freeze({ 'GROUP 1': '第1组 客户、供应商与计量单位', 'GROUP 2': '第2组 物料与产品工程', 'GROUP 3': '第3组 制造工程', 'GROUP 4': '第4组 制造资源与日历', 'GROUP 5': '第5组 采购、仓储与供应', 'GROUP 6': '第6组 生产批次与排程策略' })
const MODULE_LABELS = Object.freeze({
  customers: '客户 / 经销商', suppliers: '供应商', uoms: '计量单位', materials: '物料', products: '产品', product_versions: '产品版本', product_configurations: '产品配置',
  operations: '工序', boms: 'BOM', routings: '工艺路线', routing_versions: '工艺路线版本', routing_steps: '路线步骤', workshops: '车间', work_centers: '工作中心', teams: '班组', shifts: '班次',
  standard_capacity: '标准产能', standard_time: '工序标准工时', daily_working_time: '每日工作时间', calendar: '工作日历', staffing: '人员配置', purchase_lead_time: '采购提前期',
  warehouses: '仓库', locations: '库位', inventory: '库存', supply_other: '其它计划 / 供应资料', production_batch: '生产批次', batch_allocation: '批次明细分配', transition_policy: '一般 / 齐套配置',
  kitting_scope: '齐套范围', date_propagation: '计划日期传递', kitting_status: '齐套状态',
})
const action = (key, label, route, options = {}) => Object.freeze({ key, label, route, requiredAction: options.requiredAction || 'READ', prominent: Boolean(options.prominent) })
const isComparisonRoute = (route = '') => route.includes('comparison') || route.includes('group3-acceptance') || route.includes('revalidation')
const isMaintenanceRoute = (route = '') => route.includes('/master-data/') || route === '/organization' || route.startsWith('/organization?') || route === '/shifts'

export const getFoundationGroupLabel = (groupCode = '') => GROUP_LABELS[groupCode] || groupCode
export const getFoundationModuleLabel = (moduleCode = '', fallback = '') => MODULE_LABELS[moduleCode] || fallback || moduleCode

export function getFoundationModuleActions(groupCode, item = {}, role = 'viewer') {
  const identity = getFoundationCanonicalModuleByAcceptanceCode(item.code)
  if (!identity) return []
  const actions = [action('view', '查看数据', canonicalPath(identity.moduleId))]
  if (identity.availableModes.includes('maintain')) actions.push(action('maintain', '维护', canonicalPath(identity.moduleId, 'maintain'), { requiredAction: 'EXECUTE' }))
  if (identity.availableModes.includes('source_compare')) actions.push(action('source-compare', '来源对照', canonicalPath(identity.moduleId, 'source_compare')))
  if (identity.availableModes.includes('acceptance')) actions.push(action('acceptance', '人工验收', canonicalPath(identity.moduleId, 'acceptance'), { prominent: groupCode === 'GROUP 3' }))
  return actions
    .filter(itemAction => canPerformAction(role, itemAction.requiredAction))
}

export function isFoundationAcceptanceRoute(path = '') {
  return path === FOUNDATION_ROUTES.acceptanceCenter || path.startsWith('/foundation/base-data-comparison/') || path.startsWith('/foundation/group2-comparison/')
    || path.startsWith('/foundation/group2-material-targeted-revalidation') || path.startsWith('/foundation/group3-acceptance/') || path.startsWith('/foundation/group3a-operation-targeted-revalidation')
}

export function getAccessibleFoundationNavigation(navigation, state) {
  return navigation.reduce((result, item) => {
    if (!canAccessModule(state.plan, item.moduleKey || item.key)) return result
    if (item.requiredAction && !canPerformAction(state.role, item.requiredAction)) return result
    if (item.requiredPermission && Array.isArray(state.permissionCodes)
      && !state.permissionCodes.includes('*')
      && !state.permissionCodes.includes(item.requiredPermission)) return result
    const children = item.children ? getAccessibleFoundationNavigation(item.children, state) : undefined
    if (item.children && !children.length) return result
    result.push(children ? { ...item, children } : item)
    return result
  }, [])
}
