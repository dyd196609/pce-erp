export const PDE_WORKBENCH_VERSION = 'V1.14.2.8.4.10.4'

export const pdeWorkbenchEntries = Object.freeze([
  Object.freeze({ code: 'customer-order-demand', label: '客户订单需求', route: '/pde/product-requirements', sourceModule: 'CRM' }),
  Object.freeze({ code: 'engineering-readiness', label: 'PDE工程准备', route: '/pde/engineering-readiness', sourceModule: 'PDE' }),
  Object.freeze({ code: 'product-requirement-review', label: '生产可行性评审', route: '/pde/product-requirement-reviews', sourceModule: 'PDE' }),
  Object.freeze({ code: 'product-design', label: '产品设计', route: '/pde/product-definitions', sourceModule: 'PDE' }),
  Object.freeze({ code: 'bom', label: 'BOM', route: '/pde/product-boms', sourceModule: 'PDE' }),
  Object.freeze({ code: 'routing', label: '工艺路线', route: '/pde/routings', sourceModule: 'PDE' }),
  Object.freeze({ code: 'engineering-documents', label: '工程资料', route: '/pde/engineering-documents', sourceModule: 'PDE' }),
  Object.freeze({ code: 'version-management', label: '版本管理', route: '/pde/product-versions', sourceModule: 'PDE' }),
  Object.freeze({ code: 'engineering-change-ecn', label: 'ECN', route: '/pde/engineering-changes', sourceModule: 'PDE' }),
  Object.freeze({ code: 'manufacturing-output', label: '工程输出', route: '/pde/manufacturing-outputs', sourceModule: 'PDE' }),
  Object.freeze({ code: 'manufacturing-admission-confirmation', label: '制造承接确认', route: '/pde/manufacturing-admissions', sourceModule: 'PDE' }),
  Object.freeze({ code: 'mrp-input-preparation', label: 'MRP输入准备', route: '/pde/mrp-input-preparation', sourceModule: 'PDE' }),
])

export const pdeWorkbenchRelationship = Object.freeze({
  source: 'CRM客户订单',
  chain: Object.freeze([
    'CRM客户订单',
    'PDE',
    'EMD物料',
    'BOM',
    '工艺路线',
    'MRP输入',
    'SCM采购依据',
  ]),
  bomMaterialOwner: 'EMD',
  routingWorkCenterOwner: 'EMD',
  scmAccess: 'read_only_basis',
  purchaseOrderGeneration: false,
})

export const pdeWorkbenchGovernance = Object.freeze({
  version: PDE_WORKBENCH_VERSION,
  frameworkVersion: 'PCE Enterprise Page V2',
  businessModule: 'PDE',
  pageName: 'PDE产品工程工作台',
  pageCode: 'pde-product-engineering-workbench',
  purpose: '统一承接CRM客户订单需求，并导航产品研发与制造准备活动。',
  allowed: Object.freeze(['✓ 查看CRM订单需求来源', '✓ 进入既有PDE工程页面', '✓ 查看制造输入关系']),
  forbidden: Object.freeze(['× CAD', '× PLM', '× PDM', '× 三维设计', '× 生成采购订单']),
  flowSteps: Object.freeze(pdeWorkbenchEntries.map(entry => entry.label)),
  currentFlowStep: '客户订单需求',
  navigation: Object.freeze({
    previous: Object.freeze({ label: 'CRM客户订单', pageCode: 'crm-customer-orders', pageUrl: '/process-center?module=CRM' }),
    current: Object.freeze({ label: 'PDE产品工程工作台', pageCode: 'pde-product-engineering-workbench', pageUrl: '/pde/workbench' }),
    next: Object.freeze({ label: 'PDE工程流程', pageCode: 'pde-product-engineering-process', pageUrl: '/process-center?module=PDE' }),
  }),
  returnModuleCode: 'PDE',
  positioning: '订单驱动的产品研发与制造准备入口',
})

export function findPdeWorkbenchEntry(code) {
  return pdeWorkbenchEntries.find(entry => entry.code === code) || null
}
