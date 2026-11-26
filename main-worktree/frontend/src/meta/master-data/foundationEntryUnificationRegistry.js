export const FOUNDATION_ENTRY_UNIFICATION_VERSION = 'PCE-FRONTEND-IDENTITY-V1.0'

export const FOUNDATION_PAGE_MODES = Object.freeze(['view', 'maintain', 'source_compare', 'acceptance'])
const DEFAULT_COMPONENT = 'ProductionFoundationMaintenance'

const module = (moduleId, entityKey, businessDomain, displayName, routeName, routePath, dataSource, options = {}) => Object.freeze({
  moduleId,
  entityKey,
  businessDomain,
  groupKey: options.groupKey || businessDomain,
  displayName,
  objectCode: options.objectCode || moduleId,
  navigationKey: options.navigationKey || `${businessDomain}.${moduleId}`,
  pageKey: options.pageKey || `foundation-${moduleId}`,
  routeName,
  routePath,
  component: options.component || DEFAULT_COMPONENT,
  dataSource,
  maintenanceComponent: DEFAULT_COMPONENT,
  maintenanceApi: `/api/pde/a1-foundation/${entityKey}/`,
  api: options.api || `/api/pde/a1-foundation/${entityKey}/`,
  permissions: Object.freeze(options.permissions || { view: 'READ', maintain: 'EXECUTE' }),
  availableModes: Object.freeze(options.availableModes || ['view', 'maintain']),
  defaultMode: 'view',
  acceptanceCode: options.acceptanceCode || entityKey.replaceAll('-', '_'),
  description: options.description || `${displayName}正式维护入口。`,
  portalVisible: options.portalVisible !== false,
  subviews: Object.freeze(options.subviews || []),
})

