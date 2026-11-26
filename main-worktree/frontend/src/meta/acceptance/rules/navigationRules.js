export const BUSINESS_NAVIGATION_RULESET_VERSION = 'PCE-BUSINESS-NAVIGATION-GOVERNANCE-V1.0'

export const businessNavigationRules = Object.freeze([
  Object.freeze({
    ruleId: 'NAV-007',
    title: '业务流程中心禁止存在孤立业务页面快捷入口',
    requirement: '流程中心不得在流程目录之外提供采购申请、付款申请、供应商对账或供应商绩效直达按钮。',
  }),
  Object.freeze({
    ruleId: 'NAV-008',
    title: '流程节点必须是唯一业务入口',
    requirement: '业务页面只能从模块、流程、节点导航链中的流程节点进入。',
  }),
  Object.freeze({
    ruleId: 'NAV-009',
    title: '页面必须通过流程节点访问',
    requirement: '每个已挂接业务页面必须具有唯一流程节点及有效页面地址。',
  }),
])

const result = (ruleId, passed, evidence) => ({
  ruleId,
  status: passed ? 'PASS' : 'FAIL',
  evidence,
})

export function evaluateBusinessNavigationRules({
  processCenterSource = '',
  processNodes = [],
} = {}) {
  const isolatedShortcutMatches = [
    ...processCenterSource.matchAll(/data-pce-business-module-zone=["']top["']/g),
  ]
  const boundNodes = processNodes.filter(node => node.pageUrl)
  const pageUrls = boundNodes.map(node => node.pageUrl)
  const uniquePageUrls = new Set(pageUrls)
  const uniqueNodeCodes = new Set(boundNodes.map(node => node.nodeCode))
  const nodeNavigationPresent = processCenterSource.includes('@click="node.pageUrl && router.push(node.pageUrl)"')

  return [
    result('NAV-007', isolatedShortcutMatches.length === 0, {
      isolatedBusinessShortcutCount: isolatedShortcutMatches.length,
    }),
    result(
      'NAV-008',
      isolatedShortcutMatches.length === 0 && nodeNavigationPresent,
      {
        navigationHierarchy: 'module-process-node-page',
        nodeNavigationPresent,
      },
    ),
    result(
      'NAV-009',
      boundNodes.length === processNodes.length
        && uniquePageUrls.size === boundNodes.length
        && uniqueNodeCodes.size === boundNodes.length,
      {
        processNodeCount: processNodes.length,
        boundPageCount: boundNodes.length,
        uniquePageCount: uniquePageUrls.size,
        uniqueNodeCount: uniqueNodeCodes.size,
      },
    ),
  ]
}

export function listBusinessNavigationRules() {
  return businessNavigationRules.map(rule => ({ ...rule }))
}
