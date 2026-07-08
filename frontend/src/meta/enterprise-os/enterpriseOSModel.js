export const ENTERPRISE_OS_STATUS = {
  enterpriseOSMode: 'ON',
  moduleUI: 'DISABLED',
  processUI: 'ACTIVE',
  organizationUI: 'ACTIVE',
}

export const enterpriseOSNavigation = [
  {
    key: 'dashboard',
    label: '仪表盘',
    path: '/dashboard',
    icon: 'DataBoard',
  },
  {
    key: 'organization',
    label: '组织结构',
    path: '/organization',
    icon: 'UserFilled',
  },
  {
    key: 'process-center',
    label: '业务流程中心',
    path: '/process-center',
    icon: 'Tickets',
  },
  {
    key: 'work-center',
    label: '个人工作台',
    path: '/work-center',
    icon: 'Cpu',
  },
  {
    key: 'analytics',
    label: '分析中心',
    path: '/analytics',
    icon: 'TrendCharts',
  },
  {
    key: 'admin',
    label: '系统配置',
    path: '/admin',
    icon: 'Monitor',
  },
]

export const legacyModuleProcessMap = [
  {
    legacyModule: 'CRM',
    processNode: 'Plan',
    ownerRole: 'Sales Manager',
    status: 'ACTIVE',
    kpi: 'Lead conversion 24%',
    risk: 'LOW',
  },
  {
    legacyModule: 'SCM',
    processNode: 'Purchase',
    ownerRole: 'Procurement Manager',
    status: 'ACTIVE',
    kpi: 'Supplier OTD 91%',
    risk: 'MEDIUM',
  },
  {
    legacyModule: 'Inventory',
    processNode: 'Warehouse',
    ownerRole: 'Warehouse Lead',
    status: 'ACTIVE',
    kpi: 'Inventory turnover 7.8x',
    risk: 'LOW',
  },
  {
    legacyModule: 'Finance',
    processNode: 'Finance',
    ownerRole: 'Finance Controller',
    status: 'ACTIVE',
    kpi: 'Cashflow $128,000',
    risk: 'LOW',
  },
]

export const processNodes = [
  {
    key: 'plan',
    name: 'Plan',
    status: 'RUNNING',
    owner: 'Sales Manager',
    kpi: 'Forecast accuracy 88%',
    risk: 'LOW',
    roleBasedEntry: true,
  },
  {
    key: 'purchase',
    name: 'Purchase',
    displayName: '采购流程',
    status: 'APPROVAL',
    owner: 'Procurement Manager',
    kpi: 'Cycle time 5.5d',
    risk: 'MEDIUM',
    route: '/purchase/order',
    primaryAction: 'Submit purchase approval',
    roleBasedEntry: true,
  },
  {
    key: 'production',
    name: 'Production',
    displayName: '生产流程',
    status: 'RUNNING',
    owner: 'Production Lead',
    kpi: 'OEE 86%',
    risk: 'LOW',
    primaryAction: 'Start production task',
    roleBasedEntry: true,
  },
  {
    key: 'quality',
    name: 'Quality',
    status: 'REVIEW',
    owner: 'Quality Manager',
    kpi: 'Yield 94%',
    risk: 'MEDIUM',
    roleBasedEntry: true,
  },
  {
    key: 'warehouse',
    name: 'Warehouse',
    displayName: '仓储流程',
    status: 'RUNNING',
    owner: 'Warehouse Lead',
    kpi: 'Turnover 7.8x',
    risk: 'LOW',
    primaryAction: 'Process warehouse receipt',
    roleBasedEntry: true,
  },
  {
    key: 'finance',
    name: 'Finance',
    displayName: '财务结算流程',
    status: 'POSTING',
    owner: 'Finance Controller',
    kpi: 'Margin 18%',
    risk: 'LOW',
    primaryAction: 'Run settlement check',
    roleBasedEntry: true,
  },
]

export const organizationNodes = [
  { type: 'Company', name: 'PalmCloud Enterprise', people: 128, processBinding: 'Enterprise Strategy' },
  { type: 'Department', name: 'Procurement', people: 18, processBinding: 'Purchase' },
  { type: 'Department', name: 'Production', people: 42, processBinding: 'Production' },
  { type: 'Department', name: 'Finance', people: 12, processBinding: 'Finance' },
  { type: 'Role', name: 'Procurement Manager', people: 3, processBinding: 'Purchase Approval' },
  { type: 'User', name: 'Current Operator', people: 1, processBinding: 'Assigned Workflows' },
]

export const workCenterQueues = [
  { name: 'My Tasks', count: 12, role: 'Current Role', priority: 'NORMAL' },
  { name: 'Pending Approvals', count: 5, role: 'Manager', priority: 'HIGH' },
  { name: 'Assigned Workflows', count: 8, role: 'Process Owner', priority: 'NORMAL' },
  { name: 'Execution Queue', count: 17, role: 'Operator', priority: 'MEDIUM' },
]

export const processCenterTasks = [
  {
    id: 'task-purchase-approval',
    title: 'Purchase approval pending',
    process: '采购流程',
    ownerRole: 'Procurement Manager',
    status: 'PENDING',
    action: 'Review supplier quote',
  },
  {
    id: 'task-production-release',
    title: 'Production work order ready',
    process: '生产流程',
    ownerRole: 'Production Lead',
    status: 'READY',
    action: 'Release work order',
  },
  {
    id: 'task-warehouse-receipt',
    title: 'Inbound receipt waiting',
    process: '仓储流程',
    ownerRole: 'Warehouse Lead',
    status: 'WAITING',
    action: 'Confirm receiving',
  },
  {
    id: 'task-finance-settlement',
    title: 'Settlement batch prepared',
    process: '财务结算流程',
    ownerRole: 'Finance Controller',
    status: 'READY',
    action: 'Validate settlement',
  },
]

export function getEnterpriseOSModel() {
  return {
    mode: 'ENTERPRISE_OPERATING_SYSTEM_UI',
    ...ENTERPRISE_OS_STATUS,
    navigation: enterpriseOSNavigation,
    organization: organizationNodes,
    processNodes,
    processCenterTasks,
    workCenterQueues,
    legacyModuleProcessMap,
    dashboard: {
      kpis: {
        health: 92,
        profit: '$286,000',
        cost: '$104,000',
        capacity: '86%',
        riskIndex: '18/100',
      },
      liveBusinessFlow: processNodes.map((node) => `${node.name}:${node.status}`),
    },
  }
}
