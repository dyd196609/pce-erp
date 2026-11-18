import {MES_TEST_NODES} from '../runtime/mesTestProcessNavigation.js'
import { listBusinessOperationPageConfigs } from './businessOperationPageRegistry.js'
import { resolveScmProcessNavigation } from './scmProcessNavigationContract.js'
import { SCM_PURCHASE_PROCESS_CENTER_NODES,
  resolveScmPurchaseProcessNodePageUrlV11428166,
  resolveScmPurchaseProcessNodePageUrlV11428167,
  resolveScmPurchaseProcessNodePageUrlV11428169,
  resolveScmPurchaseProcessNodePageUrlV11428171 } from './scmPurchaseProcessCenterRegistryV11428101.js'
import { resolveBusinessName } from '../governance/businessNameRegistry.js'

export const BUSINESS_PROCESS_REGISTRY_VERSION = 'V1.14.2.8.18.10.4'
export const BUSINESS_PROCESS_STORAGE_KEY = 'pce-business-process-registry-v11428104'

export const businessProcessModules = Object.freeze([
  { moduleCode: 'CRM', moduleName: '营销业务中心', description: '客户、市场与销售业务管理', order: 1, status: 'active' },
  { moduleCode: 'PDE', moduleName: '产品研发与工程管理中心', description: '产品需求、设计、BOM、工艺路线管理', order: 2, status: 'active' },
  { moduleCode: 'EMD', moduleName: '企业主数据中心', description: '组织、客户、供应商、物料、BOM、工艺路线与仓库主数据治理', order: 3, status: 'active' },
  { moduleCode: 'SCM', moduleName: '供应链管理中心', description: '采购、供应商协同与供应商结算', order: 4, status: 'active' },
  { moduleCode: 'PLAN', moduleName: '计划管理中心', description: '需求、物料与生产计划管理', order: 5, status: 'planned' },
  { moduleCode: 'MRP', moduleName: '物料需求计划', description: '物料净需求与采购、生产建议', order: 6, status: 'planned' },
  { moduleCode: 'MPS', moduleName: '主生产计划', description: '成品主生产计划与粗能力校验', order: 7, status: 'planned' },
  { moduleCode: 'APS', moduleName: '高级计划排程', description: '有限产能与制造资源排程', order: 8, status: 'planned' },
  { moduleCode: 'WMS', moduleName: '仓储物流中心', description: '收货、库存与仓储物流管理', order: 9, status: 'active' },
  { moduleCode: 'MES', moduleName: '制造运营中心', description: '制造执行与现场运营管理', order: 10, status: 'planned' },
  { moduleCode: 'QMS', moduleName: '质量管理中心', description: '来料、过程与成品质量管理', order: 11, status: 'active' },
  { moduleCode: 'BI/FDM', moduleName: '数据分析中心', description: '企业分析与制造现场数据展示', order: 12, status: 'planned' },
  { moduleCode: 'KPI', moduleName: '经营绩效中心', description: '经营与组织绩效分析', order: 13, status: 'planned' },
  { moduleCode: 'ProfitOS', moduleName: '经营效益中心', description: '经营效益与绩效管理', order: 14, status: 'planned' },
])

export const businessModuleRelationships = Object.freeze([
  Object.freeze({
    fromModule: 'PDE',
    toModule: 'SCM',
    relationship: '工程资料驱动采购',
    businessChain: ['产品研发', 'BOM发布', '工艺路线', '物料需求', '采购执行'],
  }),
])

