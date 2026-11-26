export const ENTERPRISE_DATA_BOUNDARY_VERSION = 'V1.14.2.8.4.8.5.1'

export const enterpriseDataCenters = Object.freeze({
  EMD: Object.freeze({
    code: 'EMD',
    name: '企业主数据中心',
    englishName: 'Enterprise Master Data Center',
    role: 'data-maintenance-center',
    entry: '/master-data/organizations',
    responsibilities: Object.freeze(['组织', '客户', '供应商', '物料', 'BOM', '工艺路线', '仓库']),
    exclusions: Object.freeze(['采购订单', '库存业务', '质量业务', '付款业务', '财务业务']),
    maintenanceOwner: true,
  }),
  Reference: Object.freeze({
    code: 'Reference',
    name: '数据引用中心',
    role: 'data-reference-analysis-center',
    entry: '/reference',
    responsibilities: Object.freeze(['展示企业主数据被各业务模块引用关系']),
    forbiddenActions: Object.freeze(['新增', '编辑', '删除', '维护']),
    maintenanceOwner: false,
  }),
  BusinessModule: Object.freeze({
    code: 'BusinessModule',
    name: '业务使用中心',
    role: 'master-data-consumer',
    maintenanceOwner: false,
  }),
  ManufacturingCapabilityMap: Object.freeze({
    code: 'ManufacturingCapabilityMap',
    name: 'PCE制造数字化能力地图',
    role: 'product-architecture-display-center',
    entry: '/manufacturing/modules',
    operationEntry: false,
  }),
})

export const businessProcessModuleOrder = Object.freeze([
  'CRM',
  'PDE',
  'EMD',
  'SCM',
  'PLAN',
  'MRP',
  'MPS',
  'APS',
  'WMS',
  'MES',
  'QMS',
  'BI/FDM',
  'KPI',
  'ProfitOS',
])

export const manufacturingCapabilityOrder = Object.freeze([
  'PDE',
  'CRM',
  'EMD',
  'SCM',
  'PLAN',
  'MRP',
  'MPS',
  'APS',
  'WMS',
  'MES',
  'QMS',
  'BI/FDM',
  'KPI',
])

export function listEnterpriseDataCenters() {
  return Object.values(enterpriseDataCenters).map(center => ({ ...center }))
}