export const foundationCanonicalModules = Object.freeze([
  module('customer', 'customers', 'material-supply', '客户 / 经销商', 'MasterDataCustomers', '/master-data/customers', 'sales.Customer', { component: 'MasterDataPage:customers', api: '/api/masterdata/enterprise/customers/facts/', description: '客户与经销商正式主数据入口。' }),
  module('supplier', 'suppliers', 'material-supply', '供应商', 'MasterDataSuppliers', '/master-data/suppliers', 'procurement.Supplier', { component: 'MasterDataPage:suppliers', api: '/api/masterdata/enterprise/suppliers/facts/', description: '继续复用现有供应商主数据正式入口。' }),
  module('material-category', 'material-categories', 'material-supply', '物料类别', 'FoundationMasterDataMaterialCategories', '/foundation/master-data/material-categories', 'masterdata.MaterialCategory', { portalVisible: false, description: '物料档案使用的正式企业分类；与产品分类保持对象边界。' }),
  module('material', 'materials', 'material-supply', '物料档案', 'FoundationMasterDataMaterials', '/foundation/master-data/materials', 'masterdata.Material', { description: 'Material、计量单位状态、供应属性、类型及启停状态。' }),
  module('uom', 'units', 'material-supply', '计量单位', 'FoundationMasterDataUnits', '/foundation/master-data/units', 'masterdata.UnitOfMeasure', { acceptanceCode: 'uoms', description: '物料、BOM及标准产能共用的正式计量单位。' }),
  module('product-category', 'product-categories', 'product-engineering', '产品分类 / 产品族', 'FoundationMasterDataProductCategories', '/foundation/master-data/product-categories', 'pde.ProductCategory', { objectCode: 'ProductCategory', description: '产品分类层级承载产品族语义。' }),
  module('manufacturing-process-type', 'manufacturing-process-types', 'product-engineering', '工艺类型', 'FoundationMasterDataManufacturingProcessTypes', '/foundation/master-data/manufacturing-process-types', 'pde.ManufacturingProcessType', { objectCode: 'ManufacturingProcessType', description: '可维护的制造/涂饰工艺类型维度；不在前端硬编码行业类型。' }),
  module('engineering-breakdown-option', 'engineering-breakdown-options', 'product-engineering', '工程录入基础选项', 'FoundationEngineeringBreakdownOptions', '/foundation/master-data/engineering-breakdown-options', 'pde.EngineeringBreakdownOption', { objectCode: 'EngineeringBreakdownOption', portalVisible: false, description: '门开方向、线型、封边方式和包装方式的正式选项；不混入制造工艺类型。' }),
  module('product-definition', 'products', 'product-engineering', '产品定义', 'FoundationMasterDataProducts', '/foundation/master-data/products', 'pde.ProductDefinition', { objectCode: 'ProductDefinition', acceptanceCode: 'products', description: '正式产品定义入口；产品候选不是正式产品。' }),
  module('product-version', 'product-versions', 'product-engineering', '产品版本', 'FoundationMasterDataProductVersions', '/foundation/master-data/product-versions', 'pde.ProductVersion', { objectCode: 'ProductVersion', acceptanceCode: 'product_versions', portalVisible: false }),
  module('bom', 'boms', 'product-engineering', 'BOM', 'FoundationMasterDataBoms', '/foundation/master-data/boms', 'pde.ProductBOM', { objectCode: 'ProductBOM', acceptanceCode: 'boms', availableModes: FOUNDATION_PAGE_MODES, description: 'BOM主表、版本、明细与替代料使用同一维护实现；来源对照和人工验收仍是本模块的页面模式。' }),
  module('bom-version', 'bom-versions', 'product-engineering', 'BOM版本', 'FoundationMasterDataBomVersions', '/foundation/master-data/bom-versions', 'pde.BOMVersion', { portalVisible: false }),
  module('bom-item', 'bom-items', 'product-engineering', 'BOM明细', 'FoundationMasterDataBomItems', '/foundation/master-data/bom-items', 'pde.BOMItem', { portalVisible: false }),
  module('bom-substitute', 'bom-substitutes', 'product-engineering', 'BOM替代料', 'FoundationMasterDataBomSubstitutes', '/foundation/master-data/bom-substitutes', 'pde.BOMItemSubstitute', { portalVisible: false }),
  module('routing', 'routings', 'product-engineering', '工艺路线', 'FoundationFormalRoutings', '/foundation/master-data/routings', 'pde.Routing', { objectCode: 'Routing', pageKey: 'foundation-formal-routings', acceptanceCode: 'routings', availableModes: FOUNDATION_PAGE_MODES, description: '正式数据与来源预览共用同一模块；人工验收显示42张来源路线卡。' }),
  module('routing-version', 'routing-versions', 'product-engineering', '工艺路线版本', 'FoundationMasterDataRoutingVersions', '/foundation/master-data/routing-versions', 'pde.RoutingVersion', { acceptanceCode: 'routing_versions', portalVisible: false }),
  module('routing-step', 'routing-steps', 'product-engineering', '路线步骤', 'FoundationFormalRoutingSteps', '/foundation/master-data/routing-steps', 'pde.RoutingStep', { pageKey: 'foundation-formal-routing-steps', acceptanceCode: 'routing_steps', portalVisible: false }),
  module('engineering-document', 'engineering-documents', 'product-engineering', '工程资料', 'FoundationMasterDataEngineeringDocuments', '/foundation/master-data/engineering-documents', 'pde.EngineeringDocument'),
  module('engineering-document-version', 'engineering-document-versions', 'product-engineering', '工程资料版本', 'FoundationMasterDataEngineeringDocumentVersions', '/foundation/master-data/engineering-document-versions', 'pde.EngineeringDocumentVersion', { portalVisible: false }),
  module('manufacturing-output', 'manufacturing-outputs', 'product-engineering', '工程发布', 'FoundationMasterDataManufacturingOutputs', '/foundation/master-data/manufacturing-outputs', 'pde.ProductManufacturingOutput', { objectCode: 'ProductManufacturingOutput', description: '发布产品、BOM、路线和工程资料版本的唯一组合。' }),
  module('engineering-source-record', 'engineering-source-records', 'product-engineering', '工程来源记录', 'FoundationMasterDataEngineeringSourceRecords', '/foundation/master-data/engineering-source-records', 'pde.EngineeringSourceRecord', { portalVisible: true }),
  module('engineering-rule-definition', 'engineering-rule-definitions', 'product-engineering', '工程规则定义', 'FoundationEngineeringRuleDefinitions', '/foundation/master-data/engineering-rule-definitions', 'pde.EngineeringRuleDefinition', {
    objectCode: 'EngineeringRuleDefinition',
    portalVisible: true,
    permissions: { view: 'production.engineering.rule.view', maintain: 'production.engineering.rule.create / production.engineering.rule.update_draft / production.engineering.rule.release' },
    description: '工程规则定义唯一正式维护入口；查看、草稿维护与生命周期动作继续使用统一服务端授权。',
  }),
  module('engineering-calculation', 'engineering-calculations', 'product-engineering', '工程核算 / 物料核算', 'PdeOrderEngineeringCalculation', '/pde/engineering-calculations', 'pde.EngineeringCalculationRecord / EngineeringCalculationDetail / EngineeringDerivedFact', {
    component: 'PdeOrderEngineeringCalculationPage',
    objectCode: 'EngineeringCalculationRecord',
    navigationKey: 'product-engineering.engineering-calculation',
    pageKey: 'pde-order-engineering-calculation',
    api: '/api/pde/a1-engineering/calculations/readiness/',
    availableModes: FOUNDATION_PAGE_MODES,
    acceptanceCode: 'engineering_calculation',
    subviews: [{ key: 'semi-finished-structure', label: '半成品物料结构', mode: 'view' }],
    description: '查看核算规则、来源对照、计算预览与人工验收状态；当前只读，不生成正式物料需求。',
  }),
  module('workshop', 'workshops', 'manufacturing-resource', '车间 / 生产区域', 'FoundationMasterDataWorkshops', '/foundation/master-data/workshops', 'system.Workshop', { objectCode: 'Workshop', description: 'Workshop是组织生产区域，不等同于WorkCenter。' }),
  module('team', 'teams', 'manufacturing-resource', '班组', 'FoundationMasterDataTeams', '/foundation/master-data/teams', 'system.Team', { objectCode: 'Team', description: '班组是可增减、可设置有效期的人员作业组织，不等同于工序或工作中心。' }),
  module('team-membership', 'team-memberships', 'manufacturing-resource', '班组成员', 'FoundationMasterDataTeamMemberships', '/foundation/master-data/team-memberships', 'system.TeamMembership', { objectCode: 'TeamMembership', portalVisible: false, description: '员工通过有效期关系加入班组；不改变员工正式部门和岗位。' }),
  module('work-center', 'work-centers', 'manufacturing-resource', '工作中心', 'FoundationMasterDataWorkCenters', '/foundation/master-data/work-centers', 'pde.WorkCenter', { objectCode: 'WorkCenter', acceptanceCode: 'work_centers', description: '可计划资源中心。' }),
  module('operation', 'operations', 'manufacturing-resource', '工序', 'FoundationFormalOperations', '/foundation/master-data/operations', 'system.Process', { objectCode: 'Process', navigationKey: 'manufacturing-resource.operation', pageKey: 'foundation-formal-operations', acceptanceCode: 'operations', availableModes: FOUNDATION_PAGE_MODES, description: 'system.Process正式工序唯一入口。' }),
  module('work-center-operation-capability', 'work-center-operation-capabilities', 'manufacturing-resource', '工序候选工作中心', 'FoundationWorkCenterOperationCapabilities', '/foundation/master-data/work-center-operation-capabilities', 'pde.WorkCenterOperationCapability', { objectCode: 'WorkCenterOperationCapability', portalVisible: false, description: '同一工序可配置主工作中心与多个备选工作中心，供路线和计划按正式能力关系选择。' }),
  module('operation-team-capability', 'operation-team-capabilities', 'manufacturing-resource', '工序可承担班组', 'FoundationOperationTeamCapabilities', '/foundation/master-data/operation-team-capabilities', 'system.ProcessTeamCapability', { objectCode: 'ProcessTeamCapability', description: '同一工序可配置多个合资格班组；班组可按实际能力承担一种或多种工序。' }),
  module('work-center-team-assignment', 'work-center-team-assignments', 'manufacturing-resource', '工作中心可用班组', 'FoundationWorkCenterTeamAssignments', '/foundation/master-data/work-center-team-assignments', 'pde.WorkCenterTeamAssignment', { objectCode: 'WorkCenterTeamAssignment', portalVisible: false, description: '工作中心与实际班组保持可调整的多对多分配关系，不把班组固化成工作中心字段。' }),
  module('equipment', 'equipment', 'manufacturing-resource', '设备资料', 'FoundationMasterDataEquipment', '/foundation/master-data/equipment', 'pde.Equipment', { objectCode: 'Equipment' }),
  module('capacity', 'standard-capacities', 'manufacturing-resource', '标准产能', 'FoundationMasterDataStandardCapacities', '/foundation/master-data/standard-capacities', 'pde.StandardCapacity', { objectCode: 'StandardCapacity', acceptanceCode: 'standard_capacity', description: '维护测量状态、数量、单位、时间基准及资源范围。' }),
  module('warehouse', 'warehouses', 'warehouse', '仓库', 'FoundationMasterDataWarehouses', '/foundation/master-data/warehouses', 'procurement.Warehouse', { objectCode: 'Warehouse', acceptanceCode: 'warehouses', description: '正式Warehouse主数据。' }),
  module('warehouse-location', 'warehouse-locations', 'warehouse', '仓库库位', 'FoundationMasterDataWarehouseLocations', '/foundation/master-data/warehouse-locations', 'procurement.WarehouseLocation', { objectCode: 'WarehouseLocation', acceptanceCode: 'locations', description: '库位身份维护不产生库存事务。' }),
])

