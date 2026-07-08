export const manufacturingDevelopmentPhases = [
  {
    phase: '第一期',
    title: '平台基础与主数据',
    focus: '先建立人员、主数据、权限、日志和预警底座，为制造模块提供统一基础资料。',
    items: ['PFM', 'ERP主数据', '系统管理', '权限', '日志', '预警引擎基础'],
  },
  {
    phase: '第二期',
    title: '采购销售库存与财务基础',
    focus: '打通制造企业最基础的进销存与应收应付闭环。',
    items: ['SCM采购', 'CRM销售', 'WMS库存', 'ERP应收应付基础'],
  },
  {
    phase: '第三期',
    title: 'BOM、工单与MRP',
    focus: '建立物料需求计划能力，让系统能从计划推导采购和生产建议。',
    items: ['BOM', '工单管理', 'MRP生产计划基础'],
  },
  {
    phase: '第四期',
    title: '车间执行与高级排程',
    focus: '落地制造执行、PDA报工、设备接口、APS有限产能排程和MPS主生产计划。',
    items: ['MES', 'PDA报工', '班次管理', '设备接口基础', 'APS', 'MPS'],
  },
  {
    phase: '第五期',
    title: '质量闭环与预警集成',
    focus: '打通订单、来料、进度和品质预警，形成制造过程质量闭环。',
    items: ['QMS', '订单预警', '来料预警', '进度预警', '品质预警完整集成'],
  },
  {
    phase: '第六期',
    title: '经营分析与可视化',
    focus: '基于各业务模块数据形成报表、绩效和车间实时大屏。',
    items: ['BI', 'KPI', 'FDM大屏'],
  },
]

export const manufacturingIntegrationFlow = [
  'CRM客户订单和销售预测进入MPS主生产计划。',
  '审核后的MPS作为MRP运算输入。',
  'ERP主数据向全模块提供物料、客户、供应商、部门、人员、工作中心和编码规则。',
  'SCM采购单、供应商交期、采购入库和应付数据联动MRP、WMS与ERP。',
  'WMS库存、批号、库位、出入库数据联动MRP、MES、SCM与CRM。',
  'MRP生成采购请购建议和制造工单建议，分别进入SCM与MES。',
  'APS排程结果生成车间派工和计划开完工时间，进入MES执行。',
  'MES生产进度影响CRM交期、APS重排、BI分析、KPI绩效和FDM大屏。',
  'QMS来料、制程、出货质量影响SCM供应商评价、MES工单处理、WMS库存状态和KPI考核。',
  'BI、KPI、FDM读取ERP、CRM、SCM、WMS、MES、QMS等模块数据，形成报表、指标和实时看板。',
]

export function getManufacturingDevelopmentPhases() {
  return manufacturingDevelopmentPhases
}

export function getManufacturingIntegrationFlow() {
  return manufacturingIntegrationFlow
}