const pdeNodeDefinitions = [
  ['product-order-demand', '客户订单需求', 'pde-product-requirements', '/pde/product-requirements', 'V1.14.2.8.4.10.4'],
  ['engineering-readiness-control', 'PDE工程准备', 'pde-engineering-readiness', '/pde/engineering-readiness', 'V1.14.2.8.4.10.4'],
  ['product-requirement-review', '生产可行性评审', 'pde-product-requirement-reviews', '/pde/product-requirement-reviews'],
  ['product-design-management', '产品设计管理', 'pde-product-definitions', '/pde/product-definitions'],
  ['product-version-management', '产品版本管理', 'pde-product-versions', '/pde/product-versions'],
  ['engineering-material-calculation', '工程核算 / 物料核算', 'pde-order-engineering-calculation', '/pde/engineering-calculations'],
  ['bom-management', 'BOM管理', 'pde-product-boms', '/pde/product-boms'],
  ['bom-version-management', 'BOM版本管理', 'pde-bom-versions', '/pde/bom-versions'],
  ['routing-management', '工艺路线管理', 'pde-routings', '/pde/routings'],
  ['routing-version-management', '工艺路线版本管理', 'pde-routing-versions', '/pde/routing-versions'],
  ['engineering-data-release', '工程资料发布', 'pde-engineering-documents', '/pde/engineering-documents'],
  ['engineering-change-ecn', '工程变更ECN', 'pde-engineering-changes', '/pde/engineering-changes'],
  ['trial-production-validation', '试制验证', 'pde-trial-production-validations', '/pde/trial-production-validations'],
  ['mass-production-introduction', '量产导入', 'pde-mass-production-introductions', '/pde/mass-production-introductions'],
  ['manufacturing-output-confirmation', '工程输出确认', 'pde-manufacturing-outputs', '/pde/manufacturing-outputs', 'V1.14.2.8.4.10.2'],
  ['manufacturing-admission-confirmation', '制造承接确认', 'pde-manufacturing-admissions', '/pde/manufacturing-admissions'],
  ['production-demand-admission', '生产需求准入', 'sales-orders', '/sales/orders'],
  ['mrp-input-preparation', 'MRP输入准备', 'pde-mrp-input-preparation', '/pde/mrp-input-preparation', 'V1.14.2.8.4.10.2'],
]

const emdNodeDefinitions = [
  ['organization-data', '组织数据', 'master-data-organizations', '/master-data/organizations'],
  ['customer-data', '客户数据', 'master-data-customers', '/master-data/customers'],
  ['supplier-data', '供应商数据', 'master-data-suppliers', '/master-data/suppliers'],
  ['material-data', '物料数据', 'master-data-materials', '/master-data/materials'],
  ['bom-data', 'BOM数据', 'master-data-boms', '/master-data/boms'],
  ['routing-data', '工艺路线', 'master-data-routings', '/master-data/routings'],
  ['warehouse-data', '仓库数据', 'master-data-warehouses', '/master-data/warehouses'],
]

const scmNodeDefinitions = SCM_PURCHASE_PROCESS_CENTER_NODES

const pdeProcessNodes = pdeNodeDefinitions.map(
  ([nodeCode, nodeName, pageCode = '', pageUrl = '', pageVersion = 'V1.14.2.8.4.9.2'], index) => Object.freeze({
  moduleCode: 'PDE',
  moduleName: '产品研发与工程管理中心',
  processCode: 'PDE_PRODUCT_ENGINEERING',
  processName: 'PDE产品研发工程流程 V1.3',
  nodeCode,
  nodeName,
  sequence: index + 1,
  pageCode,
  pageUrl,
  allowNewTab: true,
  pageVersion: pageUrl ? pageVersion : '',
  pageStatus: pageUrl ? 'active' : 'process_node',
  acceptanceStatus: 'PASS',
  ...(nodeCode === 'manufacturing-admission-confirmation' ? { workflowBinding: {
    processDefinitionId: 10, processCode: 'ORDER_MANUFACTURING_ADMISSION',
    workflowNodeId: 48, nodeCode: 'MANUFACTURING_ADMISSION_CONFIRM',
    actionCode: 'pde.order.manufacturing_admission.confirm',
    responsibilityType: 'MANUFACTURING_ADMISSION_APPROVER', roleCode: 'manufacturing_admission_approver',
    readOnly: true,
  } } : {}),
}))