export const foundationCanonicalModuleById = Object.freeze(Object.fromEntries(foundationCanonicalModules.map(item => [item.moduleId, item])))
export const foundationCanonicalModuleByEntity = Object.freeze(Object.fromEntries(foundationCanonicalModules.map(item => [item.entityKey, item])))

const groupDefinitions = Object.freeze([
  Object.freeze({ key: 'material-supply', label: '物料与供应', description: '客户、供应商、物料类别、物料和计量单位使用各自唯一正式入口。' }),
  Object.freeze({ key: 'product-engineering', label: '产品工程', description: '产品、BOM、工艺路线和工程发布在一个业务分组内维护。' }),
  Object.freeze({ key: 'manufacturing-resource', label: '制造资源', description: '车间、班组、工序与工作中心分别维护；工序和班组通过可调整的能力关系关联。' }),
  Object.freeze({ key: 'warehouse', label: '仓储基础', description: '仓库和库位属于维护型主数据；维护不产生库存事务。' }),
])

const productEngineeringWorkspaceShortcut = Object.freeze({
  objectCode: 'EngineeringBreakdownBaseDataWorkspace',
  displayName: '工艺／拆单基础数据',
  route: '/foundation/master-data/engineering-breakdown-options?workspace=engineering-breakdown',
  routeName: '',
  navigationKey: 'product-engineering.engineering-breakdown-base-data',
  pageKey: 'foundation-engineering-breakdown-base-data',
  description: '直接进入专用基础选项工作区；产品关系、工艺路线和工程规则继续使用各自唯一正式对象。',
  acceptanceAvailable: false,
})

