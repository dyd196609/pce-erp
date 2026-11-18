export const PDE_RULESET_VERSION = 'PCE-PDE-GOVERNANCE-V90'

export const pdeRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-001', title: 'PDE必须注册到业务流程中心' }),
  Object.freeze({ ruleId: 'PDE-002', title: 'PDE流程顺序正确' }),
  Object.freeze({ ruleId: 'PDE-003', title: 'BOM必须引用EMD物料' }),
  Object.freeze({ ruleId: 'PDE-004', title: 'PDE不能创建第二套物料主数据' }),
  Object.freeze({ ruleId: 'PDE-005', title: '工艺路线必须绑定产品' }),
  Object.freeze({ ruleId: 'PDE-006', title: '页面必须有流程节点' }),
])

const expectedNodes = [
  '产品需求',
  '产品立项',
  '产品设计',
  'BOM建立',
  '工艺路线设计',
  '工程资料发布',
  '量产导入',
]

function result(ruleId, passed, evidence) {
  return {
    ruleId,
    title: pdeRules.find(rule => rule.ruleId === ruleId)?.title || '',
    status: passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

export function evaluatePdeRules({
  module,
  process,
  dependency,
  pageDefinitions,
  modelEvidence,
  canary,
}) {
  const nodes = [...(process?.nodes || [])].sort((a, b) => a.sequence - b.sequence)
  const pages = Object.values(pageDefinitions || {})
  const boundPageCodes = nodes.map(node => node.pageCode).filter(Boolean)
  return [
    result(
      'PDE-001',
      module?.moduleCode === 'PDE' && module?.status === 'active'
        && process?.processCode === 'PDE_PRODUCT_ENGINEERING' && process?.status === 'active',
      { module, processCode: process?.processCode, processStatus: process?.status },
    ),
    result(
      'PDE-002',
      nodes.length === expectedNodes.length
        && nodes.every((node, index) => node.nodeName === expectedNodes[index]),
      { expectedNodes, actualNodes: nodes.map(node => node.nodeName) },
    ),
    result(
      'PDE-003',
      dependency?.dependsOn?.includes('EMD_MATERIAL_MASTER')
        && modelEvidence?.bomUsesEmdMaterialReference === true
        && canary?.boms?.every(bom => bom.components.every(item => item.emdMaterialCode)),
      {
        dependency: dependency?.dependsOn,
        bomUsesEmdMaterialReference: modelEvidence?.bomUsesEmdMaterialReference,
      },
    ),
    result(
      'PDE-004',
      modelEvidence?.pdeMaterialMasterModelPresent === false
        && dependency?.integrationRules?.materialCodeOwnership === 'EMD',
      {
        pdeMaterialMasterModelPresent: modelEvidence?.pdeMaterialMasterModelPresent,
        materialCodeOwnership: dependency?.integrationRules?.materialCodeOwnership,
      },
    ),
    result(
      'PDE-005',
      modelEvidence?.routingUsesProductForeignKey === true
        && canary?.routings?.every(routing => routing.productCode),
      {
        routingUsesProductForeignKey: modelEvidence?.routingUsesProductForeignKey,
        routingCount: canary?.routings?.length,
      },
    ),
    result(
      'PDE-006',
      pages.length === 4
        && pages.every(page => page.nodeCode && boundPageCodes.includes(page.pageCode)),
      {
        pageCount: pages.length,
        pageBindings: pages.map(page => ({ pageCode: page.pageCode, nodeCode: page.nodeCode })),
        boundPageCodes,
      },
    ),
  ]
}