const emdProcessNodes = emdNodeDefinitions.map(
  ([nodeCode, nodeName, pageCode, pageUrl], index) => Object.freeze({
    moduleCode: 'EMD',
    moduleName: '企业主数据中心',
    processCode: 'EMD_MASTER_DATA_MAINTENANCE',
    processName: '主数据维护流程',
    nodeCode,
    nodeName,
    sequence: index + 1,
    pageCode,
    pageUrl,
    allowNewTab: true,
    pageVersion: 'V1.14.2.8.4.8.5',
    pageStatus: 'active',
    acceptanceStatus: 'PASS',
  }),
)

const scmProcessNodes = scmNodeDefinitions.map((definition, index) => {
  const { nodeCode, nodeName, pageCode = '', pageRoute: configuredPageUrl = '',
    acceptanceProfile = '', previousNode = null, nextNode = null,
    statusDescription = '', runtimeNodeCode = '' } = definition
  const pageUrl = (
    resolveScmProcessNavigation(pageCode)?.pageUrl
    || resolveScmProcessNavigation(nodeCode)?.pageUrl
    || configuredPageUrl
  )
  return Object.freeze({
    moduleCode: 'SCM',
    moduleName: 'SCM供应链管理中心',
    processCode: 'SCM_PURCHASE_SETTLEMENT',
    processName: 'SCM采购与供应商结算流程',
    nodeCode,
    nodeName,
    sequence: index + 1,
    pageCode,
    pageUrl,
    pageRoute: pageUrl,
    allowNewTab: true,
    pageVersion: 'V1.14.2.8.18.10.3',
    pageStatus: pageUrl ? 'active' : 'planned',
    acceptanceStatus: pageUrl ? 'PASS' : 'NOT_APPLICABLE',
    acceptanceProfile,
    previousNode,
    nextNode,
    statusDescription,
    runtimeNodeCode,
  })
})

const makeNode = ({
  moduleCode,
  moduleName,
  processCode,
  processName,
  nodeCode,
  nodeName,
  sequence,
  pageCode = '',
  pageUrl = '',
  pageVersion = '',
  allowNewTab = true,
  pageStatus = pageUrl ? 'active' : 'planned',
  acceptanceStatus = pageUrl ? 'PASS' : 'not_started',
}) => Object.freeze({
  moduleCode,
  moduleName,
  processCode,
  processName,
  nodeCode,
  nodeName,
  sequence,
  pageCode,
  pageUrl,
  allowNewTab,
  pageVersion,
  pageStatus,
  acceptanceStatus,
})

const createProcess = ({
  processCode,
  processName,
  moduleCode,
  moduleName,
  processVersion = 'V1.0',
  status = 'active',
  owner,
  nodes,
}) => Object.freeze({
  processCode,
  processName,
  moduleCode,
  moduleName,
  version: processVersion,
  processVersion,
  versionHistory: Object.freeze([processVersion]),
  status,
  enabled: status === 'active',
  owner,
  nodes: Object.freeze(nodes),
})