export const foundationMaintenanceGroups = Object.freeze(groupDefinitions.map(group => Object.freeze({
  ...group,
  entities: Object.freeze(foundationCanonicalModules.filter(item => item.groupKey === group.key && item.component === DEFAULT_COMPONENT).map(item => item.entityKey)),
})))

export const foundationEntryGroups = Object.freeze([
  Object.freeze({
    key: 'organization', label: '组织与人员', description: '组织、部门、岗位、职责、员工与账户继续复用现有组织权限体系。',
    entries: Object.freeze([
      Object.freeze({ objectCode: 'OrganizationFoundation', displayName: '组织与权限', route: '/organization', routeName: '', navigationKey: 'organization', pageKey: 'organization', description: '维护组织、部门、岗位、职责、员工、账户和权限关系。', acceptanceAvailable: false }),
      Object.freeze({ objectCode: 'EmployeeFoundation', displayName: '员工档案', route: '/organization?tab=employees', routeName: '', navigationKey: 'organization.employees', pageKey: 'organization-employees', description: '员工任职关系继续使用现有组织员工正式入口。', acceptanceAvailable: false }),
    ]),
  }),
  ...groupDefinitions.map(group => Object.freeze({
    ...group,
    entries: Object.freeze([
      ...(group.key === 'product-engineering' ? [productEngineeringWorkspaceShortcut] : []),
      ...foundationCanonicalModules.filter(item => item.groupKey === group.key && item.portalVisible).map(item => Object.freeze({
        ...item,
        route: item.routePath,
        acceptanceAvailable: item.availableModes.includes('acceptance'),
      })),
    ]),
  })),
])

