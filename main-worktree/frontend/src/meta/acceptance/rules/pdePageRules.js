export const PDE_PAGE_RULESET_VERSION = 'PCE-PDE-PAGE-GOVERNANCE-V491'

export const pdePageRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-001', title: 'PDE页面必须属于PDE模块' }),
  Object.freeze({ ruleId: 'PDE-002', title: 'PDE页面必须绑定业务节点' }),
  Object.freeze({ ruleId: 'PDE-003', title: 'PDE页面必须使用统一页面模板' }),
  Object.freeze({ ruleId: 'PDE-004', title: 'PDE详情禁止JSON和技术字段展示' }),
  Object.freeze({ ruleId: 'PDE-005', title: 'PDE必须引用EMD数据' }),
  Object.freeze({ ruleId: 'PDE-006', title: 'PDE页面治理区域必须完整' }),
  Object.freeze({ ruleId: 'PDE_RETURN_MODULE_001', title: '返回流程中心必须保持PDE定位' }),
])

function result(ruleId, passed, evidence) {
  return {
    ruleId,
    title: pdePageRules.find(rule => rule.ruleId === ruleId)?.title || '',
    status: passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

export function evaluatePdePageRules({
  pageDefinitions,
  process,
  dependency,
  sources,
}) {
  const pages = Object.values(pageDefinitions || {})
  const boundNodeCodes = new Set(
    (process?.nodes || []).filter(node => node.pageUrl).map(node => node.nodeCode),
  )
  const forbiddenTechnicalFields = ['statusCode', 'sourceObjectRefs', 'technicalState']
  return [
    result(
      'PDE-001',
      pages.length === 4
        && pages.every(page => page.governance?.businessModule === 'PDE'),
      { modules: pages.map(page => page.governance?.businessModule) },
    ),
    result(
      'PDE-002',
      pages.every(page => page.nodeCode && boundNodeCodes.has(page.nodeCode)),
      {
        pageNodes: pages.map(page => ({ pageCode: page.pageCode, nodeCode: page.nodeCode })),
        boundNodeCodes: [...boundNodeCodes],
      },
    ),
    result(
      'PDE-003',
      sources.router.includes('wrapPdeGovernedPage')
        && sources.router.includes('PceListPageShell')
        && sources.page.includes('data-page-template="PceListPageShell"'),
      { template: 'PceListPageShell', pageCount: pages.length },
    ),
    result(
      'PDE-004',
      sources.page.includes('PceBusinessDetailCard')
        && !sources.page.includes('<pre')
        && forbiddenTechnicalFields.every(field => !sources.page.includes(field)),
      {
        detailTemplate: 'PceBusinessDetailCard',
        forbiddenTechnicalFields,
        jsonDetailPresent: sources.page.includes('<pre'),
      },
    ),
    result(
      'PDE-005',
      ['EMD_MATERIAL_MASTER', 'EMD_ORGANIZATION', 'EMD_WORK_CENTER']
        .every(reference => dependency?.dependsOn?.includes(reference)),
      { emdReferences: dependency?.dependsOn || [] },
    ),
    result(
      'PDE-006',
      pages.every(page => (
        page.governance?.purpose
        && page.governance?.allowed?.length
        && page.governance?.forbidden?.length
        && page.governance?.flowSteps?.length === 8
        && page.governance?.navigation?.previous
        && page.governance?.navigation?.next
      ))
        && sources.page.includes('pde-business-boundary-protection'),
      {
        requiredRegions: ['当前业务动作说明', '模块主流程', '业务流程导航', '业务边界保护'],
        pageCount: pages.length,
      },
    ),
    result(
      'PDE_RETURN_MODULE_001',
      pages.every(page => page.governance?.returnModuleCode === 'PDE')
        && sources.shell.includes('governedPage.value?.returnModuleCode')
        && sources.processCenter.includes('route.query.module'),
      {
        configuredModules: pages.map(page => page.governance?.returnModuleCode),
        expected: 'PDE',
      },
    ),
  ]
}