const formalBusinessProcesses = [
  createProcess({
    processCode: 'EMD_MASTER_DATA_MAINTENANCE',
    processName: '主数据维护流程',
    moduleCode: 'EMD',
    moduleName: '企业主数据中心',
    owner: '企业主数据管理员',
    nodes: emdProcessNodes,
  }),
  createProcess({
    processCode: 'PDE_PRODUCT_ENGINEERING',
    processName: 'PDE产品研发工程流程 V1.3',
    moduleCode: 'PDE',
    moduleName: '产品研发与工程管理中心',
    processVersion: 'V1.3',
    status: 'active',
    owner: '产品工程负责人',
    nodes: pdeProcessNodes,
  }),
  createProcess({
    processCode: 'SCM_PURCHASE_SETTLEMENT',
    processName: 'SCM采购与供应商结算流程',
    moduleCode: 'SCM',
    moduleName: '供应链管理中心',
    owner: '采购经理',
    nodes: scmProcessNodes,
  }),
  createProcess({
    processCode: 'WMS_WAREHOUSE_OPERATION',
    processName: '仓储流程',
    moduleCode: 'WMS',
    moduleName: '仓储物流中心',
    owner: '仓库主管',
    nodes: [
      makeNode({
        moduleCode: 'WMS', moduleName: '仓储物流中心',
        processCode: 'WMS_WAREHOUSE_OPERATION', processName: '仓储流程',
        nodeCode: 'goods-receipt', nodeName: '收货', sequence: 1,
        pageCode: 'purchase-receive-preview', pageUrl: '/wms/purchase-receive-preview',
        pageVersion: 'V1.14.2.8.4.8.4.1',
      }),
      makeNode({
        moduleCode: 'WMS', moduleName: '仓储物流中心',
        processCode: 'WMS_WAREHOUSE_OPERATION', processName: '仓储流程',
        nodeCode: 'inventory-balance', nodeName: '库存余额', sequence: 2,
        pageCode: 'inventory-balances', pageUrl: '/wms/inventory-balances',
        pageVersion: 'V1.14.2.8.4.8.4.1',
      }),
    ],
  }),
  createProcess({
    processCode: 'MES_PRODUCTION_OPERATION',
    processName: '生产流程',
    moduleCode: 'MES',
    moduleName: '制造运营中心',
    status: 'planned',
    owner: '生产主管',
    nodes: [
      makeNode({
        moduleCode: 'MES', moduleName: '制造运营中心',
        processCode: 'MES_PRODUCTION_OPERATION', processName: '生产流程',
        nodeCode: 'production-work-order', nodeName: '生产工单', sequence: 1,
      }),
    ],
  }),
  createProcess({
    processCode: 'QMS_QUALITY_OPERATION',
    processName: '质量流程',
    moduleCode: 'QMS',
    moduleName: '质量管理中心',
    owner: '质量经理',
    nodes: [
      makeNode({
        moduleCode: 'QMS', moduleName: '质量管理中心',
        processCode: 'QMS_QUALITY_OPERATION', processName: '质量流程',
        nodeCode: 'quality-inspection', nodeName: '质量检验', sequence: 1,
        pageCode: 'incoming-inspection', pageUrl: '/qms/incoming-inspections',
        pageVersion: 'V1.14.2.8.4.8.4.1',
      }),
    ],
  }),
  createProcess({
    processCode: 'FIN_FINANCIAL_SETTLEMENT',
    processName: '财务结算流程',
    moduleCode: 'FIN',
    moduleName: '财务结算中心',
    owner: '财务主管',
    nodes: scmProcessNodes.filter(node => [
      'supplier-payable-confirmation', 'supplier-payment-request',
      'payment-status-record', 'supplier-settlement-completion',
    ].includes(node.nodeCode)).map((node, index) => makeNode({
      ...node,
      moduleCode: 'FIN',
      moduleName: '财务结算中心',
      processCode: 'FIN_FINANCIAL_SETTLEMENT',
      processName: '财务结算流程',
      sequence: index + 1,
    })),
  }),
  createProcess({
    processCode: 'PROFITOS_PERFORMANCE',
    processName: '绩效流程',
    moduleCode: 'ProfitOS',
    moduleName: '经营效益中心',
    owner: '运营经理',
    nodes: scmProcessNodes.filter(node => [
      'supplier-performance', 'buyer-performance',
    ].includes(node.nodeCode)).map((node, index) => makeNode({
      ...node,
      moduleCode: 'ProfitOS',
      moduleName: '经营效益中心',
      processCode: 'PROFITOS_PERFORMANCE',
      processName: '绩效流程',
      sequence: index + 1,
    })),
  }),
]