export function getFoundationCanonicalModule(moduleId = '') {
  return foundationCanonicalModuleById[moduleId] || null
}

export function getFoundationCanonicalModuleByEntity(entityKey = '') {
  return foundationCanonicalModuleByEntity[entityKey] || null
}

export function getFoundationCanonicalModuleByAcceptanceCode(code = '') {
  const aliases = Object.freeze({ product_configurations: 'product-definition' })
  return getFoundationCanonicalModule(aliases[code]) || foundationCanonicalModules.find(item => item.acceptanceCode === code) || null
}

export function getFoundationCanonicalModuleByRoute(route = {}) {
  const metaModuleId = String(route.meta?.canonicalModuleId || '')
  const byMeta = getFoundationCanonicalModule(metaModuleId)
  const path = String(route.path || '')
  const byPath = foundationCanonicalModules.find(item => item.routePath === path) || null
  if (byMeta && byPath && byMeta.moduleId !== byPath.moduleId) throw new Error(`PAGE IDENTITY MISMATCH: route meta ${byMeta.moduleId} != path ${byPath.moduleId}`)
  return byMeta || byPath
}

export function normalizeFoundationMode(value = '') {
  const raw = String(value || 'view').trim().toLowerCase()
  if (raw === 'comparison') return 'source_compare'
  if (raw === 'formal') return 'view'
  if (!FOUNDATION_PAGE_MODES.includes(raw)) throw new Error(`PAGE IDENTITY MISMATCH: unsupported mode ${raw}`)
  return raw
}

export function serializeFoundationMode(mode = 'view') {
  const normalized = normalizeFoundationMode(mode)
  return normalized === 'view' ? '' : normalized === 'source_compare' ? 'comparison' : normalized
}

export function resolveFoundationPageState(route = {}) {
  const identity = getFoundationCanonicalModuleByRoute(route)
  if (!identity) throw new Error(`PAGE IDENTITY MISMATCH: no canonical module for ${String(route.path || route.name || 'unknown route')}`)
  const mode = normalizeFoundationMode(route.query?.view)
  if (!identity.availableModes.includes(mode)) throw new Error(`PAGE IDENTITY MISMATCH: ${identity.moduleId} does not support ${mode}`)
  const requestedSubview = String(route.query?.subview || '')
  if (requestedSubview && !identity.subviews.some(item => item.key === requestedSubview && item.mode === mode)) throw new Error(`PAGE IDENTITY MISMATCH: unsupported subview ${requestedSubview}`)
  return Object.freeze({ domain: 'enterprise-master-data', moduleId: identity.moduleId, mode, recordId: route.params?.id || null, filters: Object.freeze({}), subview: requestedSubview || (mode === 'source_compare' || mode === 'acceptance' ? mode : null), identity })
}

