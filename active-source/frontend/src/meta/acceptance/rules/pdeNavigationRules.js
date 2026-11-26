export const PDE_NAVIGATION_RULESET_VERSION = 'PCE-PDE-NAVIGATION-GOVERNANCE-V492'

export const pdeNavigationRules = Object.freeze([
  Object.freeze({ ruleId: 'PDE-NAV-001', title: '所有PDE流程节点必须可跳转' }),
  Object.freeze({ ruleId: 'PDE-NAV-002', title: '页面返回必须保持模块' }),
  Object.freeze({ ruleId: 'PDE-NAV-003', title: '不存在页面绑定必须FAIL' }),
  Object.freeze({ ruleId: 'PDE-NAV-004', title: '流程中心模块定位必须正确' }),
  Object.freeze({ ruleId: 'PDE-NAV-005', title: '页面必须接入统一页面壳' }),
])

function result(ruleId, passed, evidence) {
  return {
    ruleId,
    title: pdeNavigationRules.find(rule => rule.ruleId === ruleId)?.title || '',
    status: passed ? 'PASS' : 'FAIL',
    evidence,
  }
}

export function evaluatePdeNavigationRules({ nodes, pageDefinitions, routeExists, sources }) {
  const pages = Object.values(pageDefinitions || {})
  const pageByCode = new Map(pages.map(page => [page.pageCode, page]))
  const bindings = (nodes || []).map(node => ({
    nodeCode: node.nodeCode,
    moduleCode: node.moduleCode,
    pageCode: node.pageCode,
    pageUrl: node.pageUrl,
    pageVersion: node.pageVersion,
    definitionExists: pageByCode.has(node.pageCode),
    routeExists: routeExists(node.pageUrl),
  }))
  const complete = binding => Boolean(
    binding.moduleCode === 'PDE'
      && binding.pageCode
      && binding.pageUrl
      && binding.pageVersion
      && binding.definitionExists
      && binding.routeExists,
  )
  return [
    result(
      'PDE-NAV-001',
      bindings.length === 10 && bindings.every(complete),
      { nodeCount: bindings.length, jumpableCount: bindings.filter(complete).length, bindings },
    ),
    result(
      'PDE-NAV-002',
      pages.every(page => (
        page.governance?.businessModule === 'PDE'
          && page.governance?.returnModuleCode === 'PDE'
      ))
        && sources.shell.includes("path: '/process-center'")
        && sources.shell.includes('governedPage.value?.businessModule')
        && sources.shell.includes('query: moduleCode ? { module: moduleCode } : {}'),
      { expectedReturn: '/process-center?module=PDE', governedPageCount: pages.length },
    ),
    result(
      'PDE-NAV-003',
      bindings.every(binding => binding.definitionExists && binding.routeExists),
      { missingBindings: bindings.filter(binding => !binding.definitionExists || !binding.routeExists) },
    ),
    result(
      'PDE-NAV-004',
      sources.processCenter.includes('route.query.module')
        && sources.processCenter.includes('selectProcessModule')
        && sources.processCenter.includes("selectedProcessModule === 'PDE'"),
      { query: 'module=PDE', selectedModule: 'PDE' },
    ),
    result(
      'PDE-NAV-005',
      pages.every(page => page.governance?.frameworkVersion === 'PCE Enterprise Page V2')
        && sources.router.includes('wrapPdeGovernedPage')
        && sources.router.includes('PceListPageShell')
        && sources.page.includes('data-page-template="PceListPageShell"'),
      { shell: 'PceListPageShell', pageCount: pages.length },
    ),
  ]
}