// Add the isolated execution flow without replacing the planned formal MES flow.
const mesTestExecutionProcess=createProcess({processCode:'MES_TEST_PRODUCTION_EXECUTION',processName:'生产执行与成品交接（独立开发验收）',moduleCode:'MES',moduleName:'制造运营中心',processVersion:'PCE-MES-TEST-COMPAT-V1',owner:'各工序班组长、独立审核人与指定仓管',nodes:MES_TEST_NODES.map(({nodeCode,nodeName,pageCode,pageUrl},index)=>makeNode({moduleCode:'MES',moduleName:'制造运营中心',processCode:'MES_TEST_PRODUCTION_EXECUTION',processName:'生产执行与成品交接（独立开发验收）',nodeCode,nodeName,sequence:index+1,pageCode,pageUrl,pageVersion:'PCE-MES-TEST-COMPAT-V1',acceptanceStatus:'PENDING'}))})
formalBusinessProcesses.push(mesTestExecutionProcess)

export const businessProcessRegistry = Object.freeze(formalBusinessProcesses)

const cloneProcess = process => ({
  ...process,
  // Official PDE mappings must not be shadowed by an older directory projection.
  // Preserve unrelated/custom nodes and all other module definitions.
  nodes: (process.processCode === 'PDE_PRODUCT_ENGINEERING'
    ? [...pdeProcessNodes, ...(process.nodes || []).filter(node => !pdeProcessNodes.some(current => current.nodeCode === node.nodeCode))]
    : (process.nodes || [])).map(node => {
    const governedName = resolveBusinessName({
      nodeCode: node.nodeCode,
      pageCode: node.pageCode,
      route: node.pageUrl,
    })
    return {
      ...node,
      nodeName: process.processCode==='MES_TEST_PRODUCTION_EXECUTION' || node.nodeCode === 'production-demand-admission' ? node.nodeName : (governedName?.processName || node.nodeName),
      nameSource: process.processCode==='MES_TEST_PRODUCTION_EXECUTION' || node.nodeCode === 'production-demand-admission' ? 'BusinessProcessRegistry' : (governedName ? 'BusinessNameRegistry' : node.nameSource),
    }
  }),
})

function loadProcessRegistryState() {
  if (typeof localStorage === 'undefined') return businessProcessRegistry.map(cloneProcess)
  try {
    const stored = JSON.parse(localStorage.getItem(BUSINESS_PROCESS_STORAGE_KEY) || 'null')
    if (!Array.isArray(stored)) return businessProcessRegistry.map(cloneProcess)
    return [...stored,...(stored.some(p=>p?.processCode===mesTestExecutionProcess.processCode)?[]:[mesTestExecutionProcess])]
      .filter(process => process?.processCode && process?.moduleCode)
      .map(cloneProcess)
  } catch {
    return businessProcessRegistry.map(cloneProcess)
  }
}

let processRegistryState = loadProcessRegistryState()

function persistProcessRegistryState() {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(BUSINESS_PROCESS_STORAGE_KEY, JSON.stringify(processRegistryState))
  }
}

export function listBusinessProcesses() {
  return processRegistryState.map(cloneProcess)
}

export function getBusinessProcessByCode(processCode = '') {
  const process = processRegistryState.find(item => item.processCode === String(processCode))
  return process ? cloneProcess(process) : null
}

export function addBusinessProcess(definition = {}) {
  const processCode = String(definition.processCode || '').trim()
  if (!processCode) throw new Error('processCode is required')
  if (getBusinessProcessByCode(processCode)) throw new Error(`process already exists: ${processCode}`)
  const processVersion = String(definition.processVersion || definition.version || 'V1.0')
  const next = {
    processCode,
    processName: String(definition.processName || processCode),
    moduleCode: String(definition.moduleCode || ''),
    moduleName: String(definition.moduleName || ''),
    version: processVersion,
    processVersion,
    versionHistory: [processVersion],
    status: String(definition.status || 'planned'),
    enabled: definition.enabled !== false,
    owner: String(definition.owner || '流程负责人'),
    nodes: (definition.nodes || []).map((node, index) => ({
      ...node,
      sequence: Number(node.sequence || index + 1),
    })),
  }
  processRegistryState = [...processRegistryState, next]
  persistProcessRegistryState()
  return processCode
}

