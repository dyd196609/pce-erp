export const LIST_PAGE_CONTAINER_RULE_VERSION = 'V1.14.2.8.18.14'
export const LIST_PAGE_CONTAINER_RULE = Object.freeze({
  page: Object.freeze({ width: '100%', minWidth: 0, maxWidth: '100%', overflowX: 'hidden' }),
  table: Object.freeze({ width: '100%', minWidth: 0, maxWidth: '100%', overflowX: 'hidden' }),
  horizontalScrollOwner: 'element-plus-native',
  frozenLeft: Object.freeze(['selection', 'index', 'primaryNo']),
  frozenRight: Object.freeze(['operation']),
})

export function assertListPageContainerRule(rule = LIST_PAGE_CONTAINER_RULE) {
  if (rule.page?.overflowX !== 'hidden' || rule.table?.overflowX !== 'hidden'
    || rule.horizontalScrollOwner !== 'element-plus-native') {
    throw new Error('LIST_PAGE_CONTAINER_RULE_INVALID')
  }
  return rule
}