export function foundationSubviewLocation(moduleId, subview) {
  const identity = getFoundationCanonicalModule(moduleId)
  const definition = identity?.subviews.find(item => item.key === subview)
  if (!definition) throw new Error(`PAGE IDENTITY MISMATCH: unknown subview ${subview}`)
  return { name: identity.routeName, query: { ...(definition.mode === 'view' ? {} : { view: serializeFoundationMode(definition.mode) }), subview } }
}

export const foundationCanonicalRouteDefinitions = Object.freeze(foundationCanonicalModules
  .filter(item => item.component === DEFAULT_COMPONENT)
  .map(item => Object.freeze({
    path: item.routePath.replace(/^\//, ''),
    name: item.routeName,
    entityKey: item.entityKey,
    meta: Object.freeze({ pageCode: item.pageKey, moduleCode: 'EMD', canonicalModuleId: item.moduleId, businessObject: item.displayName, formalModel: item.dataSource, componentKey: item.component, dataAdapter: item.api }),
  })))

export const foundationEntryAuditRows = Object.freeze([
  ['Material', '/foundation/erp/materials', 'A1.7材料维护', 'masterdata.Material', '/api/pde/a1-foundation/materials/', 'ProductionFoundationService', '是', '/foundation/master-data/materials'],
  ['UnitOfMeasure', '无', 'A1.7计量单位', 'masterdata.UnitOfMeasure', '/api/pde/a1-foundation/units/', 'ProductionFoundationService', '否', '/foundation/master-data/units'],
  ['Supplier', '/foundation/erp/suppliers', '无重复入口', 'procurement.Supplier', '/api/masterdata/enterprise/suppliers/facts/', 'SupplierMasterRuntimeAdapter', '否', '/master-data/suppliers'],
  ['SupplierMaterialRelation', '/foundation/erp/material-suppliers', '无重复入口', 'masterdata.MaterialSupplierRelation', '/api/masterdata/relations/material-suppliers/runtime/facts/', 'MaterialSupplierRelationRuntime', '否', '/foundation/erp/material-suppliers'],
  ['SupplierPrice', '/foundation/erp/supplier-material-prices', '无重复入口', 'masterdata.SupplierMaterialPrice', '/api/masterdata/prices/supplier-material-prices/runtime/facts/', 'SupplierMaterialPriceRuntime', '否', '/foundation/erp/supplier-material-prices'],
  ['ProductCategory', '/foundation/erp/product-categories', 'A1.7产品分类', 'pde.ProductCategory', '/api/pde/a1-foundation/product-categories/', 'ProductionFoundationService', '是', '/foundation/master-data/product-categories'],
  ['ProductDefinition', '原入口缺失', 'A1.7产品定义', 'pde.ProductDefinition', '/api/pde/a1-foundation/products/', 'ProductionFoundationService', '否', '/foundation/master-data/products'],
  ['ProductVersion', '原入口缺失', 'A1.7产品版本', 'pde.ProductVersion', '/api/pde/a1-foundation/product-versions/', 'ProductionFoundationService', '否', '/foundation/master-data/products'],
  ['Process / Operation', '/foundation/manufacturing/processes', 'A1.7工序', 'system.Process', '/api/pde/a1-foundation/operations/', 'ProductionFoundationService', '是', '/foundation/master-data/operations'],
  ['Workshop', '原入口缺失', 'A1.7车间', 'system.Workshop', '/api/pde/a1-foundation/workshops/', 'ProductionFoundationService', '否', '/foundation/master-data/workshops'],
  ['WorkCenter', '/foundation/erp/work-centers', 'A1.7工作中心', 'pde.WorkCenter', '/api/pde/a1-foundation/work-centers/', 'ProductionFoundationService', '是', '/foundation/master-data/work-centers'],
  ['Equipment', '/foundation/manufacturing/equipment', 'A1.7设备', 'pde.Equipment', '/api/pde/a1-foundation/equipment/', 'ProductionFoundationService', '是', '/foundation/master-data/equipment'],
  ['StandardCapacity', '原入口缺失', 'A1.7标准产能', 'pde.StandardCapacity', '/api/pde/a1-foundation/standard-capacities/', 'ProductionFoundationService', '否', '/foundation/master-data/standard-capacities'],
  ['ProductBOM', '/master-data/boms', 'A1.7 BOM主表', 'pde.ProductBOM', '/api/pde/a1-foundation/boms/', 'ProductionFoundationService', '是', '/foundation/master-data/boms'],
  ['BOMVersion', '原入口缺失', 'A1.7 BOM版本', 'pde.BOMVersion', '/api/pde/a1-foundation/bom-versions/', 'ProductionFoundationService', '否', '/foundation/master-data/boms'],
  ['BOMItem', '原入口缺失', 'A1.7 BOM明细', 'pde.BOMItem', '/api/pde/a1-foundation/bom-items/', 'ProductionFoundationService', '否', '/foundation/master-data/boms'],
  ['BOMItemSubstitute', '原入口缺失', 'A1.7替代料', 'pde.BOMItemSubstitute', '/api/pde/a1-foundation/bom-substitutes/', 'ProductionFoundationService', '否', '/foundation/master-data/boms'],
  ['Routing', '/foundation/manufacturing/routings', 'A1.7路线主表', 'pde.Routing', '/api/pde/a1-foundation/routings/', 'ProductionFoundationService', '是', '/foundation/master-data/routings'],
  ['RoutingVersion', '原入口缺失', 'A1.7路线版本', 'pde.RoutingVersion', '/api/pde/a1-foundation/routing-versions/', 'ProductionFoundationService', '否', '/foundation/master-data/routings'],
  ['RoutingStep', '原入口缺失', 'A1.7路线步骤', 'pde.RoutingStep', '/api/pde/a1-foundation/routing-steps/', 'ProductionFoundationService', '否', '/foundation/master-data/routing-steps'],
  ['EngineeringDocument', '原入口缺失', 'A1.7工程资料', 'pde.EngineeringDocument', '/api/pde/a1-foundation/engineering-documents/', 'ProductionFoundationService', '否', '/foundation/master-data/engineering-documents'],
  ['EngineeringDocumentVersion', '原入口缺失', 'A1.7工程资料版本', 'pde.EngineeringDocumentVersion', '/api/pde/a1-foundation/engineering-document-versions/', 'ProductionFoundationService', '否', '/foundation/master-data/engineering-documents'],
  ['ProductManufacturingOutput', '原入口缺失', 'A1.7工程发布', 'pde.ProductManufacturingOutput', '/api/pde/a1-foundation/manufacturing-outputs/', 'ProductionFoundationService', '否', '/foundation/master-data/manufacturing-outputs'],
  ['Warehouse', '/foundation/erp/warehouses', 'A1.7缺失', 'procurement.Warehouse', '/api/pde/a1-foundation/warehouses/', 'ProductionFoundationService', '是', '/foundation/master-data/warehouses'],
  ['WarehouseLocation', '原入口缺失', 'A1.7库位', 'procurement.WarehouseLocation', '/api/pde/a1-foundation/warehouse-locations/', 'ProductionFoundationService', '否', '/foundation/master-data/warehouse-locations'],
  ['Lot / Batch', '无日常维护入口', 'A1.7诊断回读', 'procurement.InventoryLot', '/api/pde/a1-foundation/inventory-lots/', 'ProductionFoundationService（只作Gate/引用回读）', '否', '/pde/a1-foundation'],
].map(row => Object.freeze({
  object: row[0], legacyEntry: row[1], a17Entry: row[2], model: row[3], api: row[4], service: row[5], duplicatedBefore: row[6], finalEntry: row[7],
})))

export function findFoundationEntry(entity = '') {
  return foundationEntryGroups.flatMap(group => group.entries)
    .find(item => item.route.endsWith(`/${entity}`)) || null
}