export function updateBusinessProcess(processCode, patch = {}) {
  const current = getBusinessProcessByCode(processCode)
  if (!current) return false
  const processVersion = String(
    patch.processVersion || patch.version || current.processVersion || current.version,
  )
  const versionHistory = Array.from(new Set([
    ...(current.versionHistory || [current.processVersion || current.version]),
    processVersion,
  ]))
  processRegistryState = processRegistryState.map(process => (
    process.processCode === processCode
      ? {
        ...process,
        ...patch,
        processCode,
        version: processVersion,
        processVersion,
        versionHistory,
        nodes: (patch.nodes || process.nodes || []).map(node => ({ ...node })),
      }
      : process
  ))
  persistProcessRegistryState()
  return true
}

export function setBusinessProcessEnabled(processCode, enabled) {
  return updateBusinessProcess(processCode, {
    enabled: Boolean(enabled),
    status: enabled ? 'active' : 'inactive',
  })
}

export function recordBusinessProcessDesignExecution(processCode, payload = {}) {
  return updateBusinessProcess(processCode, {
    lastDesignExecutionAt: new Date().toISOString(),
    lastDesignExecutionAction: String(payload.action || '受控流程设计验证'),
    lastDesignExecutionResult: String(payload.result || '设计验证完成'),
  })
}

export function resetBusinessProcessRegistry() {
  processRegistryState = businessProcessRegistry.map(cloneProcess)
  persistProcessRegistryState()
}

export function listBusinessProcessModules() {
  return businessProcessModules
    .slice()
    .sort((left, right) => left.order - right.order)
    .map((module) => ({ ...module }))
}

export function listBusinessProcessNodes(processCode = 'SCM_PURCHASE_SETTLEMENT') {
  return (getBusinessProcessByCode(processCode)?.nodes || [])
    .slice()
    .sort((left, right) => left.sequence - right.sequence)
    .map((node) => {
      if (processCode !== 'SCM_PURCHASE_SETTLEMENT' || node.nodeCode !== 'supplier-recommendation') {
        return { ...node }
      }
      // V16.6 RuntimeContext navigation is retained as a compatibility symbol;
      // V16.7 resolves the process-center entry exclusively by SupplierRecommendationTask.
      void resolveScmPurchaseProcessNodePageUrlV11428166
      void resolveScmPurchaseProcessNodePageUrlV11428167
      void resolveScmPurchaseProcessNodePageUrlV11428169
      const pageUrl = resolveScmPurchaseProcessNodePageUrlV11428171(node)
      return { ...node, pageUrl, pageRoute: pageUrl, allowNewTab: Boolean(pageUrl) }
    })
}

export function listBoundBusinessProcessPages() {
  return listBusinessProcesses()
    .flatMap(process => process.nodes)
    .filter(node => node.pageUrl)
    .map(node => ({ ...node }))
}

export function listBusinessModuleRelationships() {
  return businessModuleRelationships.map((relationship) => ({
    ...relationship,
    businessChain: [...relationship.businessChain],
  }))
}

export function listPdeProcessNodes() {
  return listBusinessProcessNodes('PDE_PRODUCT_ENGINEERING')
}

export function listEmdProcessNodes() {
  return listBusinessProcessNodes('EMD_MASTER_DATA_MAINTENANCE')
}

