import { LIST_PAGE_CONTAINER_RULE } from './listPageContainerRule.js'

export const LIST_CONTAINER_RUNTIME_VERSION = 'V1.14.2.8.18.13.1'

export function createListContainerRuntime({ tableMinWidth = '1180px' } = {}) {
  const minWidth = typeof tableMinWidth === 'number' ? `${tableMinWidth}px` : String(tableMinWidth || '1180px')
  if (!/^\d+(?:\.\d+)?px$/.test(minWidth)) throw new Error('LIST_CONTAINER_MIN_WIDTH_INVALID')
  return Object.freeze({ runtimeVersion: LIST_CONTAINER_RUNTIME_VERSION,
    pageStyle: Object.freeze({ width: '100%', minWidth: 0, maxWidth: '100%', overflowX: 'hidden' }),
    cardStyle: Object.freeze({ width: '100%', minWidth: 0, maxWidth: '100%', overflowX: 'hidden' }),
    tableStyle: Object.freeze({ width: '100%', minWidth: 0, maxWidth: '100%', overflowX: 'auto' }),
    tableMinWidth: minWidth, horizontalScrollOwner: LIST_PAGE_CONTAINER_RULE.horizontalScrollOwner })
}
