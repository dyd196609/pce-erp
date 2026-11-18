export const MANUFACTURING_CAPABILITY_MAP_VERSION = 'V1.14.2.8.4.8.5.2'

const capabilityDefinitions = [
  ['erp', 'ERP', '企业资源计划', 'Enterprise Resource Planning', '企业资源与经营管理能力展示', ['资源计划', '业财协同', '经营管理', '企业配置']],
  ['crm', 'CRM', '营销业务中心', 'Customer Relationship Management', '客户、市场、销售与交付协同能力', ['客户关系', '销售机会', '报价', '销售订单']],
  ['scm', 'SCM', '供应链管理中心', 'Supply Chain Management', '采购、供应商协同与供应链可视化能力', ['采购协同', '供应商协同', '交期管理', '供应链分析']],
  ['wms', 'WMS', '仓储物流中心', 'Warehouse Management System', '仓库、库位、库存与物流能力展示', ['仓库', '库位', '库存', '仓内物流']],
  ['mrp', 'MRP', '物料需求计划', 'Material Requirements Planning', '物料净需求计算与采购、生产建议能力', ['净需求计算', '采购建议', '生产建议', '缺料分析']],
  ['mps', 'MPS', '主生产计划', 'Master Production Schedule', '成品主生产计划与粗能力校验能力', ['主生产计划', '粗能力校验', '计划锁定', '计划调整']],
  ['aps', 'APS', '高级计划排程', 'Advanced Planning and Scheduling', '有限产能、资源约束与制造排程能力', ['有限产能', '资源排程', '甘特图', '插单重排']],
  ['mes', 'MES', '制造运营中心', 'Manufacturing Operations Management', '工单执行、车间协同、报工与制造追踪能力', ['工单执行', '车间任务', '报工', '制造追踪']],
  ['qms', 'QMS', '质量管理中心', 'Quality Management System', '来料、制程、成品质量与追溯能力', ['检验标准', '质量检验', '不合格处理', '质量追溯']],
  ['bi', 'BI', '商业智能', 'Business Intelligence', '企业分析与管理驾驶舱能力展示', ['经营分析', '管理驾驶舱', '报表', '数据洞察']],
  ['fdm', 'FDM', '制造数据看板', 'Factory Data Monitor', '制造现场数据与状态可视化能力展示', ['制造看板', '现场状态', '数据可视化', '异常展示']],
  ['kpi', 'KPI', '经营绩效中心', 'Key Performance Indicator Management', '企业、部门、岗位与业务绩效分析能力', ['指标治理', '绩效分析', '组织绩效', '改进闭环']],
  ['pfm', 'PFM', '人员档案管理', 'Personnel File Management', '人员、技能、班次与组织协同能力展示', ['人员档案', '技能', '班次', '组织协同']],
]

export const manufacturingModules = Object.freeze(
  capabilityDefinitions.map(([id, shortName, name, englishName, position, subModules], index) => Object.freeze({
    id,
    shortName,
    name,
    englishName,
    position,
    phase: '能力架构',
    status: 'planning',
    order: index + 1,
    subModules: Object.freeze(subModules),
    coreData: Object.freeze([]),
    warningPoints: Object.freeze([]),
    integrationWith: Object.freeze([]),
    operationEntry: false,
  })),
)

export function getManufacturingModules() {
  return manufacturingModules.map(module => ({ ...module }))
}

export function getManufacturingModuleById(moduleId) {
  return manufacturingModules.find(module => module.id === moduleId)
}

export function getManufacturingModuleSummary() {
  return {
    total: manufacturingModules.length,
    status: {
      foundation: manufacturingModules.filter(module => module.status === 'foundation').length,
      planning: manufacturingModules.filter(module => module.status === 'planning').length,
      developing: manufacturingModules.filter(module => module.status === 'developing').length,
      ready: manufacturingModules.filter(module => module.status === 'ready').length,
    },
  }
}
