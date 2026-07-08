export const manufacturingIntegrationMap = {
  scm: {
    moduleName: 'SCM供应链管理',
    references: ['suppliers', 'materials', 'buyers', 'warehouses', 'locations', 'codingRules', 'warningRules'],
    description: '采购、供应商、到货与交期预警所需的基础资料引用。',
  },
  crm: {
    moduleName: 'CRM客户关系管理',
    references: ['customers', 'materials', 'salespersons', 'warehouses', 'codingRules', 'warningRules'],
    description: '客户、销售订单、报价与信用控制所需的基础资料引用。',
  },
  wms: {
    moduleName: 'WMS仓储管理',
    references: ['materials', 'warehouses', 'locations', 'employees', 'codingRules', 'warningRules'],
    description: '出入库、库存、库位和条码作业所需的基础资料引用。',
  },
  mrp: {
    moduleName: 'MRP物料需求计划',
    references: ['materials', 'warehouses', 'locations', 'workCenters', 'systemParameters', 'warningRules'],
    description: '净需求计算、库存约束和生产建议所需的基础资料引用。',
  },
  mps: {
    moduleName: 'MPS主生产计划',
    references: ['customers', 'materials', 'workCenters', 'systemParameters'],
    description: '销售需求、成品计划和粗能力校验所需的基础资料引用。',
  },
  aps: {
    moduleName: 'APS高级计划排程',
    references: ['workCenters', 'employees', 'shifts', 'materials', 'systemParameters'],
    description: '有限产能排程、人员班次和物料约束所需的基础资料引用。',
  },
  mes: {
    moduleName: 'MES制造执行',
    references: ['materials', 'employees', 'shifts', 'workCenters', 'warehouses', 'locations', 'warningRules'],
    description: '工单执行、领料、报工和完工入库所需的基础资料引用。',
  },
  qms: {
    moduleName: 'QMS质量管理',
    references: ['materials', 'suppliers', 'customers', 'employees', 'dataDictionaries', 'warningRules'],
    description: '来料、制程、出货检验和质量预警所需的基础资料引用。',
  },
  bi: {
    moduleName: 'BI商业智能',
    references: ['allModuleOutputs', 'employees', 'departments', 'workCenters', 'warningRecords', 'operationLogs'],
    description: '经营报表、管理驾驶舱和跨模块分析所需的基础资料引用。',
  },
  kpi: {
    moduleName: 'KPI绩效管理',
    references: ['allModuleOutputs', 'employees', 'departments', 'workCenters', 'warningRecords', 'operationLogs'],
    description: '部门、人员、工作中心绩效考核所需的基础资料引用。',
  },
  fdm: {
    moduleName: 'FDM车间数据大屏',
    references: ['allModuleOutputs', 'employees', 'departments', 'workCenters', 'warningRecords', 'operationLogs'],
    description: '车间实时看板、状态监控和异常提示所需的基础资料引用。',
  },
}

export const referenceUsageLabels = {
  allModuleOutputs: '全部后续模块输出',
  buyers: '采购员',
  codingRules: '编码规则',
  customers: '客户',
  dataDictionaries: '数据字典',
  departments: '部门',
  employees: '员工',
  locations: '库位',
  materials: '物料',
  operationLogs: '操作日志',
  salespersons: '销售人员',
  shifts: '班次',
  suppliers: '供应商',
  systemParameters: '系统参数',
  warehouses: '仓库',
  warningRecords: '预警记录',
  warningRules: '预警规则',
  workCenters: '工作中心',
}

export function getManufacturingIntegrationMap() {
  return manufacturingIntegrationMap
}

export function getModulesUsingReference(referenceKey) {
  return Object.entries(manufacturingIntegrationMap)
    .filter(([, moduleConfig]) => moduleConfig.references.includes(referenceKey))
    .map(([moduleId, moduleConfig]) => ({
      moduleId,
      moduleName: moduleConfig.moduleName,
    }))
}

export function formatReferenceUsers(referenceKey) {
  const users = getModulesUsingReference(referenceKey)
  return users.length ? users.map((item) => item.moduleName).join('、') : '暂未配置引用模块'
}