// Compatibility projection for the established page/runtime registries. The V832
// catalog is additive; existing consumers continue to receive their original
// purchase-to-payment step shape from the single process metadata source.
const upstreamBusinessProcessSteps = Object.freeze([
  ['procurement-request', 'SCM', '采购申请', '/scm/purchase-request'],
  ['purchase-inquiry', 'SCM', '询价', '/scm/purchase-inquiries'],
  ['price-approval', 'SCM', '采购核价', '/scm/price-approval'],
  ['purchase-order', 'SCM', '采购订单', '/scm/purchase-orders'],
  ['purchase-arrival-preview', 'SCM', '采购到货预备', '/scm/purchase-orders'],
  ['purchase-receive-preview', 'WMS', '采购收货预备', '/wms/purchase-receive-preview'],
  ['incoming-inspection', 'QMS', '来料质量检验', '/qms/incoming-inspections'],
].map(([stepId, moduleCode, stepName, routePath], index, definitions) => Object.freeze({
  stepId,
  moduleId: stepId,
  moduleCode,
  moduleName: moduleCode === 'SCM' ? '供应链管理' : moduleCode === 'WMS' ? '仓储管理' : '质量管理',
  processCode: 'PURCHASE_TO_PAYMENT',
  processName: '采购到付款流程',
  stepName,
  pageTitle: stepName,
  routePath,
  routeName: stepId,
  previousStepId: index > 0 ? definitions[index - 1][0] : null,
  sourceStepIds: index > 0 ? [definitions[index - 1][0]] : [],
  defaultNextStepId: index < definitions.length - 1 ? definitions[index + 1][0] : 'payable-prepare',
  completionStatusValues: [],
  blockedStatusValues: [],
  outputDocumentTypes: [],
  allowedSections: [],
  primaryActionCodes: [],
  secondaryActionCodes: ['view_source_document'],
  introducedInVersion: 'registered-current-business-version',
})))

const downstreamBusinessProcessSteps = listBusinessOperationPageConfigs().map((page) => Object.freeze({
  stepId: page.pageStepId,
  moduleId: page.pageStepId,
  moduleCode: page.routePath.startsWith('/scm/') ? 'SCM' : 'FIN',
  moduleName: page.moduleName,
  processCode: 'PURCHASE_TO_PAYMENT',
  processName: page.processName,
  stepName: page.pageTitle,
  pageTitle: page.pageTitle,
  routePath: page.routePath,
  routeName: page.pageStepId,
  previousStepId: page.previousStepId || null,
  sourceStepIds: page.sourceStepId ? [page.sourceStepId] : [],
  defaultNextStepId: page.nextStepId || null,
  completionStatusValues: [],
  blockedStatusValues: [],
  outputDocumentTypes: page.outputName ? [page.outputName] : [],
  allowedSections: page.businessSectionIds || [],
  primaryActionCodes: page.realActionCode ? [page.realActionCode] : [],
  secondaryActionCodes: ['view_source_document'],
  introducedInVersion: page.introducedInVersion,
}))

const legacyBusinessProcessSteps = Object.freeze([
  ...upstreamBusinessProcessSteps,
  ...downstreamBusinessProcessSteps.map((step, index) => index === 0
    ? Object.freeze({
      ...step,
      previousStepId: 'incoming-inspection',
      sourceStepIds: ['incoming-inspection'],
    })
    : step),
])

export function listBusinessProcessSteps() {
  return legacyBusinessProcessSteps.map((step) => ({
    ...step,
    ...(() => {
      const governedName = resolveBusinessName({ nodeCode: step.stepId, route: step.routePath })
      return governedName ? {
        stepName: governedName.processName,
        pageTitle: governedName.pageTitle,
        nameSource: 'BusinessNameRegistry',
      } : {}
    })(),
    sourceStepIds: [...step.sourceStepIds],
    completionStatusValues: [...step.completionStatusValues],
    blockedStatusValues: [...step.blockedStatusValues],
    outputDocumentTypes: [...step.outputDocumentTypes],
    allowedSections: [...step.allowedSections],
    primaryActionCodes: [...step.primaryActionCodes],
    secondaryActionCodes: [...step.secondaryActionCodes],
  }))
}

export function findBusinessProcessStepByRoutePath(routePath = '') {
  const normalized = String(routePath || '').split('?')[0].split('#')[0]
  return listBusinessProcessSteps().find((step) => step.routePath === normalized) || null
}
